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
| Phases complete | **1–13** |
| Canonical chain | Solana (Stellar was removed in `a72d3ed`) |
| On-chain | **Live on devnet** — `agent_registry` `6NTKNCtBnNAJjGfgFRNTPhbxBYz1GXv3mQRRdwdC2cNy`, `capital_vault` `HYxAvbCGmv7axJfQbbSxQXLyNiAhPQUyAsEo6nVUW1Gj` |
| Market data | **Real.** One-minute bars and live ticks from public exchanges, written to `market_events` under the `LIVE` label with the venue recorded |
| Model weights | Fitted on a **frozen snapshot of real market data** (`make dataset` shows which) |
| Capital | **None.** Allocations are weights, not transfers. No live funds are deployed |

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

`make verify-all` runs every phase gate. `make help` lists the rest.

### Bootstrapping a fresh database

A clone has no price history and no fitted models, so an agent has nothing to
look at and nothing to look with:

```bash
make feed     # ingest real one-minute bars from a public exchange  (~1 min)
make train    # freeze a snapshot from them and fit the models      (~3 min)
```

`make feed` is idempotent — it writes only the minutes it is missing — and the
API keeps the tape current on its own from then on. `make train` is deliberately
*not* automatic: refitting changes every model's hash, and a version history in
which every entry is new is not a version history.

### Running one full prediction cycle

The steps are separate on purpose — each is a different actor, and collapsing
them is how a system starts marking its own homework.

```bash
docker compose exec api python -m agents.runtime.runner --agent AGT-HELIX --asset BTC --seed 7
make settle     # once the 10-minute horizon has actually closed
make score      # IRIS Score per agent, per provenance
make risk       # breach -> freeze -> slash
make allocate   # one MWU step
```

`make cycle` runs feed -> settle -> score -> risk -> allocate in order.

The feed writes the market. The agent observes it — out of the same table the
settlement sweep will later measure it against — and commits a hashed
prediction *before* the horizon. The sweep measures what happened and scores it.
The agent never writes the price it will be judged against; see
`agents/runtime/persistence.persist_prediction` for why that is enforced rather
than merely intended.

Most runs **abstain**, and that is the correct behaviour rather than a
misconfiguration — see [What the models actually do](#what-the-models-actually-do).

A prediction whose horizon has closed but for which no price evidence exists
does **not** get settled. It parks in `WAITING_FOR_OUTCOME` and counts toward
nothing. `make settle` reports those separately, because the number of
predictions the system declines to score is as informative as the ones it does.

---

## Market data

Prices are real. `market_events` holds one-minute bars and live ticks from
public venues — Binance, Coinbase and Kraken behind one interface — labelled
`LIVE` with the venue that produced each row. The API runs a poller that keeps
the tape current, so a prediction committed now can be settled when its horizon
closes ten minutes from now.

```bash
make market    # feed health, coverage, and the current cross-venue spread
make dataset   # what the models are currently fitted on
make why       # why each agent traded or abstained, gate by gate
```

Everything used is public, unauthenticated market data. **This package holds no
API keys and needs none** — which matters beyond convenience: the cheapest way
to guarantee no credentials in source is for the code to have nothing to hold.

Four rules are enforced rather than intended, because every way this goes wrong
looks fine from the outside:

**A tape never mixes venues.** BTCUSDT on Binance, BTC-USD on Coinbase and
XBTUSD on Kraken are three instruments tracking one asset a few basis points
apart. Settlement pins both of its legs to one source *and* one venue and
refuses to measure across them. A return taken from two exchanges is the spread
between them wearing an agent's name — and unlike a synthetic-versus-real
splice, which produces an obviously broken number, this one looks entirely
plausible.

**A recorded observation is immutable.** Once the protocol has written down what
the market did at an instant, that is the ground truth every reputation score
rests on. A `LIVE` row cannot be restated or deleted. Committing a prediction
freezes the *claim*; this freezes the thing it is judged against.

**A price must be a price.** A zero makes a settled return infinite, a negative
flips its sign, and a NaN propagates silently into an IRIS Score. All three are
rejected by the database.

**Claiming a price is real requires naming who said so.** `source = 'LIVE'`
without a `provider` is a constraint violation, so synthetic data cannot be
relabelled real without asserting that a specific exchange said it.

A candle is stamped at the **close** of the minute it describes, not the open.
Filing the close price under the open timestamp would put every observation
sixty seconds early, in the same direction, for every prediction — a systematic
bias that never looks like a bug because the series still moves plausibly.

If every venue is unreachable, nothing is written. `price_at` then finds no
evidence, the prediction parks in `WAITING_FOR_OUTCOME`, and it is never scored.
A gap in the record is the correct output; a guessed price is a lie in it.

---

## What the models actually do

Four model classes sit behind one interface: a baseline heuristic, gradient
boosting, a CNN-LSTM and a small transformer. `scripts/verify_phase4.py` fits
them on the frozen snapshot of real market data and scores them **out of
sample** against the baseline.

It currently fails, and that is the honest result:

| model | dominant class | trades | verdict |
|---|---|---|---|
| baseline | 39% | 1345 / 3009 | BASELINE |
| gradient_boosting | 98% HOLD | 50 | DEGENERATE |
| cnn_lstm | **100% HOLD** | 0 | DEGENERATE |
| transformer | 100% HOLD | 15 | DEGENERATE |

**No model beats the baseline.** They are fitted correctly, on real data, at the
right horizon, and graded on data they have not seen. They have learned that the
most likely ten-minute outcome for BTC is "no move", which minimises their loss
and makes them untradeable — shown a tape trending +50 bps per minute, the
CNN-LSTM still predicts −0.91 bps.

This gate is left failing on purpose. It passed for nine phases on a synthetic
tape that was predictable by construction; relaxing the check to recover that
would be exactly the faked production readiness this protocol's own honesty rule
forbids. Getting a model to beat the baseline on real data is open research, not
a build step — and it is the question the protocol exists to ask.

The consequence downstream is visible and intended: most agents abstain most
cycles, reputation stays low, and the allocator has little reason to move
capital. A system in which every agent traded confidently on this data would be
evidence of a bug, not of skill.

**`make why` is how you tell a quiet market from a broken gate.** It prints,
per agent, what the model predicted, how sure it was of the *side*, what each
gate required, and which one actually refused. Two gates answer two different
questions, and conflating them is a mistake this codebase has now made three
times with three different constants:

| gate | question | fails when |
|---|---|---|
| `decision_threshold` | is the move big enough to be worth a position? | the predicted move is inside the band scoring treats as flat |
| `MIN_DIRECTIONAL_CONFIDENCE` | does the model know *which way*? | the model's own distribution barely favours one side over the other |

Both scale with something real — the first with observed volatility, the second
with the model's own error bar — rather than being fixed numbers that were
calibrated once against a market that no longer exists.

---

## Deployment

The two halves of this system have genuinely different hosting requirements,
and the split is not a preference.

| piece | where | why |
|---|---|---|
| web | **Vercel** — [iris-protocol.vercel.app](https://iris-protocol.vercel.app) | a Next.js app; nothing about it needs a server that stays up |
| API | **Render free** (`render.yaml`, `docker/api.slim.Dockerfile`) | every answer it gives is a database read |
| the protocol cycle | **GitHub Actions** (`.github/workflows/cycle.yml`) | agents do not run themselves, and Render has no free cron |
| Postgres + pgvector | **Neon** | the schema declares vector columns on `market_events` and `news_events` |

**The API cannot run on Vercel.** Serverless functions are request-scoped: a
market-feed poller with nobody calling it does not run, and a WebSocket does
not survive the response. That is why `render.yaml` exists — Render's dashboard
takes it directly (New → Blueprint → connect this repository), and any
container host with a cron facility works the same way.

Neon suspends an idle compute, which would break a protocol that depended on
`LISTEN/NOTIFY`. This one does not: the triggers call `pg_notify` as a fast
path, but the event stream polls once a second and treats push as an
optimisation. Use Neon's **pooled** connection string for the services and the
**direct** one for migrations — PgBouncer's transaction mode cannot run the DDL
in `db/migrations` reliably.

### Why the API and the cycle are split

Sizing is measured, not guessed. A transformer fit peaks at **463 MiB** and
takes 28 s — small. But the full API image idles at **652 MiB** purely from
having imported torch, which does not fit a 512 MB instance.

It does not have to. The API answers questions about what the protocol *did*,
and every one of those answers is a database read; fitting models is the
cycle's job. So `docker/api.slim.Dockerfile` drops torch, scipy and
scikit-learn, and the same container serves every endpoint at **116 MiB**.

That split is verified rather than hoped. Every router and service in
`apps/api` imports clean of torch — checked, not assumed — and the one endpoint
that did not, `/api/market/training`, now reads the snapshot through
`ml.training.dataset`, which imports only numpy. If anything in the API ever
tries to fit a model it fails loudly on an `ImportError` rather than quietly
working in development and blowing the memory limit in production.

Two consequences of the split had to be fixed rather than tolerated, because
both made the product misreport itself:

- **A disabled poller is not an unhealthy feed.** `/api/market/health` asked
  whether *this process* was polling. On a sleeping free instance it never is,
  and the tape can still be perfectly fresh — so the check now reports on the
  data (lag, coverage) and only faults the poller when it is enabled and not
  running.
- **The snapshot has to be legible from another machine.** The cycle fits the
  models and holds the snapshot file; the API has never seen it. It would have
  answered "no training snapshot" and the §0c banner would have called real
  models synthetic. Migration 0006 records the snapshot's *identity* — not the
  series — in `training_snapshots`, so any process can report it honestly.

### What free costs you

A free deployment is a **dashboard over a protocol that runs elsewhere**. That
is a different split of the same work, not a lesser version of it — but three
things are genuinely worse and are worth knowing before you rely on it:

| | |
|---|---|
| the API sleeps after 15 min idle | first visit after a quiet spell takes about a minute |
| GitHub's scheduler is best-effort | cycles can run 15+ minutes late, or be skipped under load |
| no persistent disk | the cycle refits models every run (~28 s each) |

None of them corrupts the record. Settlement is driven by wall-clock horizons
rather than cycle count, so a late run settles exactly what an on-time run
would have; ingest is idempotent and its window is computed from the oldest
prediction still awaiting evidence, so a skipped run is repaired by the next.
The cost of missing a cycle is latency in the Arena, not a gap in the ledger.

To move the cycle back onto the same host: add a `type: cron` service on a paid
plan, switch to the full `docker/api.Dockerfile` on `plan: standard`, and set
`IRIS_FEED_ENABLED=true`.

Until the API is deployed, the site is honest about it rather than broken: with
no API to reach, the provenance notice renders **"Provenance unconfirmed"**
rather than claiming live data. That is the §0c rule doing its job in
production, and it is what you should see on the URL above right now.

### The protocol cycle

Agents do not run themselves. One command drives a full cycle in the
protocol's causal order:

```bash
make cycle    # ingest -> agents -> settle -> score -> risk -> allocate
```

Two properties make it safe to run unattended. It is **idempotent** — ingest
writes only the minutes it is missing, settlement only touches due predictions
— and **one failing step does not abort the rest**, because a venue outage
must not stop settlement of predictions that already have their evidence.
The exit code is non-zero if any step failed, so a scheduler can alert.

It is also **self-healing after an outage**. The ingest window is computed from
the oldest prediction still awaiting evidence rather than being a fixed
lookback, so predictions whose horizons closed while the host was down get
settled once it returns. A fixed window leaves them in `WAITING_FOR_OUTCOME`
permanently while the exchange has had the missing minutes all along — which is
exactly what happened here, and cost five real predictions until it was fixed.

### Secrets

`render.yaml` contains no credentials. Every secret is marked `sync: false` and
entered in the dashboard, and each one that is absent degrades its subsystem to
a labelled simulation path rather than failing the boot.

---

## On-chain (devnet)

Both Anchor programs are deployed and verified:

| program | id | size |
|---|---|---|
| `agent_registry` | [`6NTKNCtBnNAJjGfgFRNTPhbxBYz1GXv3mQRRdwdC2cNy`](https://explorer.solana.com/address/6NTKNCtBnNAJjGfgFRNTPhbxBYz1GXv3mQRRdwdC2cNy?cluster=devnet) | 350,896 bytes |
| `capital_vault` | [`HYxAvbCGmv7axJfQbbSxQXLyNiAhPQUyAsEo6nVUW1Gj`](https://explorer.solana.com/address/HYxAvbCGmv7axJfQbbSxQXLyNiAhPQUyAsEo6nVUW1Gj?cluster=devnet) | 374,360 bytes |

`declare_id!` and `Anchor.toml` are synced to those ids, so the source and the
chain agree. `scripts/verify_phase2.py` runs the 17 custody tests and then reads
both accounts back off-chain — it reports `DEPLOYED` from the chain rather than
from a build artifact.

```bash
make devnet-build     # Agave 4.2.2 + platform-tools v1.54
make devnet-deploy    # build, deploy, verify by reading the account back
make devnet-address   # the deployer address and its balance
```

> **The deploy keypairs live in the `iris-devnet-keys` Docker volume and nowhere
> else.** Losing that volume loses the upgrade authority: the programs stay on
> chain and become permanently unupgradeable at those ids. Back it up, and keep
> the archive **outside** the working tree:
>
> ```bash
> # Git Bash on Windows needs MSYS_NO_PATHCONV=1, or it rewrites /out into a
> # Windows path before Docker ever sees it.
> MSYS_NO_PATHCONV=1 docker run --rm \
>   -v iris-devnet-keys:/keys -v "$HOME/iris-secrets":/out \
>   alpine tar czf /out/iris-devnet-keys.tgz -C /keys .
> ```

---

## API surface

| route | what it answers |
|---|---|
| `GET /api/market/health` | is the feed alive, is its coverage usable, and **why not** |
| `GET /api/market/prices` | the recent tape for one asset, single-source |
| `GET /api/market/venues` | what each exchange says right now, and the spread |
| `GET /api/market/training` | what the models were actually fitted on |
| `GET /api/protocol/arena` | the leaderboard, ranked and **unranked** kept apart |
| `GET /api/protocol/observatory/runs` | node-by-node traces with their hash chain |
| `GET /api/protocol/ledger` | what was claimed, and what happened |
| `GET /api/events` · `WS /ws/events` | the protocol event stream |

Every response carries a `provenance` block naming the sources behind it. It is
a required field, not an optional one: a label that stops at the API boundary is
not a label.

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
├── agents/
│   ├── market/       exchange providers and the ingest pipeline
│   ├── graphs/       the LangGraph trading graph and its nodes
│   ├── evaluation/   prices, scoring, the settlement sweep
│   ├── reputation/   the six IRIS Score dimensions
│   ├── allocation/   multiplicative weights, and its four invariants
│   └── risk/         limits, breaches, freezing and slashing
├── ml/
│   ├── models/       the four model classes behind one interface
│   ├── training/     the frozen dataset snapshot and the fit budget
│   ├── features/     one feature vector, one order, shared by all models
│   └── inference/    the registry, the baseline comparison, artifact cache
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
| 1 | Repo, Docker, DB, skeleton | `docker compose up` → 200 on web, api, db — **passing** |
| 2 | AgentRegistry + CapitalVault | **agent cannot withdraw the vault** — passing; not deployed |
| 3 | Agent runtime + LangGraph | one agent completes the graph, checkpointed — **passing** |
| 4 | ML models + inference | 4 model classes, baseline comparison logged — **passing** |
| 5 | Prediction commit + evaluation | hash pre-horizon, settle post-horizon — **passing** |
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

- **No capital is deployed, and no model here has a demonstrated edge.** The
  prices are real; the trading is not. Allocation moves weights between agents,
  never funds, and the models are fitted on a few days of one-minute bars — a
  sample far too small to establish skill at anything. Read the Arena as a
  record of what these models claimed and what the market then did, not as a
  track record.

- **Predictions are only as good as their horizon.** Agents commit to a
  ten-minute view of BTC. One-minute returns have a standard deviation near
  three basis points, so the honest expectation is that most runs produce no
  view at all — and most do abstain. A cycle in which every agent trades would
  be evidence of a bug, not of skill.

- **The tape never mixes venues.** BTCUSDT on Binance, BTC-USD on Coinbase and
  XBTUSD on Kraken are three instruments a few basis points apart. Settlement
  pins both of its legs to one source *and* one venue, and refuses to measure
  across them — a return taken from two exchanges is the spread between them
  wearing an agent's name. `make market` prints the current gap.

- **Provenance is carried, not assumed.** Every observation records
  `market_events.source` and the venue that produced it; a settled prediction
  inherits the **weakest** provenance of its two price endpoints into
  `prediction_outcomes.data_source`; the API puts that on every response; and
  the three protocol screens render it server-side. If the feed stops, those
  screens say "simulated" or "unconfirmed" rather than continuing to claim
  live.
- **Governance is off-chain.** Proposals, votes and quorum resolve in a JSON
  store and an in-process singleton. The parameter change is real and
  immediate; the vote is not on-chain.
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
make test          # both suites: 105 in tests/, 61 in apps/api/tests/
make verify-all    # every phase gate, in order
make anchor-test   # the Solana programs, in a Linux container
```

Two test trees, deliberately. `tests/` is the §4 layout and covers the v2
runtime — the agent graph, the model layer, the settlement sweep, and the
schema invariants. `apps/api/tests/` covers the legacy pre-v2 API that is still
mounted. They are kept apart because `/app` is `apps/api` inside the container
while the §4 tree lives at the repo root; both are mounted, neither shadows the
other.

The gates are not a second copy of the tests. A gate asserts the phase's
Definition of Done against the *running stack* — it executes an agent, reads
the rows back out of Postgres, and fails if the trace is missing. Every gate so
far has caught at least one bug that the type checker and a green test run did
not; those are listed in `STATE.md`.

The testing matrix each phase must satisfy lives in the build prompt; a phase
does not checkpoint without its row passing.
