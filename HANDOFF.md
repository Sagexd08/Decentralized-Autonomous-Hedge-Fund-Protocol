# Handoff — 2026-09-23

Written for whoever (human or agent) picks this repo up next. Nothing in this
session was pushed or committed — see "Uncommitted work" below before doing
anything else.

## Where the build actually is

`STATE.md`'s "Last verified commit" line (`d02aa1b`) is stale — 14 commits
behind `main`. The real state, per `git log`:

- **Phases 1–13 are complete**, including the two Anchor programs live on
  devnet (`a87cde7`, `86eec6d`) and the protocol running on real market data
  end to end (`a87cde7`).
- Since Phase 13 closed, the work has been **deployment and honesty fixes**,
  not new phases: Render + Neon production deploy (`9786745`, `e11dcaa`,
  `c06508e`, `ff143a5`), Supabase removed (`58ddd94`), a build fix so
  `/observatory` prerenders (`d395e0f`), the API reachable from the deployed
  dashboard (`8870979`), and two §0c provenance-label bugs where the UI
  claimed live or real data over rows that weren't (`6189020`, `1bf0457`).
- **Phase 14 (simulation/backtesting replay harness) has not been started.**
  STATE.md's "Next phase" section describes it in detail — read that section,
  not this one, before starting it; it names the three known
  non-determinism sources (wall-clock timestamps, Torch's last-bit
  nondeterminism, devnet keypair regeneration) that a naive replay harness
  will trip on.
- Phases 14–16 (security hardening, full testing matrix, production polish)
  are open. See `BACKLOG.md` for the itemized list.

**Action item:** update STATE.md's "Last verified commit" line to `1bf0457`
next time it's touched, so the drift doesn't compound further.

## Uncommitted work in this session

Two files are modified, uncommitted, unpushed:

- `apps/web/app/world-monitor/page.tsx` — full rewrite
- `apps/web/components/global-navbar.tsx` — one-line nav label change

### What changed and why

The old `/world-monitor` page ("World Monitor") was **100% hardcoded mock
data** — fake Fed decisions, a fake globe, a fake "23/24 active agents"
counter — with no `fetch` anywhere in the file and no `ProvenanceBanner`.
That's a direct violation of this repo's own §0c rule (never render a number
without labelling where it came from), and it stuck out against every other
v2 screen (`Arena`, `Observatory`, `Ledger`), which are all real-data-only by
design.

It's been replaced with **"Agent Floor"** (nav label: "Floor", same route
`/world-monitor` — url intentionally kept stable): a live view of what
agents are actually doing, driven entirely by the existing `/ws/events`
protocol stream (Phase 9's outbox — every frame is a real row, nothing
invented). It shows:

- A lane per agent (from `fetchArena()`), with status, allocation weight, and
  IRIS score, pulsing when that agent has had activity in the last ~20s.
- A "recent crossings" strip — `ALLOCATION_UPDATED` events, i.e. capital
  literally moving between agents as the MWU rule reallocates weight. This is
  the honest version of "agents crossing" for this protocol: not a
  board-game metaphor, an actual allocation-engine event.
- A live scrolling ledger of every watched event kind (run started/succeeded/
  failed, node completed, prediction committed/settled/scored, reputation
  updated, allocation updated, risk breaches, slash/freeze/reinstate).
- The same `ProvenanceBadge`/`ProvenanceBanner` pattern Arena and Ledger use,
  so this page can't silently drift back into claiming real data it doesn't
  have.

Context on why: the user pointed at an unrelated GitHub repo
(`Station-Sciences/bot-crossing`) asking to "represent the agents working and
crossing." That repo turned out to be a 3D colony-sim dev tool that
visualizes *coding-agent CLI sessions* (Claude Code, Codex, etc.) as
astronauts — nothing to do with trading agents, signals, or capital
crossing. After confirming with the user, the decision was to build this
natively against IRIS's own agent/allocation data rather than adapt an
unrelated tool. Full reasoning is in the conversation transcript if needed.

### Known follow-ups on this specific change

- `components/visuals/animated-globe.tsx` is now dead code (only consumer was
  the old World Monitor page). Left in place rather than deleted — not this
  session's call to make unprompted.
- Not yet run against a live stack (`apps/web/node_modules` isn't installed
  in this environment, so `tsc` only surfaced module-resolution noise, not a
  real typecheck — see below). Before merging: `npm install && npm run dev`
  in `apps/web`, load `/world-monitor` against a running API, and confirm the
  event ledger actually populates against `make cycle` traffic.
- Not yet reviewed against `impeccable`/design-system conventions beyond the
  automated hook, which passed with no findings but explicitly does not mean
  the design is good.

### Typecheck note

`apps/web/node_modules` was empty in this environment (dependencies never
installed here), so `npx tsc --noEmit` reported `Cannot find module 'react'`
etc. across *every* file in the app, including files untouched by this
session (e.g. `app/agents/[id]/page.tsx`). Those are environmental, not
regressions. Run `npm install` first before trusting any future typecheck
output in this checkout.

## Next steps, in order

1. `npm install` in `apps/web`, then actually load `/world-monitor` against a
   running stack (`docker compose up -d --build`, `make feed && make train`,
   `make cycle`) and confirm the lanes and event ledger populate correctly.
2. Decide whether to commit the two files above, and update STATE.md's
   commit pointer while in there.
3. Pick up Phase 14 (replay harness) per STATE.md's "Next phase" section, or
   work `BACKLOG.md` top-down — see that file for the full itemized list
   from here to a shippable v1.
