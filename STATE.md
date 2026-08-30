# IRIS Build State

> Per IRIS_BUILD_PROMPT v2.0 §0b. Every session starts by reading this file, not by
> re-reading the whole spec. Updated at every phase checkpoint.

## Current phase

**Phase 5 — prediction commitment + evaluation. COMPLETE and checkpointed.**
`python scripts/verify_phase5.py` → 17/17.

All five gates pass: `make verify-all`. Both test suites pass:
**105** in the §4 root tree (`/repo/tests`) and **61** in the legacy
`apps/api/tests`.

Phase 2's security gate passed (17/17) but the phase is **not fully
checkpointed** — its DoD also says the instructions work "on devnet" and
nothing is deployed. See *Known blockers* 6.

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

- **Price data is simulated** (`WS_MARKET_SOURCE=simulated`, Ornstein–Uhlenbeck
  engine). Not yet labeled in the UI — **violates §0c**, must be fixed by
  whichever phase next touches those screens.
- **Governance is off-chain** (`governance_store.json` + in-process singleton).
- ~~**Prediction primitive is schema-only.**~~ **Closed in Phase 5.** The
  runtime commits, the sweep settles and scores, and the ordering is enforced
  by triggers rather than by the code that happens to call them.
- **The market is simulated and says so.** `python -m agents.evaluation.prices`
  writes an Ornstein-Uhlenbeck tape stamped `SIMULATION`, and that label rides
  through settlement into `prediction_outcomes.data_source`. A real feed
  replaces the writer; nothing else changes.
- **Models train on a synthetic series.** `ml/inference/artifacts.training_series`
  — seeded, reproducible, and not evidence of live performance.
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

13. **Two test files asserted the behaviour of deleted code.**
    `test_agent_trading_engine.py` constructed the engine with Ethereum-era
    parameters and monkeypatched four methods the Solana migration removed —
    `monkeypatch.setattr` was failing on missing attributes, not on anything
    the engine did. `test_agent_gemini_social.py` patched `_call_gemini`, renamed
    `_call_llm` when the service moved to Groq. Both rewritten against the code
    that exists.

## Next phase

**Phase 6 — reputation engine.** DoD: an IRIS Score computed from at least six
dimensions with configurable weights.

Phase 5 leaves the inputs in place. `prediction_outcomes` now carries
`direction_correct`, `error` and `evaluation_score` per prediction, and
`reputation_scores` already stores `dimensions` *and* `weights` as JSONB so a
historical score can be re-derived after a weighting change — which is the
whole reason the schema keeps them side by side.

Two things Phase 6 must not do, both of which Phase 5 made easy to get wrong:

  * **Score across provenance.** An agent with 40 SIMULATION outcomes and 2 LIVE
    ones does not have a reputation. `data_source` is on every outcome; the
    aggregate has to respect it or the IRIS Score becomes a number about a
    simulation wearing a live label.
  * **Count unsettled predictions.** `WAITING_FOR_OUTCOME` exists precisely so
    that predictions with no evidence stay out of every reputation number.
    Including them as neutral would let an agent dilute a bad record by
    predicting on assets with no feed.

`agent_performance` is still empty — nothing computes windowed pnl/sharpe/
sortino yet, and four of the six dimensions will come from there.

`REGIME_ANALYSIS` still uses threshold stand-ins; the HMM classifier in
`ml/regime/classifier.py` is merged but not wired into the graph.

## Last verified commit

`9391565` — feat(phase-4): four model classes, one interface, an honest baseline

Phase 5 is committed on top of it.
