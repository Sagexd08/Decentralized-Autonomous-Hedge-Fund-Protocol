# IRIS Build State

> Per IRIS_BUILD_PROMPT v2.0 §0b. Every session starts by reading this file, not by
> re-reading the whole spec. Updated at every phase checkpoint.

## Current phase

**Phase 2 — AgentRegistry + CapitalVault.** Security gate PASSED; the phase is
**not fully checkpointed**, because the DoD also says these instructions work
"on devnet" and nothing has been deployed. See *Known blockers* 6.

`python scripts/verify_phase2.py` → 17/17 green (5 custody + 12 lifecycle).
Phase 1 remains complete (`verify_phase1.py` → 0).

### Phase 2 Definition of Done (§27)

| Requirement | Status |
|---|---|
| `agent-cannot-withdraw-vault` test passes | **verified** |
| register / stake / unstake work | verified against solana-program-test |
| …on devnet | **NOT DONE** — no toolchain, no funded keypair |

### Phase 1 Definition of Done (§27)

| Requirement | Status |
|---|---|
| Repo restructured to §4 | done |
| Stellar removed (§2 single-chain) | done |
| 21 tables, real FKs and indexes (§13) | done — `db/migrations/0001_init.sql` |
| `docker compose up` boots web + api + db | verified |
| health route returns 200 on all three | verified |

```
PASS  api          200  {"status":"ok","service":"iris-api","version":"2.2.0"}
PASS  api-db       200  {"status":"ok","dialect":"postgresql"}
PASS  web          200  {"status":"ok","service":"iris-web"}
PASS  schema       all 21 tables present
```

Plus 16/16 in `tests/integration/test_schema_invariants.py`.

## Decisions taken

1. **Migration strategy: rewrite in place, drop Stellar.** Chosen over building a
   parallel `iris/` tree. Four deployed Soroban testnet contracts and the
   dual-chain settlement path were deleted, not archived — they remain in git
   history at `43298fd` if ever needed.
2. **Start at Phase 1** rather than jumping to the prediction primitive.

## Done

### Phase 1 (commits `a72d3ed`, pending)

- [x] `frontend/` → `apps/web/`, `backend/` → `apps/api/`.
- [x] Stellar removed end to end: 4 Soroban crates, the client, settings, every
      `STELLAR_*` read, dual-chain writes in the trading engine, Stellar
      branches in 5 routers, the Freighter XDR build/submit endpoints, the
      `use-freighter` hook, the two-chain stake selector, `STELLAR_META`,
      `stellar-sdk` and `@stellar/freighter-api`.
- [x] `ws_trading.stellar_event_listener` → `chain_event_listener`, Solana only.
- [x] Wallet button falls back to a disabled "Wallet unavailable" state instead
      of Freighter when Privy is unconfigured.
- [x] **21-table schema** in `db/migrations/0001_init.sql`. Notable constraints:
      `predictions` has `CHECK (committed_at <= horizon_end)` and a unique
      `prediction_hash`; outcomes live in a separate table so settling never
      `UPDATE`s a committed claim; `reputation_scores` stores dimensions *and*
      weights so historical scores are re-derivable; `trades.execution_mode` is
      a `SIMULATION | TESTNET | LIVE` enum, making honest labelling a schema
      property. pgvector enabled for `market_events` / `news_events`.
- [x] Seed: 8 named agents (Axiom, Vector, Helix, Quanta, Meridian, Pulse,
      Nexus, Sigma), 4 model families, 3 vaults. No placeholder names.
- [x] `docker/{web,api}.Dockerfile`, rewritten `docker-compose.yml` on
      `pgvector/pgvector:pg16`, `.env.example` documenting every variable,
      `Makefile`.
- [x] Health routes: `GET /health` and `GET /health/db` (503 when the Postgres
      round trip fails) on the API; `GET /health` on the web app.
- [x] `scripts/verify_phase1.py` — asserts the gate, including that all 21
      tables exist. This is the phase's automated test.
- [x] §4 skeleton dirs (`agents/`, `ml/`, `packages/*`, `tests/*`,
      `programs/iris/`), each with a README naming the phase that owns it.
- [x] README rewritten: accurate layout, honest Limitations section.

### Phase 2

- [x] `programs/iris/` Anchor workspace: `agent_registry` and `capital_vault`
      moved out of their standalone workspaces under `contracts/rust/solana/`.
- [x] Registry extended to the full §5 surface — added `update_model`, `stake`,
      `unstake`, `deactivate_agent`, `freeze_agent`, `unfreeze_agent`.
      `AgentAccount` gained `agent_id`, `model_hash`, `model_version`,
      `reputation`, `allocation_weight`; `AgentStatus` gained `Frozen`.
- [x] **5 custody tests** in `capital_vault/tests/vault_custody.rs`, including
      the §5 gate. They assert the agent PDA is off-curve *and* that the runtime
      rejects the withdrawal, plus a control test proving the withdrawal path
      works for the actual depositor — a path that rejected everyone would pass
      the other four while proving nothing.
- [x] **12 lifecycle tests** in `agent_registry/tests/registry_lifecycle.rs`.
- [x] `docker/anchor.Dockerfile` + `make anchor-test`: the tests use
      `solana-program-test` with `processor!()`, so they need neither a
      validator nor the SBF toolchain — but `solana-runtime` pulls OpenSSL,
      whose vendored build fails under Git Bash on Windows, so they run in
      Linux.
- [x] `scripts/verify_phase2.py` asserts each required test passed **by name**,
      not just that the suite exited 0.

### Outside the phase loop

- [x] Brand assets extracted from the supplied lockup screenshot →
      `apps/web/public/iris-{mark,logo,wordmark}.png`; favicon wired to
      `favicon.ico`; navbar leads with the mark. (`b28e012`)
- [x] Vercel Turbopack build unblocked. (`8ff62ae`)

## Stubbed / SIMULATION-labeled

- **Price data is simulated** (`WS_MARKET_SOURCE=simulated`, Ornstein–Uhlenbeck
  engine). Not yet labeled in the UI — **violates §0c**, must be fixed by
  whichever phase next touches those screens.
- **Governance is off-chain** (`governance_store.json` + in-process singleton).
- **Prediction primitive is schema-only.** Tables enforce commit-before-outcome,
  but nothing writes to them; the runtime still submits returns directly.
- **Algorand** client, settings and `use-algorand` hook survive; not in the
  trading loop. Slated for removal.

## Deferred

- Anchor workspace consolidation into `programs/iris/programs/` → **Phase 2**,
  with the agent-cannot-withdraw-vault test.
- Full §25 README (Mermaid diagrams, security model, testnet deploy) → Phase 16.
- Production multi-stage web Dockerfile → Phase 16. The current one runs
  `next dev`, which is all Phase 1's gate requires.

## Known blockers

1. **Vercel will 404 until its Root Directory is changed** from `frontend` to
   `apps/web`. The deploy at `8ff62ae` was green; the next push breaks it until
   that project setting is updated. Nothing in the repo can fix this.
2. **`apps/web/node_modules` is gone.** Deleted during the move because a
   concurrent `npm install` had corrupted it (individual `.js` files missing
   from `@noble/hashes`, `ws`, `@scure/base`, `@heroicons/react`). Run
   `npm install` in `apps/web`, or just use Docker.
3. **`apps/api/.venv310` has stale absolute paths** after the move. Recreate it
   or use Docker.
4. **`tests/test_agent_trading_engine.py` is stale** — it constructs
   `AgentTradingEngine(w3=…, vault_contract=…, price_feed_contract=…, accounts=…)`,
   none of which are parameters any more, and asserts lowercase decisions
   against an engine that returns uppercase. Pre-existing, not caused by the
   Stellar removal. Belongs to Phase 3's rewrite of the runtime.
5. **The 4-month-old `pgdata` volume was destroyed.** It had to be: Postgres
   saw an existing data directory, skipped initialisation entirely, and the
   volume contained neither an `iris` nor a `postgres` role — an aborted init
   from 2026-04-04 that no credential could read. Nothing was recoverable.
   Stale `hacktropica-frontend`/`-backend` images (1.5 GB + 8.6 GB) remain and
   can be pruned.

6. **Nothing is deployed to devnet.** Needs the `solana` and `anchor` CLIs
   (neither installed; Anchor has no first-class Windows support and wants WSL)
   and a funded devnet keypair. The program IDs in `Anchor.toml` are inherited
   from the pre-v2 deployment and have not been re-verified against the
   modified programs — `agent_registry` changed shape this phase, so its
   deployed bytecode no longer matches this source.

## Local edit outside the repo

`.env` lines 53–58 were pasted CLI output (`Deployer balance OK: …`,
`Algorand deploy failed: …`), which is not valid dotenv and made
`docker compose config` fail. They are now commented out; all values preserved.

## Bugs found by the gates (not written by them)

1. **`AgentList` was unallocatable.** `#[max_len(5000)]` on `Vec<Pubkey>` asks
   for ~160KB, but the runtime caps a program-created account at 10,240 bytes.
   `initialize` failed with `InvalidRealloc` — on devnet exactly as in the
   harness, so the registry could never have been initialised as written.
   Capped at 300 (ceiling is 319). Growing past that needs a different shape,
   not a bigger number.
2. **Migrations never ran** (Phase 1) — a stale `pgdata` volume.
3. **torch pulled the CUDA wheel** (Phase 1) — 8.63GB → 3.24GB.

## Next phase

**Phase 3 — agent runtime + LangGraph.** DoD: one agent completes the full graph
end to end on synthetic data, checkpointed in Neon. Note that
`apps/api/tests/test_agent_trading_engine.py` is stale and belongs to this
phase's rewrite (blocker 4).

## Last verified commit

`d1b9d2a` — chore(phase-1): checkpoint — gate passed
