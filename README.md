# IRIS Protocol — Autonomous Intelligence Market

> **Where intelligence competes for capital.**

IRIS is a protocol where autonomous ML agents compete for capital based on
measurable, verifiable performance:

```
prediction → verifiable outcome → reputation → capital reallocation → economic consequence
```

Capital sits in on-chain vaults on Solana. Agents publish trading signals and
are scored on what actually happened. A Multiplicative Weights Update rule
continuously shifts allocation toward whoever is earning it, and agents that
breach drawdown limits are slashed automatically.

**No agent ever custodies investor capital.** Allocation authority is not wallet
control, and the vault enforces that at the contract level.

---

## Build status

This repository is mid-migration to
[`IRIS_BUILD_PROMPT v2.0`](#build-phases). Read
[`STATE.md`](STATE.md) before starting work — it records which phase is
current, what is stubbed, and what is deferred. It is the resumable memory for
the build loop, and it is more current than this file.

| | |
|---|---|
| Current phase | **Phase 1** — repo, Docker, database, skeleton |
| Canonical chain | Solana (Stellar was removed in `a72d3ed`) |
| Market data | **Simulated** — see [Limitations](#limitations) |

---

## Quick start

```bash
git clone <repo> && cd iris
cp .env.example .env
docker compose up -d --build
```

Every value in `.env.example` is optional. Each unset secret degrades its
subsystem to a labelled simulation path rather than failing the boot.

Then verify the stack:

```bash
make verify
```

which asserts the Phase 1 gate — that `web`, `api` and `db` all answer:

| Service | Check |
|---|---|
| web | `GET http://localhost:3000/health` → 200 |
| api | `GET http://localhost:8000/health` → 200 |
| api → db | `GET http://localhost:8000/health/db` → 200 |
| db | all 21 tables present |

`make help` lists the rest.

---

## Repository layout

```
.
├── apps/
│   ├── web/          Next.js 16 dashboard (App Router, React 19, Tailwind v4)
│   └── api/          FastAPI service — routers, agent runtime, ML, chain clients
├── programs/
│   └── iris/         Anchor workspace (Phase 2 consolidates the programs here)
├── contracts/
│   ├── rust/solana/  the four Anchor programs as they stand today
│   ├── src/          Solidity reference implementation, not deployed
│   └── test/         Hardhat tests for the reference contracts
├── agents/           LangGraph runtime, strategies, tools        (Phase 3)
├── ml/               models, training, inference, regime, risk   (Phase 4)
├── packages/         shared types, SDK, config                   (Phases 6–10)
├── db/
│   ├── migrations/   source of truth for the schema
│   ├── seed/         development fixtures
│   └── schema.sql    pointer + dump instructions
├── docker/           web and api Dockerfiles
├── scripts/          phase gate checks
├── tests/            unit, integration, ml, e2e
├── docker-compose.yml
├── Makefile
└── STATE.md          build state — read this first
```

Directories owned by a later phase contain a README saying so, and are
otherwise empty. That is deliberate: the build runs phase by phase and does not
reach ahead.

---

## How the protocol works

### Capital custody

Investors deposit into one of three vaults, distinguished by a volatility cap:
conservative (800 bps), balanced (1800 bps), aggressive (3500 bps). These are
**constraints, not promised returns**. Funds are tracked on-chain; the API never
holds capital.

### Agents

An agent registers, stakes collateral, and is placed on probation. It receives
allocation only once active, and its allocation is a weight — never a key.

### Allocation

Every active agent publishes a return. The allocator then runs

```
w_i(t+1) = w_i(t) · exp(η · R_i(t))  /  Σ_j w_j(t+1)
```

over the risk-adjusted score

```
R_i = Return / (Volatility + λ · |Drawdown|)
```

Raw return alone would reward whoever levered hardest, so it is not used. MWU is
chosen over a heuristic because it carries a regret bound of `O(√(T · ln N))`
against the best fixed agent in hindsight.

η is governance-tunable and takes effect on the allocator's next step.

### Consequence

Drawdown past the configured threshold (2000 bps by default) triggers an
automatic slash. No committee approves it.

---

## Database

21 tables, defined in [`db/migrations/0001_init.sql`](db/migrations/0001_init.sql)
with real foreign keys, real indexes and real check constraints. Highlights:

- **`predictions`** carries a `prediction_hash` and a `CHECK` that
  `committed_at <= horizon_end`, so a prediction provably existed before its
  outcome could be known.
- **`prediction_outcomes`** is a separate table keyed on the prediction, so
  settling an outcome never requires an `UPDATE` that could rewrite a committed
  claim.
- **`reputation_scores`** stores the dimension values *and* the weights used, so
  any historical IRIS Score can be re-derived rather than trusted.
- **`trades.execution_mode`** is a constrained enum — `SIMULATION`, `TESTNET` or
  `LIVE` — so honest labelling is a schema property, not a convention.

`pgvector` is enabled for the historical-memory layer; `market_events` and
`news_events` carry embedding columns.

---

## Build phases

The build follows a per-phase loop: plan, implement, self-test, verify against
the phase's Definition of Done, checkpoint into `STATE.md`, advance. A phase
that ships a feature which *looks* real but is not fails its gate regardless of
what else passed.

| # | Phase | Gate |
|---|---|---|
| 1 | Repo, Docker, DB, skeleton | `docker compose up` → 200 on web, api, db |
| 2 | AgentRegistry + CapitalVault | **agent cannot withdraw the vault** |
| 3 | Agent runtime + LangGraph | one agent completes the graph, checkpointed |
| 4 | ML models + inference | 4 model classes, baseline comparison logged |
| 5 | Prediction commit + evaluation | hash pre-horizon, settle post-horizon |
| 6 | Reputation engine | IRIS Score from ≥6 dimensions, unit-tested |
| 7 | MWU allocation | 4 mathematical invariants pass as tests |
| 8 | Risk + slashing | breach → freeze → slash → reduced allocation |
| 9 | WebSocket infra | real events from phases 3–8 reach a client |
| 10–12 | Arena, Observatory, Ledger | driven by real rows, not fixtures |
| 13 | Simulation + backtesting | same seed → same result |
| 14–16 | Security, testing, polish | full checklist and matrix green |

---

## Limitations

Stated plainly, because claiming production readiness we do not have would
violate the protocol's own honesty rule.

- **Market data is simulated.** `WS_MARKET_SOURCE` defaults to `simulated`;
  prices come from an Ornstein–Uhlenbeck engine, not an exchange. Every P&L,
  Sharpe ratio and slash currently runs against synthetic tape. The UI does not
  yet label this everywhere it should — that is tracked in `STATE.md`.
- **Governance is off-chain.** Proposals, votes and quorum resolve in a JSON
  store and an in-process singleton. The parameter change is real and
  immediate; the vote is not on-chain.
- **The prediction primitive is schema-only.** The tables enforce the
  commit-before-outcome ordering, but nothing writes to them yet — the agent
  runtime still submits returns directly. This is Phase 5.
- **No agent is on LangGraph yet.** The current runtime is an asyncio loop with
  three hardcoded strategy archetypes. This is Phase 3.
- **The Anchor programs are not consolidated.** Four standalone workspaces under
  `contracts/rust/solana/`; `programs/iris/` is still a placeholder. This is
  Phase 2, along with the security test that matters most.
- **Solidity contracts under `contracts/src/` are a reference implementation.**
  They are not deployed and are not on any critical path.
- **Algorand is vestigial.** A client, settings and a frontend hook survive from
  before the v2 migration. Not in the trading loop; slated for removal.
- **No token.** There is no `$IRIS` token and there will not be one until a
  mechanism justifies it. The protocol has to be compelling without it.

---

## Development without Docker

Docker is the supported path. If you need the services directly:

```bash
# api
cd apps/api
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# web
cd apps/web
npm install
npm run dev
```

`apps/api/.venv310` predates the `backend/ → apps/api/` move and has stale
absolute paths baked in; recreate it rather than reusing it.

---

## Testing

```bash
make test                      # API suite inside the container
python scripts/verify_phase1.py  # Phase 1 gate
```

The testing matrix each phase must satisfy lives in the build prompt; a phase
does not checkpoint without its row passing.
