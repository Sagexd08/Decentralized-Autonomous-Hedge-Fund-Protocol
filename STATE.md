# IRIS Build State

> Per IRIS_BUILD_PROMPT v2.0 §0b. Every session starts by reading this file, not by
> re-reading the whole spec. Updated at every phase checkpoint.

## Current phase

**Phase 0 — scoping.** Blocked on one decision (see *Known blockers*). No v2 phase has
started; nothing below claims v2 conformance.

## Where the repo actually is today

The existing codebase predates v2.0 and does **not** match the v2 target architecture.
Recording the delta honestly rather than pretending Phase 1 is partly done:

| v2 target | Repo today | Delta |
|---|---|---|
| Solana only, no Stellar (§2) | Stellar Soroban **and** Solana, both deployed to testnet, both called every trading cycle | Spec deletes a working, deployed chain |
| `iris/apps/{web,api}` + `programs/` + `agents/` + `ml/` + `packages/` (§4) | `frontend/` + `backend/` + `contracts/` + `db/` | Full re-layout |
| LangGraph state machine per agent (§10) | `backend/agents/trading_engine.py` — asyncio loop, 3 hardcoded strategy archetypes | No graph, no checkpointer, no tool layer |
| LangChain tool surface (§10) | none | Not started |
| Neon Postgres + pgvector (§2, §12) | SQLAlchemy → Postgres w/ SQLite fallback, no vector store | No embeddings, no retrieval |
| 21 tables (§13) | 10 tables in `db/schema.sql` | Missing model_versions, predictions, prediction_outcomes, reputation_scores, agent_runs, graph_checkpoints, news_events, risk_events (partial), governance_* (partial) |
| Prediction commit → settle → evaluate (§5) | Agents submit `return_bps` directly; no prediction record, no pre-horizon hash | **The core Web3×ML primitive does not exist yet** |
| IRIS Score, ≥6 dimensions (§9) | Reputation decay helper only (`core/allocation.py`) | Not implemented |
| MWU allocation (§9) | Implemented and pushing weights on-chain | Closest thing to done; invariant tests missing |
| Risk engine, freeze → slash (§8) | Auto-slash on 20% drawdown, both chains | No freeze state, no VaR/CVaR gate in the loop |
| Governance on-chain (§21) | `governance_store.json` + in-process singleton | Off-chain despite the framing |
| 16 routes (§15) | 12 routes | Missing /arena, /predictions, /models, /model-cemetery, /observatory |
| Docker Compose (§24) | `docker-compose.yml` exists, unverified against §27 Phase 1 DoD | Untested |

## Done (this session, outside the phase loop)

- [x] **Brand assets.** Extracted transparent-background PNGs from the supplied lockup
      screenshot: `frontend/public/iris-mark.png` (95×95 aperture glyph),
      `iris-logo.png` (147×172 full stacked lockup), `iris-wordmark.png`.
      Source screenshot retained.
- [x] **Favicon** wired to `public/favicon.ico` in `app/layout.tsx` metadata, replacing
      the `icon-light/dark-32x32.png` + `icon.svg` set. Added OG image (`iris-logo.png`).
- [x] **Navbar logo** — `components/global-navbar.tsx` now leads with the aperture mark
      beside the IRIS / PROTOCOL text lockup.
- [x] **Vercel build unblocked** (commit `8ff62ae`) — `thread-stream` aliased to a stub so
      Turbopack stops widening it into a context module; `envDir` replaced with a real
      root-`.env` reader; `turbopack.root` pinned; lockfile resynced.

## Stubbed / SIMULATION-labeled

- **Price data is simulated.** `WS_MARKET_SOURCE` defaults to `simulated`; prices come from
  an Ornstein–Uhlenbeck engine over WBTC/USDC/LINK/UNI. All P&L, Sharpe and slashing run
  against synthetic tape. **Not currently labeled `SIMULATION` in the UI** — this violates
  v2 §0c and must be fixed in whichever phase touches those screens first.
- **Governance is off-chain** (`governance_store.json`). Parameter changes are real and
  immediate; the vote is not on-chain.
- **Algorand** — algod client, settings, deploy script and a `use-algorand` hook exist but
  are not in the trading loop. v2 drops it; decide whether to delete or park.

## Deferred

- Nothing yet — no phase has run.

## Known blockers

1. **Migration strategy is undecided, and it gates every phase.** v2 §2 says
   "single chain, no dual-chain abstraction, no Stellar", but four Soroban contracts are
   live on testnet and referenced throughout the README, the backend and the dashboard.
   Removing them destroys working deployed work. Options: rewrite in place, build the v2
   tree alongside the current app, or amend the spec to keep Stellar. Awaiting the call.
2. **Local `frontend/node_modules` is corrupt** — individual `.js` files missing from
   `@noble/hashes`, `ws`, `@scure/base`, `@heroicons/react` while their `.d.ts`/`.map`
   siblings survive. A clean reinstall hung at 352 packages. Vercel is unaffected (fresh
   container), but local `next build` cannot go green until this is repaired.

## Last verified commit

`8ff62ae` — fix(frontend): unblock Turbopack production build
