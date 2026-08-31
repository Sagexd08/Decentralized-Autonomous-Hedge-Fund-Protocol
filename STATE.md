# IRIS Build State

> Per IRIS_BUILD_PROMPT v2.0 §0b. Every session starts by reading this file, not by
> re-reading the whole spec. Updated at every phase checkpoint.

## Current phase

**Phase 13 — real market data, end to end. COMPLETE.**
`python scripts/verify_phase13.py`.

The protocol no longer runs on a simulated tape. `market_events` holds real
one-minute bars and live ticks from a public exchange, labelled `LIVE` with the
venue that produced them; agents read that table; settlement measures against
it; the models are fitted on a frozen snapshot of it; and the three screens say
so in server-rendered HTML.

`make cycle` runs the whole loop: feed → settle → score → risk → allocate.
`make market` shows feed health and the cross-venue spread. `make train`
freezes a new training snapshot and refits. `make dataset` says what the models
are currently fitted on.

### The Phase 4 gate now fails, and it is right to

Re-pointed at the series the models are actually fitted on, and scored out of
sample, the honest comparison section 11 asks for returns:

| model | dominant class | trades | verdict |
|---|---|---|---|
| baseline | 39% | 1345 / 3009 | BASELINE |
| gradient_boosting | 98% HOLD | 50 | DEGENERATE |
| cnn_lstm | **100% HOLD** | 0 | DEGENERATE |
| transformer | 100% HOLD | 15 | DEGENERATE |

**Beating the baseline: none.** The last check — "at least one model genuinely
beats the baseline, or the ML layer is not earning its complexity" — fails.

This is left failing. It is not a plumbing bug: the models are fitted
correctly, on real data, at the right horizon, and scored out of sample. They
have learned that the most likely ten-minute outcome for BTC is "no move" and
they say so, which minimises their loss and makes them untradeable. The two
neural models are insensitive to their input — shown a tape trending
+50bps/minute the CNN-LSTM still predicts −0.91bps.

The previous PASS was earned on a synthetic tape that was predictable by
construction. Relaxing the check to recover it would be exactly the "fake
production readiness" §0c forbids, so the check stays and the result is
reported. **Getting a model to beat the baseline on real data is open research,
not a build step**, and it is the honest next question for this protocol —
which is, after all, what an autonomous intelligence market is supposed to
surface.

**§0c is satisfied in the UI**, and now in both directions: the notice reports
live, mixed, simulated or unconfirmed from what is actually true at request
time, rather than a hardcoded string. See *Stubbed / SIMULATION-labeled*.

**Phase 2 is COMPLETE.** Custody gate 17/17 and both programs live on devnet:

| program | id | size |
|---|---|---|
| `agent_registry` | `6NTKNCtBnNAJjGfgFRNTPhbxBYz1GXv3mQRRdwdC2cNy` | 350,896 bytes |
| `capital_vault` | `HYxAvbCGmv7axJfQbbSxQXLyNiAhPQUyAsEo6nVUW1Gj` | 374,360 bytes |

Both verified by reading the accounts back off-chain through the public RPC —
`executable: true`, owner `BPFLoaderUpgradeab1e...`, upgrade authority the
deployer we hold. `declare_id!` and `Anchor.toml` are synced to those ids, so
the source and the chain agree. Deployer `8t2C5qDCgw…` has 4.94 SOL left.

`.env` and `.env.example` now point at devnet and at these ids; they were
pointing at **testnet** and at two stale program ids that no longer correspond
to anything in this source.

### Phase 13 Definition of Done

| Requirement | Status |
|---|---|
| Prices come from a real venue | **verified** — 46k one-minute bars per asset from binance, plus a live poller inside the API |
| The agent observes what it is settled against | **verified** — `MARKET_OBSERVATION` reads `market_events`, the table settlement measures |
| One asset means one price series | **verified** — window and settlement pin to a single source *and* venue; a cross-venue settlement is refused |
| The models are fitted on the market they trade | **verified** — frozen snapshot, digest in the artifact cache key |
| The horizon trained is the horizon judged | **verified** — asserted by `tests/unit/test_training_contract.py` |
| The evidence cannot be rewritten | **verified** — a LIVE observation cannot be restated or deleted |
| The product says which of this is true | **verified** — provenance on every response, server-rendered notice on every screen |

### Phases 10-12 Definition of Done (§27)

| Screen | Requirement | Status |
|---|---|---|
| Agent Arena | driven by real rows | **verified** — every IRIS Score compared against `reputation_scores` |
| AI Observatory | driven by real rows | **verified** — 11 checkpoints per run, hash chain verified not asserted |
| Prediction Ledger | driven by real rows | **verified** — counts and scores compared against the tables |

The gate reads each number back out of the database rather than checking that
a page rendered. A screen backed by plausible constants looks identical to one
backed by the database until somebody does that comparison.

### Phase 9 Definition of Done (§27)

| Requirement | Status |
|---|---|
| real events from phases 3-8 | **verified** — 71 frames, every one traced to an existing row |
| reach a connected client | **verified** — client connects *first*, then the protocol runs |

The gate connects a real WebSocket client, then makes the protocol do things —
runs an agent, settles, scores, allocates, sweeps risk — and reads every frame's
`source_table`/`source_id` back out of the database. A phantom event fails it.

### Phase 8 Definition of Done (§27)

| Link | Status |
|---|---|
| breach | **verified** — recorded in `risk_events`, not just detected |
| → freeze | **verified** — status change *and* a FREEZE event, so it is explicable |
| → slash | **verified** — cites the breach, takes stake, writes the ledger |
| → reduced allocation | **verified** — weight 0.0897 → 0.0000, vault reallocated |

Checked as one causal chain on one agent, not four features in isolation. The
gate also checks the links that must **not** fire: a small sample cannot breach,
a single warning cannot freeze, a slash with no breach behind it is refused, a
slashed agent cannot be restored, and a frozen agent can still predict — which
is the only way it can earn its way back.

### Phase 7 Definition of Done (§27)

| Invariant | Status |
|---|---|
| 1. weights always sum to 1 | **verified** — worst deviation 2.2e-16 |
| 2. weights never negative or non-finite | **verified** |
| 3. a better score never loses weight to a worse one | **verified** |
| 4. the update is bounded — no weight reaches 0 or 1 | **verified** — range [0.005, 0.5] |

Checked as *properties over randomised inputs* — 1 to 150 agents, eta 0.01 to
5.0, chains up to 50 steps, and degenerate shapes (identical scores, all-zero
scores, one agent winning every round). Three of the four hold trivially on a
hand-picked example.

### Phase 6 Definition of Done (§27)

| Requirement | Status |
|---|---|
| IRIS Score from ≥6 dimensions | **verified** — accuracy, calibration, magnitude, consistency, risk_adjusted, conviction |
| configurable weights | **verified** — validated; missing / unknown / non-unit-sum / negative all rejected |
| unit-tested | **verified** — 34 unit + 11 database tests |

```
IRIS Score = 100 x (weighted quality) x evidence
```

`evidence` is a **multiplier, not a seventh dimension**, and the gate is what
forced that. See *Bugs found by the gates* 14.

### Phase 5 Definition of Done (§27)

| Requirement | Status |
|---|---|
| hash committed pre-horizon | **verified** — trigger rejects an outcome whose `settled_at < horizon_end` |
| settled post-horizon | **verified** — sweep selects on `horizon_end <= now()`, clamped to the real clock |
| error computed and stored | **verified** — `prediction_outcomes.error` |
| score computed and stored | **verified** — `prediction_outcomes.evaluation_score`, 0-100 |

Lifecycle: `COMMITTED → WAITING_FOR_OUTCOME → SETTLED → EVALUATED`, enforced
monotonic by trigger. `WAITING_FOR_OUTCOME` means *due but no price evidence* —
the state that keeps the sweep from inventing ground truth.

### Phase 4 Definition of Done (§27)

| Requirement | Status |
|---|---|
| 4 model classes via one interface | **verified** — baseline, GBDT, CNN-LSTM, transformer |
| baseline comparison logged | **verified** — printed with a per-model verdict |

Latest run: `gradient_boosting` 0.640 and `transformer` 0.623 beat the baseline's
0.422; `cnn_lstm` 0.408 **loses to it**, and is reported as losing.

### Phase 3 Definition of Done (§27)

| Requirement | Status |
|---|---|
| One agent completes the full graph end to end | **verified** — 11 nodes, §10 order |
| …on synthetic data | verified — seeded O-U tape, labelled SIMULATION |
| …checkpointed in Neon | **verified** — 11 `graph_checkpoints` rows + LangGraph `PostgresSaver` |

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

### Phase 4

- [x] `ml/` package per §4: `models/`, `features/`, `inference/`, `regime/`,
      `risk/`, `training/`. The legacy `apps/api/ml/` modules were merged in
      (monte_carlo → `risk/`, regime_classifier → `regime/`, hybrid_model →
      `models/hybrid_legacy.py`) rather than renamed away.
- [x] Four model classes behind one `BaseModel` protocol. `model_hash` is a
      real sha256 over parameters or trained weights (rounded to 6dp so float
      noise cannot forge a new identity), because invariant 3 and the on-chain
      `update_model` check depend on it.
- [x] Both torch models are real forward passes — conv+LSTM and a pre-norm
      encoder — reading two channels: returns and the z-scored price level.
- [x] `MODEL_INFERENCE` now runs real models, one per strategy, and records the
      model version in `inference_source`. Untrained models are labelled
      `(UNTRAINED)`; a model that fails to load makes the agent abstain rather
      than trade on a guess.
- [x] Evaluation leads with the direction confusion matrix, not MSE.

### Phase 13 — real market data

- [x] `agents/market/providers.py` — Binance, Coinbase and Kraken behind one
      interface. Public endpoints only: **no API keys anywhere**, which is the
      cheapest way to guarantee §0's no-credentials-in-source rule.
- [x] `agents/market/ingest.py` — backfill and stream, idempotent against a
      partial unique index, reporting failures rather than absorbing them.
      Never invents a tick: with every venue down it writes nothing, the
      prediction parks in WAITING_FOR_OUTCOME, and the gap in the record is
      the correct output.
- [x] `db/migrations/0005_market.sql` — a real observation is immutable and
      undeletable; a price must be a usable number; the same tick cannot land
      twice; claiming LIVE requires naming the venue.
- [x] `MARKET_OBSERVATION` reads `market_events` — the same table settlement
      measures. One series, both ends. The seeded tape survives as a labelled
      fallback.
- [x] `ml/training/dataset.py` — a **frozen** snapshot of real data, digest in
      the artifact cache key. Retraining is an explicit act, not a side effect
      of the clock ticking (invariant 3).
- [x] `ml/training/schedule.py` — training budgeted in gradient updates, not
      epochs. A transformer fit went from ~40 minutes back to 88s on the same
      10,080 samples, and the cost no longer grows with ingested history.
- [x] `apps/api/services/market_feed.py` — the live poller, inside the API.
- [x] `apps/api/api/market.py` — `/prices`, `/health`, `/venues`, `/training`,
      `/summary`. Health reports *reasons*, not a bare boolean.
- [x] `apps/web/components/iris/provenance-notice.tsx` — server-rendered, and
      it reports live / mixed / simulated / **unconfirmed** from what is
      actually true rather than a hardcoded string.
- [x] `scripts/verify_phase13.py` (32 checks) and 69 new tests.

### Phases 10-12

- [x] `apps/api/api/protocol.py` — `/api/protocol/{arena,observatory,ledger,risk,summary}`,
      reading the tables phases 5-8 write. **No fixture fallback anywhere in
      this path.**
- [x] `apps/web/app/{arena,observatory,ledger}/` — three screens on
      `lib/protocol.ts` and the Phase 9 socket, reloading on the events that
      actually changed something rather than on a timer.
- [x] **The Arena separates *unranked* from *last*.** An agent with no settled
      record has `iris_score: null`, and rendering it at the bottom of the same
      table would undo Phase 6's whole point — a reader scanning a leaderboard
      reads "last" as "worst".
- [x] **The Observatory verifies the hash chain** rather than displaying the
      nodes in order. `chain_intact` is computed from the rows; the gate
      tampers with a copy to prove the check is not hardcoded.
- [x] **The Ledger gives `WAITING_FOR_OUTCOME` its own treatment.** It is not
      "pending" — it is the protocol declining to score something it has no
      evidence for, and a spinner would hide the most honest thing it does.
- [x] `components/iris/simulation-notice.tsx` — a **server** component, so the
      §0c label is in the HTML before hydration, without JavaScript, and in the
      loading and error states. See *Bugs found by the gates* 24.
- [x] The legacy `/api/agents` fixture fallback is now labelled `FIXTURE` with
      a warning. See *Bugs found by the gates* 25.
- [x] `scripts/verify_phase10_12.py` (27 checks).

### Phase 9

- [x] `db/migrations/0004_events.sql` — an **outbox**. Triggers on the eight
      tables phases 3-8 write append to `protocol_events`, so the event *is* a
      row and the socket is only a reader. An event with no row behind it
      cannot be produced — not because the streaming code is careful, but
      because there is nowhere for it to come from.
- [x] One log rather than eight pollers, so `seq` is monotonic across every
      source: a prediction can never arrive before the run that produced it,
      and a reconnecting client resumes losslessly with `?since=`.
- [x] The log is **append-only** — it is what the Observatory renders and what
      a settled prediction is defended with.
- [x] `apps/api/services/event_stream.py` — one database tail feeding every
      client, with bounded per-subscriber queues. A client that stops reading is
      dropped rather than buffered forever; it reconnects with a watermark and
      loses nothing.
- [x] `apps/api/api/ws_events.py` — `/ws/events` with `agent`, `kinds`, `since`
      and `replay` filters, plus `/api/events` (same data over HTTP, so the
      socket is checkable) and `/api/events/health` (reports **lag**, because a
      stream that is up but stalled looks identical to a working one).
- [x] **Provenance never leaves the frame.** Every message carries
      `data_source`; a frame without it hands the UI a number it cannot qualify.
- [x] `python -m services.event_stream` / `make events`.
- [x] `scripts/verify_phase9.py` (12 checks) and 20 integration tests.

### Phase 8

- [x] `agents/risk/`: `limits.py` (six limits over a settled record) and
      `engine.py` (the chain).
- [x] `db/migrations/0003_risk.sql` — the chain made structural. A slash must
      cite a breach, that breach must belong to the same agent, a LIVE slash
      cannot rest on SIMULATION evidence, `slash_bps` cannot exceed the stake,
      and SLASHED → ACTIVE is rejected.
- [x] **Per-run and per-record breaches are different things.** `RISK_ANALYSIS`
      stops *this* trade; only a pattern across settled outcomes can freeze or
      slash. A single bad prediction is not misconduct.
- [x] **A sample floor.** Below 10 settled predictions nothing breaches —
      otherwise every agent is frozen for the variance every new agent has.
- [x] **HOLD earns nothing**, so an agent cannot manage its drawdown by
      abstaining.
- [x] **The slash scales with the excess, not the drawdown**, so the limit is
      not a cliff. Bounded at both ends: a slash that takes everything leaves
      no reason to keep operating honestly.
- [x] **Freezing is reversible, slashing is not.** A frozen agent keeps
      predicting — freezing removes its capital, not its voice — and is
      unfrozen by the same sweep once its record recovers.
- [x] `python -m agents.risk.engine` / `make risk`.
- [x] `scripts/verify_phase8.py` (25 checks), 21 unit tests, 21 database tests.

### Devnet (Phase 2, second half)

- [x] `docker/devnet.Dockerfile` — Agave **4.2.2**, platform-tools v1.54. The
      2.1.x line ships Rust 1.79 for the BPF target, too old for `edition2024`,
      which a transitive build-dependency of `spl-token` now requires.
- [x] `docker/devnet-deploy.sh` — generates persistent keypairs, syncs
      `declare_id!` and `Anchor.toml` to them, builds with `cargo build-sbf`,
      deploys, and **verifies by reading the account back off-chain** rather
      than trusting the exit code.
- [x] Both programs build: `agent_registry.so` 350,896 bytes,
      `capital_vault.so` 374,360 bytes.
- [x] `scripts/verify_phase2.py` now queries devnet directly and reports
      DEPLOYED / NOT DEPLOYED per program.
- [x] **Deployed to devnet and verified on chain.**
      `agent_registry` `6NTKNCtBnNAJjGfgFRNTPhbxBYz1GXv3mQRRdwdC2cNy`,
      `capital_vault` `HYxAvbCGmv7axJfQbbSxQXLyNiAhPQUyAsEo6nVUW1Gj`. Both read
      back through the public RPC as `executable`, owned by the upgradeable
      loader, with the upgrade authority we hold.
- [x] `.env` and `.env.example` repointed. They named **testnet** and two stale
      program ids belonging to nothing in this source, so the API was
      configured to talk to programs that do not correspond to these
      contracts.

### Phase 7

- [x] `agents/allocation/`: `mwu.py` (the update rule, the bounds, and
      `check_invariants`) and `allocator.py` (driving it from real reputation).
- [x] **Invariant 4 is not automatic** and is where the work is. A floor
      (0.005) because zero is *absorbing* under a multiplicative update — an
      agent that reaches it can never recover, which turns a bad month into an
      execution. A cap (0.40) because a single agent at weight 1 means the
      protocol *is* that agent, and its next mistake is the vault's.
- [x] The bounds are projected onto the simplex by **bisection on a single
      scale factor**, not by clamp-then-renormalise. See *Bugs found by the
      gates* 15 and 16.
- [x] **An unscored agent contributes no reward — absent, not zero.** Its
      weight is left untouched, so a quiet week is not punished as hard as a
      wrong one.
- [x] **FROZEN / SLASHED / RETIRED agents are excluded.** An allocator that
      ignored agent status would make Phase 8's risk engine advisory.
- [x] The score is already evidence-discounted (Phase 6), so the allocator
      applies no further sample-size correction — that would penalise a short
      record twice.
- [x] `allocation_history` stores the weight, the score and the `eta` in force;
      `UNIQUE (agent_id, step)` means a completed step cannot be rewritten. A
      corrected allocation is a new step.
- [x] `python -m agents.allocation.allocator` / `make allocate`, and
      `make cycle` for the full loop.
- [x] `scripts/verify_phase7.py` (17 checks), 34 unit tests, 18 database tests.

### Phase 6

- [x] `agents/reputation/`: `dimensions.py` (six pure functions on a settled
      record) and `score.py` (weighting, validation, persistence, CLI).
- [x] Six dimensions that each answer a question the others cannot — the gate
      proves it, by zeroing each weight in turn (none is inert) and comparing
      every pair across four records (no two are the same measurement).
- [x] **Weights are validated, not trusted.** A missing dimension is silently
      weighted 0; an unknown one is silently ignored; weights that do not sum
      to 1 shift every score by a constant factor and leave the leaderboard
      looking plausible. All four cases raise.
- [x] **An untested agent has no score.** `None`, not 0 and not 50. A default
      would let an agent that has never been tested outrank one with a proven
      bad record — and Phase 7 allocates capital by that ranking. The
      leaderboard lists them as unranked rather than last.
- [x] **Records are never aggregated across provenance.** Scoring is per
      `data_source`, so a simulated track record cannot be presented as live
      performance (§0c).
- [x] **Only settled, scored outcomes count.** `WAITING_FOR_OUTCOME` and
      measured-but-unscored rows are excluded, so an agent cannot dilute a bad
      record by predicting on assets with no price feed.
- [x] `reputation_scores` is append-only, and every row carries the weights,
      the evidence factor, the sample size and the provenance — so a score is
      re-derivable from its own row after the weighting changes.
- [x] `python -m agents.reputation.score` / `make score`.
- [x] `scripts/verify_phase6.py` (22 checks), 34 unit tests, 11 database tests.

### Phase 5

- [x] `agents/evaluation/`: `prices.py` (the reference price, and the refusal to
      invent one), `scoring.py` (the 0-100 rule), `settlement.py` (the sweep).
- [x] `db/migrations/0002_settlement.sql` — **invariant 2 enforced by the
      database, not by convention.** Triggers reject: rewriting any field of a
      committed claim, deleting a committed prediction, moving the lifecycle
      backwards, restating a measured outcome, and writing an outcome before
      its horizon closes. A `prediction_hash` that is UNIQUE but mutable
      protects nothing — the bytes it names can be edited underneath it.
- [x] `prediction_outcomes.data_source` — an outcome inherits the *weakest*
      provenance of its two price endpoints, so a return measured from one live
      and one simulated price is not reported as a live result (§0c).
- [x] Two passes, deliberately. Measurement is a fact about the market; scoring
      is a policy about what that fact is worth. `evaluation_score` is nullable
      so Phase 6 can re-score without re-measuring.
- [x] Scoring: direction 0.60, magnitude 0.40, confidence as a two-way
      multiplier. **Being confidently wrong scores below being hedged and
      wrong** — otherwise a model rewarded only for correctness learns to be
      confident always, and §12's calibration dimension measures nothing.
- [x] `python -m agents.evaluation.prices` — the simulated feed, gap-filling
      and idempotent. `python -m agents.evaluation.settlement` — the sweep,
      with `--dry-run` and a backfill-only `--as-of`.
- [x] `scripts/verify_phase5.py` (17 checks) and 38 tests in
      `tests/integration/test_settlement.py`.

### Phase 3

- [x] `agents/` package per §4: `state.py`, `graphs/{nodes,trading_graph}.py`,
      `runtime/{persistence,runner}.py`.
- [x] All 11 §10 nodes as typed functions over a Pydantic `AgentState`; single
      conditional branch at VALIDATION (commit vs abstain).
- [x] **The hard boundary holds.** RISK_ANALYSIS and VALIDATION are
      deterministic, and a test reads their source and fails if an LLM or
      network call ever appears in either.
- [x] PREDICTION_COMMIT hashes a canonical payload (sorted keys, fixed float
      formatting) and stamps `committed_at < horizon_end`. Tested for
      stability, and that changing *any* of 7 fields changes the digest.
- [x] Two checkpointing layers, both in Postgres: LangGraph's `PostgresSaver`
      (for resuming a run) and our `graph_checkpoints` (the audit trail the
      Observatory reads). Each checkpoint's `input_hash` equals the previous
      node's `output_hash`, so the trail is a chain rather than 11 snapshots.
- [x] Abstention recorded as `ABSTAINED`, not `FAILED` — declining because risk
      objected is the system working.
- [x] `scripts/verify_phase3.py` (12 checks) and 18 integration tests.

### Outside the phase loop

- [x] Brand assets extracted from the supplied lockup screenshot →
      `apps/web/public/iris-{mark,logo,wordmark}.png`; favicon wired to
      `favicon.ico`; navbar leads with the mark. (`b28e012`)
- [x] Vercel Turbopack build unblocked. (`8ff62ae`)

## Stubbed / SIMULATION-labeled

- ~~**Price data is simulated.**~~ **Closed in Phase 13.** `market_events`
  holds real one-minute bars and live ticks from a public exchange under the
  `LIVE` label, with the venue recorded on every row. The provenance chain the
  simulated tape needed is unchanged and now carries a real label:
  `market_events.source` → `prediction_outcomes.data_source` → the API's
  `provenance` block → a server-rendered notice on every protocol screen.
  The pre-v2 dashboard pages still show unlabelled numbers.
- **The synthetic tape survives as a fallback, not a default.** With no usable
  feed, `MARKET_OBSERVATION` falls back to the seeded Ornstein-Uhlenbeck window
  and says so in `observation_note` and `data_source`; `make feed-sim` still
  writes one. A graph that cannot run at all is a worse failure than a graph
  running on data it says is synthetic.
- **Governance is off-chain** (`governance_store.json` + in-process singleton).
- ~~**Prediction primitive is schema-only.**~~ **Closed in Phase 5.** The
  runtime commits, the sweep settles and scores, and the ordering is enforced
  by triggers rather than by the code that happens to call them.
- ~~**Models train on a synthetic series.**~~ **Closed in Phase 13.** They are
  fitted on a frozen snapshot of real exchange data (`make dataset`), whose
  digest is part of the artifact cache key. `synthetic_series` remains as the
  fallback when no snapshot exists, and `/api/market/training` reports which is
  in force — including a loud warning when it is the synthetic one, because
  live prices behind a synthetically trained model is the combination that
  looks best from the outside and is worst.
- **No model has a demonstrated edge, and the record is short.** Days of
  one-minute bars is nowhere near enough to establish skill. The Arena is a
  record of what was claimed and what the market did, not a track record.
- **No capital moves.** Allocation adjusts weights; it does not transfer funds.
  Phase 2's custody separation is unchanged.
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
4. ~~`tests/test_agent_trading_engine.py` is stale~~ — **fixed in Phase 5.**
   Rewritten against the engine that exists. See *Bugs found by the gates* 13.
5. **The 4-month-old `pgdata` volume was destroyed.** It had to be: Postgres
   saw an existing data directory, skipped initialisation entirely, and the
   volume contained neither an `iris` nor a `postgres` role — an aborted init
   from 2026-04-04 that no credential could read. Nothing was recoverable.
   Stale `hacktropica-frontend`/`-backend` images (1.5 GB + 8.6 GB) remain and
   can be pruned.

6. ~~**Nothing is deployed to devnet.**~~ **Cleared.** Both programs are live
   and verified on chain; `verify_phase2.py` reports DEPLOYED. The deployer
   `8t2C5qDCgwJr3arDbdYnf6AjaEYCoa1h42qcysdXL7bo` holds 4.94 SOL, enough for a
   redeploy of both.

   The keypairs live in the `iris-devnet-keys` Docker volume and nowhere else.
   **Losing that volume loses the upgrade authority** — the programs stay on
   chain and become permanently unupgradeable at those ids. Back it up before
   relying on it:

       docker run --rm -v iris-devnet-keys:/keys -v "$PWD":/out alpine          tar czf /out/iris-devnet-keys.tgz -C /keys .

   Keep that archive out of the repo. It is the upgrade authority for both
   programs and §0 forbids keys in source.

## Local edit outside the repo

`.env` lines 53–58 were pasted CLI output (`Deployer balance OK: …`,
`Algorand deploy failed: …`), which is not valid dotenv and made
`docker compose config` fail. They are now commented out; all values preserved.

## Bugs found by the gates (not written by them)

### Found deploying to devnet

41. **The balance guard had never once run.** It compared with
    `(( $(echo "$have < $MIN_SOL" | bc -l) ))`, and `bc` is not in the devnet
    image. Both comparisons errored to false, so the deploy proceeded
    regardless of balance — the guard added specifically to stop a half-funded
    run from stranding its lamports in an orphaned buffer was inert. It only
    ever looked fine because the balance happened to be sufficient the one time
    it mattered. Now compared in lamports as integers, with no external tool.

42. **The orphaned-buffer reclamation never found a buffer.**
    `solana program show --buffers --output json` answers
    `{"buffers": [...]}`, not a bare array, so `.[]?.bufferAddress` raised
    "Cannot index array with string" on every run. The other half of the same
    guard, also silently doing nothing.

43. **`.env` pointed at testnet and at two dead program ids.** The API was
    configured to talk to `F4s8zTom…` and `4AdNiFej…`, which correspond to
    nothing in this source, on a cluster the programs were never deployed to.
    Deploying is only half of "it works on devnet"; the client has to be
    pointed at what was deployed.

### Found in Phase 13

27. **Every model predicted moves ~60x too large on real prices.** The models
    were fitted on a tape whose one-step returns have a standard deviation near
    60bps; real one-minute BTC is nearer 3.4. The first live run produced
    BUY +0.83% over ten minutes on a tape with 10bps of realised volatility —
    a 2.6-sigma call at 88% confidence, and it would have made one every run.
    Nothing crashed, the hash was honest, the settlement was honest, and the
    number meant nothing.

28. **The models were trained for a one-minute horizon and judged on ten.**
    `build_dataset` defaulted to `horizon=1` while DECISION commits to 600
    seconds against a feed that ticks once a minute. Settlement then measured a
    ten-minute move against a one-minute forecast and recorded the difference
    as the agent's error. Invisible on the synthetic tape, because its returns
    were large enough that a one-step prediction happened to land in the same
    range as a ten-step real move — two wrong scales cancelling.

29. **The decision threshold was a constant tuned to a market that does not
    exist.** A flat 5bps bar was reasonable against 60bps synthetic returns and
    became a 1.4-sigma bar on real BTC, which no model could clear. It now
    scales with observed volatility, with a floor tied to
    `scoring.HOLD_BAND` so the gate and the grader cannot drift apart.

30. **`price_at` could measure across two price universes.** It took the
    nearest observation regardless of source. With a synthetic tape near 100
    and an exchange near 77,000 covering the same instant, a settlement landing
    on different sides of that reports a return of roughly 77,000% — which
    flows straight into an IRIS Score, a risk breach and a slash. Source now
    outranks proximity, and settlement pins its exit leg to the entry leg's
    source *and* venue. The plausible version is worse: two exchanges a few
    basis points apart produce a believable return that is really the spread
    between two instruments wearing an agent's name.

31. **Postgres defines `NaN = NaN` as TRUE.** The price-validation trigger used
    the idiomatic `value <> value` to catch NaN, which therefore never fired.
    `{"price": "NaN"}` is valid JSON, Postgres casts the string to a real NaN
    without complaint, and it would have propagated through every average
    computed over it into a reputation score. Caught by a test that asked.

32. **A candle stamped at its open is wrong by exactly one bar.** Every venue
    keys a one-minute bar by the minute it opened, so filing the close price
    under that timestamp puts every observation sixty seconds early, in the
    same direction, forever. Binance additionally reports its close as
    `openTime + 59_999ms`, one millisecond short of the boundary — enough for
    the same minute to land on a different key than another venue's and defeat
    the deduplication index.

33. **`make warm` warmed models nobody uses.** It fitted seed 0; model identity
    is per agent (invariant 3), so every agent's first run still fitted its own
    from cold. Tolerable at ninety seconds a fit and the dominant cost once the
    training set was real. Now `warm_agents()` reads the registry and fits what
    the registered agents actually use.

34. **Full-batch training made cost grow with ingested history.** 300 passes
    over the whole set is fine on 600 samples and takes ~40 minutes for a
    transformer on 10,080 — per agent. Now budgeted in gradient updates.
    Fixing that introduced its own bug immediately: spending the full budget on
    a 200-sample set overfitted so hard that the spread head, trained against
    |residual|, reported an error bar 64x smaller than the target scale, which
    would have made every prediction look near-certain. Small sets keep the
    schedule they were validated on.

35. **The Phase 4 evaluation graded fitted models in-sample.** It scored on the
    whole series after fitting on the first 70%, while the baseline — which
    fits nothing — was graded on all of it throughout. The comparison Phase 4
    exists to make is only meaningful if both sides sit the same exam, and the
    in-sample advantage flattered exactly the models whose value is in
    question. It also ran on a synthetic tape it generated itself, making its
    verdicts statements about a market that does not exist.

36. **Reputation, risk and allocation kept reading the empty bucket.** All
    three are computed per provenance and never across it — correctly. Their
    CLIs defaulted to SIMULATION, which was right while that was the only
    bucket and became a silent bug the moment predictions settled against a
    real market: the outcomes were LIVE, the scorers were reading SIMULATION,
    and every agent with a real record reported as "no settled predictions".

37. **Three test suites assumed a database nothing real had ever touched.**
    Tests asserting `data_source="LIVE"` returns nothing, and absolute outcome
    counts, passed only until the protocol settled its first real prediction.
    Rewritten to scope to their own fixtures or to use a genuinely empty
    provenance.

38. **The §0c notice hardcoded "Simulated data".** Correct for twelve phases
    and a lie the moment the feed became real. A stale honesty label is worse
    than none, because it is the thing a reader trusts to tell them when to
    stop trusting. It now reports live / mixed / simulated / unconfirmed from
    what is true at request time — and an unreachable API renders
    *unconfirmed*, never *live*.

39. **The server-side fetch fell back to the browser's API URL.**
    `NEXT_PUBLIC_API_URL` is `http://localhost:8000`, which inside the web
    container means the web container. Every server-side provenance fetch
    failed and the page rendered "unconfirmed" over a perfectly healthy stack.

40. **Two phase gates pinned which agent commits.** Both had already been wrong
    once when Phase 4 wired real models in; Phase 13 moved the answer again.
    Each time the gate reported "the graph cannot complete" when the truth was
    "a different agent completes it now". Both now search.


-2. **Double normalisation in the sequence models.** `build_dataset` returned
   pre-normalised return windows, which `predict()` then normalised *again* —
   differencing values already near zero. Predicted returns came out at ~3600
   (360,000%) while every type check passed. `build_dataset` now returns raw
   price windows and `fit()` normalises exactly as `predict()` does.
-1. **The evaluation called a degenerate model a winner.** A transformer
   predicting BUY for 100% of samples, MSE 1.96e+11, was reported as BEATS
   BASELINE on accuracy alone. The verdict now disqualifies a model that
   answers one class ≥90% of the time, or whose MSE is >10x the baseline's,
   *before* accuracy is consulted. Also fixed the underlying divergence
   (standardised targets, gradient clipping, cosine schedule).
0. **`apps/api/agents/` collided with the new `agents/` package** and shadowed
   it, crashing the API on boot. Four of its five modules (price_engine,
   market_stream, crypto_news, gemini_social) are data services, not agents, so
   it was renamed `apps/api/services/`. `trading_engine.py` moved with them and
   is the legacy runtime the graph replaces — remove it once the graph drives
   allocation.
1. **`AgentList` was unallocatable.** `#[max_len(5000)]` on `Vec<Pubkey>` asks
   for ~160KB, but the runtime caps a program-created account at 10,240 bytes.
   `initialize` failed with `InvalidRealloc` — on devnet exactly as in the
   harness, so the registry could never have been initialised as written.
   Capped at 300 (ceiling is 319). Growing past that needs a different shape,
   not a bigger number.
2. **Migrations never ran** (Phase 1) — a stale `pgdata` volume.
3. **torch pulled the CUDA wheel** (Phase 1) — 8.63GB → 3.24GB.

### Found in Phase 5

4. **No agent had committed a prediction since Phase 4.** Phase 4 wired real
   models into `MODEL_INFERENCE`, but built them *untrained* on every run. An
   untrained network's confidence is arbitrary; every one sat below the 0.55
   validation floor, so every agent abstained, always. The graph ran perfectly
   and traded nothing. Phase 3's gate caught it because it asserts a *commit*,
   not just a traversal — nothing type-checked wrong and nothing crashed.
   Fixed by `ml/inference/artifacts.py`: trained models, cached on disk
   (37.5s cold → 0.21s warm).

5. **Model identity moved with the run.** `all_models(seed=state.seed)` seeded
   the model from the *market tape's* seed, so the same agent produced a
   different `model_hash` on every invocation — precisely the version history
   invariant 3 forbids. The seed now derives from the agent id.

6. **`confidence` was the probability of a different class.** It was
   `max(proba)` — the likeliest class — while `direction` came from
   thresholding the predicted return. A model proposing BUY could report the
   probability it had assigned to HOLD, and the validation floor gated on that
   number. Now `confidence_for(direction, proba)`.

7. **The HOLD logit was a magic 0.35**, which pinned `max(proba)` near 0.415
   whenever the predicted move was small. Confidence was not comparable across
   models, so a shared floor was meaningless, and **no CNN-LSTM agent could
   ever clear it** — that strategy structurally could not trade. Both are now
   derived from quantities the model has: its own error spread, and the size of
   a move worth trading.

8. **The agent was writing the evidence it would be judged on.** *(Mine.)* To
   give settlement an entry price, `persist_prediction` wrote `state.prices[-1]`
   into `market_events`. But `market_observation` generates a private tape
   seeded from the run, unrelated to the shared feed — every agent wrote the
   identical `98.372476`, and settlement measured the disagreement between two
   price universes as a +2.6% return. The narrow bug was the mismatched series;
   the reason it stays removed is structural: an agent that records its own
   entry price is grading its own exam.

9. **The feed refused to extend a tape whose tail was missing.** A coverage
   check ("does this range already have observations?") counted the agents'
   sparse entry prices as a tape and wrote nothing — leaving exactly the tail
   gap where open predictions' horizons land. Replaced with gap-filling, which
   is also idempotent; duplicate ticks make `price_at` pick arbitrarily and
   settlement stop being reproducible.

10. **`--as-of` could ask for an early settlement.** A future timestamp would
    select predictions whose horizon had not closed; the database would reject
    the outcome and abort the sweep. `now` is now clamped to the real clock, so
    the flag can only look backwards — settling early is impossible rather than
    merely refused.

11. **The deposit endpoint reported `confirmed` for a simulated transaction.**
    When the Solana call failed, `tx_hash` fell back to `"0xsimulated..."` and
    the response still said `confirmed` — the dashboard would have shown a
    confirmed on-chain deposit that never happened (§0c). Status is now
    `confirmed` only with a real signature, and the response carries
    `persisted` so a memory-only fallback is distinguishable.

12. **The web container was unhealthy for hours while serving 200s.** The
    healthcheck used `wget http://localhost:3000`, which resolves to `::1`
    first; `next dev --hostname 0.0.0.0` binds IPv4 only. Now `127.0.0.1`.

### Found in Phases 10-12

24. **The §0c label depended on a successful fetch.** The provenance banner
    rendered only once data arrived, so it was absent from the server HTML,
    absent with JavaScript disabled, and absent in the loading and error states
    — which is exactly where a reader forms their first impression. Section 0c
    says label simulated data *in the UI*; a label that needs a round trip is a
    label on the happy path. Now a server component in a route layout.

25. **A database outage rendered as a working dashboard.** `/api/agents` caught
    every exception with `except Exception: pass` and fell back to nine
    hardcoded agents with invented Sharpe ratios, indistinguishable from real
    rows. The query migration in Phase 1 fixed the queries and left the
    fallback. It now logs the failure and labels every row `FIXTURE` with a
    warning; the v2 screens use `/api/protocol/*`, which has no fixture path.

26. **The web container had no live mount.** Three finished routes returned 404
    because the container serves the baked image and `apps/web` was never
    mounted, unlike `apps/api`. A new page needed a full rebuild to exist.

### Found in Phase 8

17. **The uncertainty head was never trained.** Both torch models compute
    `pred, _ = self.net(xb)` in the fit loop — the `spread` head was outside
    the loss entirely and received no gradient, so it reported its random
    initialisation forever. Confidence is `expected_return / spread`, so **every
    confidence those models ever produced was an arbitrary constant.** Its
    magnitude looked plausible only because `_target_scale` multiplies it.
    Now trained against the detached absolute residual — detached, so widening
    its error bars cannot become a way to reduce the prediction loss.

18. **CNN-LSTM was under-trained, not weak.** 60 epochs at a fixed learning
    rate against the transformer's 300 on a cosine schedule. The transformer
    was given the longer schedule when it hit the flat-HOLD basin; the same fix
    was never applied here. Mean |prediction| was 0.00086 against a target
    scale of 0.0048 — it was predicting the mean. With a matched budget it went
    0.408 → 0.508 and now **beats** the baseline. That is a fix to training,
    not a moved goalpost: the degeneracy and MSE disqualifiers are untouched.

19. **Leftover fudge factors in the tabular models.** Gradient boosting used
    `_residual_scale * 2.0` and the baseline `volatility * 4.0` — tuning
    constants from the old formulation, where snr fed a softmax against a
    hardcoded 0.35 HOLD logit. Under the current one, where spread appears in
    *both* the snr and the HOLD logit, a multiplier does not calibrate
    anything; it makes the model uniformly less certain. This left every
    `mean_reversion` agent unable to clear the 0.55 floor.

    Together, 17–19 are why **two of four strategies could not trade at all**.
    Each looked like "that model is just weak".

20. **The branch tests were pinned to lucky seeds.** Which seeds commit depends
    on the trained models, so a hardcoded seed silently becomes a test of "did
    the models change" rather than "is this branch reachable". Broken twice
    that way. They now search a seed range, and there are new tests asserting
    every strategy can both commit and abstain.

21. **A schema test depended on an empty table.** `test_one_allocation_row_per_agent_per_step`
    hardcoded step 0 and started failing the moment Phase 7's allocator wrote a
    real step 0 — a false failure for the best possible reason.

22. **The SBF toolchain was two major versions stale.** Agave 2.1.21 ships Rust
    1.79 for the BPF target; a transitive build-dependency of `spl-token` now
    requires `edition2024`. Pinning the dependency fights the resolver through
    four levels of the graph. Bumped to 4.2.2 / platform-tools v1.54.

23. **The first deploy stranded its own funds.** `MIN_SOL` was 3; each program
    costs ~2.45 SOL, so it failed partway through the first and left a write
    buffer holding the lamports needed to finish — making every retry poorer
    than the attempt that failed. The script now reclaims orphaned buffers
    before deploying and checks the balance before each program, not once.

### Found in Phase 7

15. **The floor and cap were jointly infeasible.** Two agents cannot both hold
    at most 0.40 and still sum to 1; one agent must hold exactly 1. The gate
    caught it by running the invariants over 1, 2, 3, 8, 40 and 150 agents —
    on a hand-picked eight-agent example nothing looks wrong. `_bounds(n)` now
    relaxes the policy to what is achievable, so `n*lo <= 1 <= n*hi` always
    holds and the projection is always solvable.

16. **Clamp-then-renormalise put weights back through the bound.**
    Renormalising *after* clamping scales the clamped values too — the gate saw
    0.0044 against a floor of 0.005. Replaced with bisection on a single scale
    factor: find theta with `sum(clamp(w_i*theta, lo, hi)) = 1`. Provably
    correct, and it preserves invariant 3 for free, because clamping a
    uniformly-scaled value is monotone.

### Found in Phase 6

14. **A single lucky prediction scored 79.2 out of 100.** `experience` was one
    of seven weighted dimensions at 0.10 — but every *other* dimension maxes
    out on a sample of one, and a 10% weight cannot pull that down. Phase 7
    allocates capital by this ranking, so that agent would have been handed the
    vault on one call. Evidence now **multiplies** the weighted quality instead
    of being averaged into it: a weight small enough to be fair to a long
    record is far too small to discount a short one. Same record now scores
    4.2 at n=1 and 84.9 at n=200. `conviction` took the freed dimension slot.

### Found in Phase 5 (continued)

13. **Two test files asserted the behaviour of deleted code.**
    `test_agent_trading_engine.py` constructed the engine with Ethereum-era
    parameters and monkeypatched four methods the Solana migration removed —
    `monkeypatch.setattr` was failing on missing attributes, not on anything
    the engine did. `test_agent_gemini_social.py` patched `_call_gemini`, renamed
    `_call_llm` when the service moved to Groq. Both rewritten against the code
    that exists.

## Next phase

**Phase 13 — simulation + backtesting.** DoD: the same seed produces the same
result.

Most of the pieces are already seeded and reproducible, and were built that way
deliberately: `market_observation` seeds its tape from the run,
`ml.inference.artifacts.training_series` is a fixed seeded series,
`agents.evaluation.prices.simulated_tape` is seeded, and model artifacts are
cached by a contract key that changes when any training input does.

What does not yet exist is the thing that makes those facts checkable: a
**replay harness** that runs a whole scenario end to end — feed, agents,
settlement, scoring, risk, allocation — twice from one seed and asserts the two
runs agree. That is a stronger claim than "each generator is seeded", because
the places reproducibility actually breaks are the joins: wall-clock timestamps,
dict ordering, a float summed in a different order, `now()` reaching the
database.

Three known non-determinisms to deal with rather than paper over:

  * **Wall-clock time.** `committed_at`, `settled_at` and `computed_at` all come
    from the real clock. A replay needs a virtual clock, or the comparison has
    to exclude timestamps — and excluding them silently would let a genuine
    ordering bug pass.
  * **Torch.** Seeded, but CPU thread count and library version affect the last
    bits. The comparison should be on the decisions and scores, not on raw
    weights.
  * **The devnet keypairs** are generated once and reused; a replay must not
    regenerate them.

Then Phases 14-16: security hardening, the testing matrix, production polish.
Phase 16's demo-mode gate wants a cold boot under 60 seconds, which the 3.2 GB
API image will not hit without a slimming pass — and `make warm` currently
takes ~40 seconds on a cold cache before an agent can trade at all.

`agent_performance` is still empty — nothing computes windowed pnl / sharpe /
sortino.

`REGIME_ANALYSIS` still uses threshold stand-ins; the HMM classifier in
`ml/regime/classifier.py` is merged but not wired into the graph.

## Last verified commit

`d02aa1b` — feat(phase-9): the protocol event stream, where the event is a row

Phases 10-12 are committed on top of it.
