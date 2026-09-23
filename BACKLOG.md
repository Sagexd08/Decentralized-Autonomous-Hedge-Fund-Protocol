# Backlog — path to a shippable v1

Compiled 2026-09-23 from `STATE.md`, `README.md`'s Build phases and
Limitations sections, and a direct check of the repo against both (some
claims in those two files have already drifted from what's on disk — noted
inline below). This is the end-to-end list, in rough priority order within
each phase. Check items off as they land and fold the detail back into
`STATE.md` at each phase checkpoint, per this repo's own convention.

Nothing here has been started as new work in this session — see
`HANDOFF.md` for the one UI change that was made (`/world-monitor` → "Agent
Floor").

---

## Phase 14 — Simulation + backtesting (not started)

DoD: same seed → same result, for a full scenario run end to end (feed →
agents → settlement → scoring → risk → allocation), asserted by a replay
harness, not just per-component seeding.

- [ ] Build the replay harness itself — run a scenario twice from one seed,
      assert agreement. STATE.md is explicit that per-generator seeding
      already exists (`market_observation`, `training_series`,
      `simulated_tape`, cached model artifacts) but nothing yet proves the
      *joins* between them are deterministic.
- [ ] Virtual clock for `committed_at` / `settled_at` / `computed_at`, or an
      explicit, justified exclusion of timestamps from the comparison —
      excluding them silently would hide a real ordering bug.
- [ ] Pin/verify Torch determinism at the decision/score level (not raw
      weights) — CPU thread count and library version affect the last bits
      of raw weights even when seeded.
- [ ] Ensure devnet keypairs are reused, never regenerated, across a replay.
- [ ] `make verify13` or equivalent gate wired into `make verify-all`.

## Phase 15 — Security hardening (not started)

- [ ] Finish Anchor program consolidation. **Currently half-done**: STATE.md
      Phase 2 marks this `[x]` complete, but only `agent_registry` and
      `capital_vault` actually live under `programs/iris/programs/`;
      `allocation_engine` and `slashing_module` are still only in the old
      standalone workspaces under `contracts/rust/solana/`. Move those two,
      then delete the standalone workspaces so there's one copy of the
      Solana programs, not two.
- [ ] The "agent cannot withdraw the vault" security test — README lists
      this as the test that matters most for Phase 2/consolidation and it's
      not confirmed to exist against the consolidated workspace.
- [ ] `make anchor-test` green in CI, not just locally in the Linux
      container.
- [ ] Full security checklist from the v2.0 build prompt (section reference
      lives in the prompt itself, not duplicated here — read it fresh rather
      than trust a summary, since summaries are exactly what's drifted stale
      elsewhere in this repo).
- [ ] Review the deploy surface added post-Phase-13 (Render + Neon,
      `9786745`..`ff143a5`) against the same checklist — it didn't exist when
      Phase 2's security work was scoped.

## Phase 16 — Testing matrix + production polish (not started)

- [ ] Full testing matrix from the build prompt, green, per phase row —
      README says "a phase does not checkpoint without its row passing";
      confirm all rows for phases 1-13 are actually still green after the
      deploy-era commits, not just at the time each phase originally closed.
- [ ] Cold boot under 60 seconds for the demo-mode gate. STATE.md flags the
      3.2 GB API image and ~40s `make warm` on a cold cache as the current
      blocker — needs an image-slimming pass.
- [ ] Full §25 README rewrite (Mermaid diagrams, security model, testnet
      deploy docs) — explicitly deferred to Phase 16 in STATE.md's Deferred
      section.
- [ ] `make test` — both suites (105 in `tests/`, 61 in `apps/api/tests/`) —
      confirmed green post-deploy-era changes.
- [ ] `make verify-all` — every phase gate, in order — confirmed green
      end-to-end in one run, not phase-by-phase in isolation.

## Known gaps not tied to a specific numbered phase

- [ ] `agent_performance` table is empty — nothing computes windowed
      pnl / sharpe / sortino. Referenced in STATE.md as an open item with no
      owning phase assigned yet.
- [ ] `REGIME_ANALYSIS` still uses threshold stand-ins. The HMM classifier in
      `ml/regime/classifier.py` is merged but not wired into the agent graph.
- [ ] Algorand vestiges (client, settings, a frontend hook) — README says
      "slated for removal," not yet removed. Not on the trading critical
      path, but it's dead weight and a source of confusion for anyone new to
      the repo.
- [ ] Solidity contracts under `contracts/src/` are explicitly a reference
      implementation only — confirm nothing in docs or nav implies otherwise
      before shipping, since they're not deployed and not on any critical
      path.
- [ ] Governance is off-chain (JSON store + in-process singleton) — README
      states this plainly as a limitation. No phase currently owns moving it
      on-chain; decide if that's actually in scope for v1 or a stated,
      permanent limitation.
- [ ] STATE.md's "Last verified commit" pointer is stale as of this writing
      (`d02aa1b`, 14 commits behind `main` at `1bf0457`). Not a feature gap,
      but it's the file every session is supposed to trust first per §0b, so
      letting it drift further compounds confusion for the next person (or
      agent) who reads it before the code.

## The honest research question, left open on purpose

README and STATE.md both say this directly and it's worth carrying into any
"what's left to ship" list rather than treating it as done: **no model here
has a demonstrated edge over baseline on real data.** The Phase 4 gate
currently fails and is *supposed to* — every fitted model (gradient boosting,
CNN-LSTM, transformer) either abstains almost entirely or is insensitive to
its input on the real BTC one-minute series, versus a baseline that trades on
39% of windows. This is not a build task with a defined DoD; it's open
research. Whether "v1 ships with no model beating baseline, honestly labelled"
is an acceptable launch state, or whether ML work has to close this gap
first, is a product decision, not an engineering one — flag it explicitly
before any "ready to ship" conversation, rather than let it get silently
swept into a phase checklist it doesn't belong on.

---

## Front-end specific (found via this session's `/world-monitor` work)

- [ ] `components/visuals/animated-globe.tsx` is now dead code — its only
      consumer (the old World Monitor page) was replaced. Confirm nothing
      else needs it, then delete.
- [ ] Audit other pre-v2 dashboard routes (`app/dashboard`,
      `app/allocation-engine`, `app/intelligence`, `app/analytics`,
      `app/governance`, `app/contracts`, `app/pnl-history`, `app/risk-pools`,
      `app/health`) for the same hardcoded-mock-data pattern the old World
      Monitor had. The nav comment in `global-navbar.tsx` already flags
      Arena/Floor/Observatory/Ledger as "the ones driven entirely by real
      rows" and everything else as "the pre-v2 dashboard [that] still reads
      from the legacy API" — worth confirming "legacy API" means real-but-old
      data, not literal fixtures, on each of those routes individually before
      shipping.
