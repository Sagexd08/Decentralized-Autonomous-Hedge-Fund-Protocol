#!/usr/bin/env bash
#
# Build and deploy the IRIS programs to Solana devnet.
#
# Phase 2's DoD says the registry and vault instructions work "on devnet". The
# Rust tests prove the logic against the real runtime; this proves the program
# a validator will actually load. They are different claims, and the second one
# has caught things the first cannot: an account that is too large to allocate,
# a program that exceeds the BPF size limit, a `declare_id!` that does not match
# the key it is deployed under.
#
# Idempotent. Existing program keypairs and an existing deploy wallet are reused
# — a redeploy must land on the same program IDs, or every client and every PDA
# derived from them breaks.
#
# Keys live in /keys, which is a mounted volume. Nothing here writes a key into
# the repository or the image.

set -euo pipefail

CLUSTER="${CLUSTER:-devnet}"
RPC="${RPC_URL:-https://api.devnet.solana.com}"
KEYS="${KEYS_DIR:-/keys}"
WORK="${WORK_DIR:-/work}"
PROGRAMS=(agent_registry capital_vault)

# Rent for the program account plus its upload buffer. Measured, not guessed:
# each of these programs is ~350KB and costs ~2.45 SOL to deploy, so two need
# ~5 with headroom for fees and a retry. The first version of this asked for 3
# and failed halfway through the first program, leaving an orphaned buffer
# holding the lamports it needed to finish.
MIN_SOL="${MIN_SOL:-6}"

blue()  { printf '\033[34m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
dim()   { printf '\033[2m%s\033[0m\n' "$*"; }

mkdir -p "$KEYS"
solana config set --url "$RPC" >/dev/null

# ── 1. the deploy wallet ─────────────────────────────────────────────────────

WALLET="$KEYS/deployer.json"
if [ ! -f "$WALLET" ]; then
  blue "Generating a devnet deploy wallet (it stays in the mounted volume)"
  solana-keygen new --no-bip39-passphrase --silent --outfile "$WALLET"
fi
solana config set --keypair "$WALLET" >/dev/null
DEPLOYER="$(solana address)"
blue "Deployer: $DEPLOYER"

balance_sol()      { solana balance | awk '{print $1}'; }
balance_lamports() { solana balance --lamports | awk '{print $1}'; }

# Compared in lamports, as integers, in the shell.
#
# This was `(( $(echo "$have < $MIN_SOL" | bc -l) ))`, and `bc` is not in the
# image. Both comparisons errored, both evaluated false, and the deploy went
# ahead regardless of balance — so the guard added specifically to stop a
# half-funded run from stranding its own lamports in an orphaned buffer had
# never once executed. It only looked fine because the balance happened to be
# sufficient the first time it mattered.
MIN_LAMPORTS=$(( MIN_SOL * 1000000000 ))

have="$(balance_sol)"
dim "Balance: $have SOL"

# The devnet faucet rate-limits hard. Ask a few times, then stop and say so
# rather than looping forever or pretending the deploy can proceed.
attempts=0
while [ "$(balance_lamports)" -lt "$MIN_LAMPORTS" ] && [ "$attempts" -lt 6 ]; do
  attempts=$((attempts + 1))
  dim "Requesting an airdrop (attempt $attempts)…"
  solana airdrop 2 >/dev/null 2>&1 || true
  sleep 5
  have="$(balance_sol)"
done

if [ "$(balance_lamports)" -lt "$MIN_LAMPORTS" ]; then
  red "Balance is $have SOL; deploying both programs needs about $MIN_SOL."
  red ""
  red "The devnet faucet rate-limits per IP and is currently refusing. Fund"
  red "this address and re-run — nothing else needs to change:"
  red ""
  red "  $DEPLOYER"
  red ""
  red "  https://faucet.solana.com  (web, needs a GitHub login)"
  red "  solana airdrop 5 $DEPLOYER --url devnet   (from a machine with quota)"
  red ""
  dim "The keypair lives in the mounted volume, so the address is stable across"
  dim "runs. Program keypairs are generated once and reused, so a funded retry"
  dim "lands on the same program IDs."
  exit 2
fi
green "Funded: $have SOL"

# ── 1b. reclaim orphaned buffers ─────────────────────────────────────────────
#
# A deploy that runs out of funds partway leaves a write buffer holding most of
# the lamports it needed to finish — so the retry is poorer than the attempt
# that failed, and every retry makes it worse. Reclaim them first.

# `solana program show --buffers --output json` answers {"buffers": [...]},
# not a bare array — so `.[]?.bufferAddress` raised "Cannot index array with
# string" on every run and reclaimed nothing. The element key has also moved
# between releases, so both spellings are accepted rather than pinned to the
# one this image happens to ship.
buffers="$(solana program show --buffers --output json 2>/dev/null   | jq -r '(.buffers // .)[]? | (.address // .bufferAddress) // empty'   2>/dev/null || true)"
if [ -n "$buffers" ]; then
  blue "Reclaiming lamports from orphaned deploy buffers"
  for b in $buffers; do
    dim "  closing $b"
    solana program close "$b" --bypass-warning >/dev/null 2>&1 || true
  done
  have="$(balance_sol)"
  green "Balance after reclaim: $have SOL"
fi

# ── 2. program keypairs, and declare_id! agreement ───────────────────────────
#
# A program's address IS its keypair's pubkey, and `declare_id!` in the source
# must equal it. If they disagree the program deploys and then rejects every
# instruction with DeclaredProgramIdMismatch — it looks deployed and is inert.

declare -A PROGRAM_ID
for p in "${PROGRAMS[@]}"; do
  kp="$KEYS/$p-keypair.json"
  [ -f "$kp" ] || solana-keygen new --no-bip39-passphrase --silent --outfile "$kp"
  PROGRAM_ID[$p]="$(solana address -k "$kp")"
  blue "$p → ${PROGRAM_ID[$p]}"
done

blue "Syncing declare_id! and Anchor.toml to the deploy keypairs"
for p in "${PROGRAMS[@]}"; do
  src="$WORK/programs/$p/src/lib.rs"
  current="$(grep -oP 'declare_id!\("\K[^"]+' "$src")"
  if [ "$current" != "${PROGRAM_ID[$p]}" ]; then
    dim "  $p: $current → ${PROGRAM_ID[$p]}"
    sed -i "s|declare_id!(\"$current\")|declare_id!(\"${PROGRAM_ID[$p]}\")|" "$src"
    sed -i "s|$current|${PROGRAM_ID[$p]}|g" "$WORK/Anchor.toml"
  else
    dim "  $p: already in sync"
  fi
done

# ── 3. build ─────────────────────────────────────────────────────────────────

blue "Building BPF objects (cargo build-sbf)"
cd "$WORK"
for p in "${PROGRAMS[@]}"; do
  cargo build-sbf --manifest-path "programs/$p/Cargo.toml" --sbf-out-dir target/deploy
done

for p in "${PROGRAMS[@]}"; do
  so="target/deploy/$p.so"
  [ -f "$so" ] || { red "missing $so"; exit 1; }
  dim "  $p.so  $(stat -c%s "$so") bytes"
done

# ── 4. deploy ────────────────────────────────────────────────────────────────

for p in "${PROGRAMS[@]}"; do
  # Checked before each program, not once at the start. A balance that was
  # enough for two is not enough for two after the first has been paid for, and
  # discovering that mid-upload is exactly what strands a buffer.
  have="$(balance_sol)"
  dim "$p: balance $have SOL"

  blue "Deploying $p"
  if ! solana program deploy     --program-id "$KEYS/$p-keypair.json"     --upgrade-authority "$WALLET"     "target/deploy/$p.so"
  then
    red ""
    red "Deploy of $p failed. Any buffer it stranded is reclaimed automatically"
    red "on the next run, so re-run once the wallet is funded:"
    red "  $DEPLOYER"
    exit 1
  fi
done

# ── 5. verify on chain ───────────────────────────────────────────────────────
#
# Not "the deploy command exited 0" — read the account back and check it is an
# executable program owned by the loader. A deploy that half-succeeded leaves a
# buffer account behind and reports nothing.

blue "Verifying on chain"
ok=1
for p in "${PROGRAMS[@]}"; do
  id="${PROGRAM_ID[$p]}"
  info="$(solana program show "$id" 2>&1 || true)"
  if echo "$info" | grep -q "Program Id: $id"; then
    len="$(echo "$info" | grep -oP 'Data Length: \K[0-9]+' || echo '?')"
    auth="$(echo "$info" | grep -oP 'Authority: \K\S+' || echo '?')"
    green "  $p  $id  ${len} bytes  authority ${auth}"
  else
    red "  $p  $id  NOT FOUND on $CLUSTER"
    echo "$info" | head -3
    ok=0
  fi
done

[ "$ok" -eq 1 ] || exit 1

cat > "$KEYS/deployment.json" <<EOF
{
  "cluster": "$CLUSTER",
  "rpc": "$RPC",
  "deployer": "$DEPLOYER",
  "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "programs": {
    "agent_registry": "${PROGRAM_ID[agent_registry]}",
    "capital_vault": "${PROGRAM_ID[capital_vault]}"
  }
}
EOF

green ""
green "Deployed to $CLUSTER. Record written to \$KEYS/deployment.json."
dim "Explorer: https://explorer.solana.com/address/${PROGRAM_ID[agent_registry]}?cluster=devnet"
