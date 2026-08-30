# IRIS Build State

> Per IRIS_BUILD_PROMPT v2.0 §0b. Every session starts by reading this file, not by
> re-reading the whole spec. Updated at every phase checkpoint.

## Current phase

**Phase 1 — repo, Docker, database, skeleton.**
Implementation complete; **gate not yet verified**. `docker compose up -d --build`
is running for the first time against the new compose file. Phase 1 may not
checkpoint, and Phase 2 may not start, until `python scripts/verify_phase1.py`
exits 0.

### Phase 1 Definition of Done (§27)

| Requirement | Status |
|---|---|
| Repo restructured to §4 | done |
| Stellar removed (§2 single-chain) | done |
| 21 tables, real FKs and indexes (§13) | done — `db/migrations/0001_init.sql` |
| `docker compose up` boots web + api + db | **unverified** |
| health route returns 200 on all three | **unverified** |

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
5. **Stale containers from the old compose file** (`backend`, `frontend`,
   `postgres`) are still on the machine, plus an 8.6 GB `hacktropica-backend`
   image. Safe to `docker rm` / `docker image prune` once the new stack is up.

## Local edit outside the repo

`.env` lines 53–58 were pasted CLI output (`Deployer balance OK: …`,
`Algorand deploy failed: …`), which is not valid dotenv and made
`docker compose config` fail. They are now commented out; all values preserved.

## Last verified commit

`a72d3ed` — refactor: restructure to apps/ layout and drop Stellar
