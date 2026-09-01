"""
One full protocol cycle — the command production runs on a schedule.

Everything the protocol does was reachable before this, but only as six
separate commands, and `make cycle` ran five of them: feed, settle, score,
risk, allocate. It never ran the **agents**. Locally that was invisible because
a person runs `agents.runtime.runner` by hand when they want a prediction; in
production nobody does, so a deployed protocol would ingest prices, settle
nothing, and score an empty record forever.

So the order here is the protocol's actual causal order, and each step feeds
the next:

    ingest   real prices, so there is a market to observe and settle against
    run      every eligible agent, each committing or abstaining
    settle   predictions whose horizon has closed, against recorded prices
    score    the IRIS Score per agent, per provenance
    risk     breach -> freeze -> slash
    allocate one multiplicative-weights step over the new scores

Two properties matter for something that runs unattended:

**It is safe to run repeatedly.** Ingest is idempotent, settlement only touches
due predictions, and scoring appends. Running twice in a minute does no damage;
it just finds less to do the second time.

**One failing step does not abort the cycle.** A venue outage must not stop
settlement of predictions that already have their evidence, and a scoring bug
must not stop the risk engine from freezing an agent that is breaching. Each
step is isolated, its failure recorded and reported in the summary, and the
exit code says whether anything failed — so a scheduler can alert without the
protocol silently stopping.

    python -m agents.runtime.cycle
    python -m agents.runtime.cycle --assets BTC,ETH --no-ingest
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger("iris.cycle")

DEFAULT_ASSETS = ("BTC",)

# The floor on how much history to top up each cycle. Ingest is idempotent and
# writes only the minutes it is missing, so this is a ceiling on repair work
# rather than a per-run cost.
BACKFILL_MINUTES = 240

# ...and the ceiling, because the reach is computed from the data (see
# `_backfill_minutes`) and an unbounded window would ask an exchange for its
# entire history the first time a very old prediction turned up.
MAX_BACKFILL_MINUTES = 60 * 24 * 30


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""
    seconds: float = 0.0

    def line(self) -> str:
        mark = "ok " if self.ok else "FAIL"
        return f"  {mark}  {self.name:<10} {self.seconds:6.2f}s  {self.detail}"


@dataclass
class CycleResult:
    started_at: datetime
    steps: list[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)

    def as_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(),
            "ok": self.ok,
            "steps": [
                {"name": s.name, "ok": s.ok, "detail": s.detail,
                 "seconds": round(s.seconds, 3)}
                for s in self.steps
            ],
        }


def _step(result: CycleResult, name: str, fn: Callable[[], str]) -> None:
    """
    Run one step, and let the cycle survive it failing.

    Deliberately broad. The alternative — letting an exception propagate — means
    a single unreachable exchange stops predictions that already have their
    evidence from being settled, and stops the risk engine from acting on
    agents that are breaching right now. The failure is recorded, reported, and
    reflected in the exit code; it is not swallowed.
    """
    started = time.monotonic()
    try:
        detail = fn() or ""
        ok = True
    except Exception as exc:  # noqa: BLE001 - see docstring
        detail = f"{type(exc).__name__}: {exc}"
        ok = False
        logger.warning("cycle step %s failed: %s", name, detail)
        logger.debug("%s", traceback.format_exc())
    result.steps.append(
        StepResult(name=name, ok=ok, detail=detail,
                   seconds=time.monotonic() - started)
    )


def run_cycle(
    *,
    assets: tuple[str, ...] = DEFAULT_ASSETS,
    dsn: Optional[str] = None,
    ingest: bool = True,
    run_agents: bool = True,
    seed: int = 0,
) -> CycleResult:
    """Drive the protocol through one full cycle. Never raises."""
    from agents.allocation.allocator import allocatable_agents, allocate
    from agents.evaluation.prices import strongest_outcome_source
    from agents.evaluation.settlement import run_sweep as settle_sweep
    from agents.market.ingest import backfill
    from agents.reputation.score import score_all
    from agents.risk.engine import run_sweep as risk_sweep
    from agents.runtime import persistence
    from agents.runtime.runner import run_agent

    result = CycleResult(started_at=datetime.now(timezone.utc))

    # ── 1. the market ───────────────────────────────────────────────────────
    if ingest:
        def _ingest() -> str:
            written = []
            with persistence.connection(dsn) as conn:
                minutes = _backfill_minutes(conn, assets)
                for asset in assets:
                    report = backfill(conn, asset=asset, minutes=minutes)
                    if not report.ok:
                        raise RuntimeError(str(report))
                    written.append(f"{asset}+{report.written}")
            return f"{minutes}m window, " + " ".join(written)

        _step(result, "ingest", _ingest)

    # ── 2. the agents ───────────────────────────────────────────────────────
    #
    # Each agent runs in its own transaction inside `run_agent`, so one that
    # fails leaves the others' runs intact. An abstention is a normal outcome
    # and is counted, not treated as an error.
    if run_agents:
        def _run() -> str:
            with persistence.connection(dsn) as conn:
                agents = [
                    row[0]
                    for row in conn.execute(
                        """select a.id from agents a
                             join model_versions m on m.agent_id = a.id
                            where a.status in ('ACTIVE', 'PROBATION')
                            order by a.id"""
                    ).fetchall()
                ]

            committed = abstained = failed = 0
            for index, agent in enumerate(agents):
                try:
                    outcome = run_agent(
                        agent_id=agent,
                        asset=assets[index % len(assets)],
                        seed=seed + index,
                        dsn=dsn,
                        use_langgraph_checkpointer=False,
                    ).outcome
                except Exception as exc:  # noqa: BLE001 - one agent, not the run
                    logger.warning("agent %s failed: %s", agent, exc)
                    failed += 1
                    continue
                committed += int(outcome == "COMPLETED")
                abstained += int(outcome == "ABSTAINED")

            if agents and failed == len(agents):
                raise RuntimeError(f"every agent failed ({failed})")
            return (f"{len(agents)} agents: {committed} committed, "
                    f"{abstained} abstained, {failed} failed")

        _step(result, "agents", _run)

    # ── 3. measure, score, police, allocate ─────────────────────────────────
    def _settle() -> str:
        with persistence.connection(dsn) as conn:
            sweep = settle_sweep(conn)
        # `waiting` is reported alongside `settled` on purpose: the number of
        # predictions the protocol declines to score is as informative as the
        # number it does, and a cycle log that hid it would make a broken feed
        # look like a quiet market.
        return (f"scanned {sweep.scanned}, settled {len(sweep.settled)}, "
                f"waiting {len(sweep.waiting)}, scored {sweep.evaluated}")

    _step(result, "settle", _settle)

    def _score() -> str:
        with persistence.connection(dsn) as conn:
            source = strongest_outcome_source(conn)
            scores = score_all(conn, data_source=source, persist=True)
        return f"{len(scores)} scored on {source}"

    _step(result, "score", _score)

    def _risk() -> str:
        with persistence.connection(dsn) as conn:
            source = strongest_outcome_source(conn)
            sweep = risk_sweep(conn, data_source=source)
        return sweep.summary()

    _step(result, "risk", _risk)

    def _allocate() -> str:
        with persistence.connection(dsn) as conn:
            eligible = allocatable_agents(conn)
            if not eligible:
                return "no eligible agent"
            source = strongest_outcome_source(conn)
            step = allocate(conn, data_source=source, persist=True)
        return f"{len(eligible)} agents on {source}, step {getattr(step, 'step', '?')}"

    _step(result, "allocate", _allocate)

    return result


def _backfill_minutes(conn, assets: tuple[str, ...]) -> int:
    """
    Reach back far enough to settle whatever is still waiting.

    A fixed window makes the protocol permanently forgetful. Predictions
    committed while the host was down have horizons that close in the gap, and
    a four-hour top-up never reaches them — so they sit in
    WAITING_FOR_OUTCOME forever, correctly unscored, while the exchange has
    had the missing minutes the whole time.

    The window is therefore derived from the data: far enough back to cover the
    oldest prediction still awaiting evidence, with a floor so a quiet database
    still refreshes the recent tape and a ceiling so one very old row cannot
    ask a venue for its entire history.

    This is what makes an outage recoverable rather than permanent. It stays
    honest either way — settlement still refuses to invent a price, and the
    predictions it cannot cover stay unscored.
    """
    row = conn.execute(
        """select min(horizon_end) from predictions
            where status in ('COMMITTED', 'WAITING_FOR_OUTCOME')
              and asset = any(%s)""",
        (list(assets),),
    ).fetchone()

    oldest = row[0] if row else None
    if oldest is None:
        return BACKFILL_MINUTES

    # Plus a margin so the settlement tolerance has observations on both sides
    # of the horizon rather than exactly up to it.
    age = (datetime.now(timezone.utc) - oldest).total_seconds() / 60.0
    return int(min(MAX_BACKFILL_MINUTES, max(BACKFILL_MINUTES, age + 30)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one full protocol cycle.")
    parser.add_argument("--assets", default="BTC",
                        help="comma separated; agents are spread across them")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-ingest", action="store_true",
                        help="skip the feed; the API's poller may already run it")
    parser.add_argument("--no-agents", action="store_true",
                        help="settle and score only, without producing predictions")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dsn", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    )

    assets = tuple(a.strip().upper() for a in args.assets.split(",") if a.strip())
    result = run_cycle(
        assets=assets or DEFAULT_ASSETS,
        dsn=args.dsn,
        ingest=not args.no_ingest,
        run_agents=not args.no_agents,
        seed=args.seed,
    )

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(f"\nprotocol cycle — {result.started_at:%Y-%m-%d %H:%M:%S} UTC\n")
        for step in result.steps:
            print(step.line())
        total = sum(s.seconds for s in result.steps)
        print(f"\n{'complete' if result.ok else 'COMPLETED WITH FAILURES'} "
              f"in {total:.1f}s\n")

    # Non-zero when any step failed, so a scheduler can alert rather than the
    # protocol quietly stopping.
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
