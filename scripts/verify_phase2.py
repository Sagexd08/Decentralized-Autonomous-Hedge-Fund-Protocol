#!/usr/bin/env python3
"""
Phase 2 gate check — IRIS_BUILD_PROMPT v2.0 section 27.

Definition of Done:
    Register/stake/unstake work on devnet; **agent-cannot-withdraw-vault test
    passes**.

The second clause is the one section 5 calls "the single highest-priority
security test in the whole repo", so this script does not merely check that
`cargo test` exited 0 — a suite that silently stopped running the custody tests
would do that too. It asserts each required test ran *and* passed by name.

    python scripts/verify_phase2.py

Exit code 0 means the security gate is met.
"""

from __future__ import annotations

import re
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

GREEN, RED, YELLOW, DIM, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m",
)

# The custody boundary. Every one of these must pass by name.
CUSTODY_TESTS = [
    "agent_pda_cannot_sign_a_vault_withdrawal",
    "a_signing_agent_cannot_drain_a_depositors_balance",
    "an_agent_cannot_conjure_its_own_balance_account",
    "an_agent_cannot_impersonate_the_allocation_engine",
    # the control: the guards must be about authority, not a broken path
    "the_depositor_can_still_withdraw",
]

# register / stake / unstake, per the first clause of the DoD.
LIFECYCLE_TESTS = [
    "register_agent_records_identity_and_moves_the_stake",
    "registering_below_the_minimum_stake_is_rejected",
    "stake_and_unstake_move_collateral_both_ways",
    "a_live_agent_cannot_unstake_below_the_minimum",
    "a_stranger_cannot_stake_against_someone_elses_agent",
    "update_model_bumps_the_version",
    "republishing_the_same_model_is_rejected",
    "a_stranger_cannot_swap_an_agents_model",
    "freeze_is_reversible_and_zeroes_allocation",
    "deactivation_retires_the_agent_and_zeroes_allocation",
    "a_retired_agent_may_recover_its_full_stake",
    "only_the_admin_may_freeze_an_agent",
]

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def run_suite() -> str:
    """Run the Anchor tests in the Linux container and return clean output."""
    print(f"{DIM}building the test image…{RESET}")
    build = subprocess.run(
        ["docker", "build", "-f", "docker/anchor.Dockerfile", "-t", "iris-anchor-test", "."],
        capture_output=True, text=True,
    )
    if build.returncode != 0:
        print(f"{RED}FAIL{RESET}  could not build the test image:\n{build.stderr[-2000:]}")
        sys.exit(2)

    print(f"{DIM}running cargo test --workspace…{RESET}\n")
    proc = subprocess.run(
        [
            "docker", "run", "--rm",
            "-v", "//c/Desktop/Coding/hacktropica/programs/iris:/work",
            "-v", "iris-cargo-registry:/usr/local/cargo/registry",
            "-v", "iris-cargo-target:/work/target",
            "iris-anchor-test", "cargo", "test", "--workspace",
        ],
        capture_output=True, text=True,
    )
    return ANSI.sub("", proc.stdout + proc.stderr)


def check(output: str, names: list[str], heading: str) -> bool:
    print(f"{heading}")
    ok = True
    for name in names:
        if re.search(rf"^test {re.escape(name)} \.\.\. ok$", output, re.M):
            print(f"  {GREEN}PASS{RESET}  {name}")
        elif re.search(rf"^test {re.escape(name)} \.\.\.", output, re.M):
            print(f"  {RED}FAIL{RESET}  {name}")
            ok = False
        else:
            print(f"  {RED}MISS{RESET}  {name} {DIM}(did not run){RESET}")
            ok = False
    print()
    return ok


DEVNET_RPC = "https://api.devnet.solana.com"


def declared_program_ids():
    """The ids the source actually claims, read from `declare_id!`."""
    root = Path(__file__).resolve().parents[1] / "programs" / "iris" / "programs"
    ids = {}
    for name in ("agent_registry", "capital_vault"):
        src = (root / name / "src" / "lib.rs").read_text(encoding="utf-8")
        match = re.search(r'declare_id!\("([^"]+)"\)', src)
        if match:
            ids[name] = match.group(1)
    return ids


def devnet_status(program_id):
    """
    Ask devnet whether this program exists and is executable.

    Read from the chain rather than from a deployment record we wrote
    ourselves. A deployment.json says what we believe happened, and the whole
    point of this check is to notice when that belief is wrong.
    """
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
        "params": [program_id, {"encoding": "base64"}],
    }).encode()
    request = urllib.request.Request(
        DEVNET_RPC, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            value = json.load(response).get("result", {}).get("value")
    except Exception as exc:
        return "UNKNOWN (" + type(exc).__name__ + ")"

    if value is None:
        return "NOT DEPLOYED"
    return "DEPLOYED" if value.get("executable") else "NOT EXECUTABLE"


def report_devnet():
    """
    Report the devnet half of the DoD. Returns True when both are live.

    Deliberately outside the pass/fail count: the security gate is about the
    custody boundary, and a rate-limited faucet must not be able to turn that
    red. It is printed every run anyway, because a DoD half nobody looks at is
    a DoD half nobody does.
    """
    print("")
    print("Devnet deployment")
    print("-" * 62)

    deployed = True
    for name, program_id in declared_program_ids().items():
        status = devnet_status(program_id)
        colour = GREEN if status == "DEPLOYED" else YELLOW
        print("  " + name.ljust(18) + program_id)
        print("  " + "".ljust(18) + colour + status + RESET)
        deployed = deployed and status == "DEPLOYED"
    return deployed


def main() -> int:
    output = run_suite()

    custody = check(output, CUSTODY_TESTS, "Custody boundary — agents never hold capital")
    lifecycle = check(output, LIFECYCLE_TESTS, "Registry lifecycle — register / stake / unstake")

    if not (custody and lifecycle):
        print(f"{RED}Phase 2 gate FAILED{RESET} — do not checkpoint.\n")
        return 1

    print(f"{GREEN}Phase 2 security gate PASSED{RESET} — "
          f"{len(CUSTODY_TESTS) + len(LIFECYCLE_TESTS)} tests green.")

    if report_devnet():
        print("")
        print(GREEN + "Phase 2 COMPLETE" + RESET + " — custody gate green and "
              "both programs live on devnet.")
        print("")
        return 0

    print("")
    print(YELLOW + "The DoD is not fully met." + RESET + " These tests run against "
          "solana-program-test,")
    print("which executes the real program against the real runtime — but the DoD")
    print('also says the instructions work "on devnet", and that is a different claim.')
    print("")
    print("The toolchain is ready: `make devnet-deploy` builds both programs with")
    print("cargo-build-sbf and deploys them, and declare_id!/Anchor.toml are already")
    print("synced to keypairs we hold. What is missing is devnet SOL — the faucet")
    print("rate-limits per IP. Fund the deployer address the script prints, re-run.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
