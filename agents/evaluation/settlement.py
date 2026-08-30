"""
The settlement sweep — Phase 5.

Phase 3 built the commit half of the commit-before-outcome primitive: a hash
written before the horizon, with the database enforcing that ordering. This is
the other half. It reads predictions whose horizon has closed, measures what
actually happened, and writes an outcome the prediction row cannot argue with.

The lifecycle, and why each state earns its place:

    COMMITTED            hash written, horizon still open
    WAITING_FOR_OUTCOME  horizon closed, but the price evidence is missing
    SETTLED              measured: actual return, error, direction correctness
    EVALUATED            scored

WAITING_FOR_OUTCOME is the state that matters most and is the easiest to omit.
Without it, "due but unsettleable" collapses into "not due yet", and the
pressure to settle *something* falls on the sweep — which is how ground truth
gets interpolated into existence. Here a prediction with no price evidence
parks in a named state and stays out of every reputation number until real data
arrives. Nothing downstream mistakes it for a result.

Settlement and scoring are two passes over the same row because they answer
different questions. Measurement is a fact about the market; scoring is a
policy about how much that fact is worth. `evaluation_score` is nullable
precisely so the two can be told apart, and so a change to the scoring policy
in Phase 6 can be re-run without re-measuring anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import psycopg

from agents.evaluation.prices import (
    DEFAULT_TOLERANCE,
    price_at,
    realised_return,
    utcnow,
)
from agents.evaluation.scoring import Score, score_prediction

# Statuses a prediction can be settled from. PREDICTED is excluded on purpose:
# an uncommitted draft has made no claim to judge.
SETTLEABLE = ("COMMITTED", "WAITING_FOR_OUTCOME")


@dataclass(frozen=True)
class Settlement:
    """One prediction's measurement. Written, not returned as an opinion."""

    prediction_id: str
    agent_id: str
    asset: str
    direction: str
    expected_return: float
    actual_return: float
    error: float
    direction_correct: bool
    entry_price: float
    exit_price: float
    data_source: str
    settled_at: datetime


@dataclass(frozen=True)
class SweepResult:
    """What one sweep did, in terms a human can check against the database."""

    settled: list[Settlement]
    waiting: list[str]     # due, but no price evidence — deliberately unsettled
    evaluated: int
    scanned: int

    def summary(self) -> str:
        return (
            f"scanned {self.scanned} due, settled {len(self.settled)}, "
            f"waiting {len(self.waiting)}, scored {self.evaluated}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Pass 1 — measure
# ─────────────────────────────────────────────────────────────────────────────

def due_predictions(
    conn: psycopg.Connection, *, now: Optional[datetime] = None, limit: int = 500
) -> list[tuple]:
    """
    Predictions whose horizon has closed and which carry no outcome yet.

    `now` is a parameter rather than a call to now() inside the query so a test
    can drive the sweep at a chosen instant without waiting out a real horizon.

    It is clamped to the real clock, so it can only ever look *backwards*. A
    future `now` would select predictions whose horizon has not actually closed
    yet; the database would then reject the outcome (its `settled_at` comes
    from the real clock and would precede `horizon_end`) and take the whole
    sweep down with it. Clamping makes the parameter mean "backfill up to
    here", which is the only use it has, and makes settling early structurally
    impossible rather than merely refused.
    """
    now = min(now, utcnow()) if now else utcnow()
    return conn.execute(
        """
        select p.id, p.agent_id, p.asset, p.direction, p.expected_return,
               p.confidence, p.committed_at, p.horizon_end, p.status
          from predictions p
     left join prediction_outcomes o on o.prediction_id = p.id
         where p.status = any(%s)
           and p.horizon_end <= %s
           and o.prediction_id is null
      order by p.horizon_end
         limit %s
        """,
        (list(SETTLEABLE), now, limit),
    ).fetchall()


def settle_one(
    conn: psycopg.Connection,
    row: tuple,
    *,
    tolerance: timedelta = DEFAULT_TOLERANCE,
) -> Optional[Settlement]:
    """
    Measure one due prediction, or mark it as waiting and return None.

    Returning None is a real outcome of this function, not an error path. It
    means the evidence isn't there, and the correct response is to record that
    and move on — never to estimate.
    """
    (pid, agent_id, asset, direction, expected_return,
     _confidence, committed_at, horizon_end, _status) = row

    entry = price_at(conn, asset=asset, at=committed_at, tolerance=tolerance)
    exit_ = price_at(conn, asset=asset, at=horizon_end, tolerance=tolerance)

    if entry is None or exit_ is None:
        conn.execute(
            "update predictions set status = 'WAITING_FOR_OUTCOME' "
            " where id = %s and status = 'COMMITTED'",
            (pid,),
        )
        return None

    actual = realised_return(entry.price, exit_.price)
    expected = float(expected_return)

    # Scored here rather than in pass 2 because `direction_correct` is a
    # measurement — it depends only on the market — while `evaluation_score` is
    # a policy. The split is the point of having two passes.
    measurement = score_prediction(
        direction=direction,
        expected_return=expected,
        confidence=0.0,          # confidence weighting belongs to scoring, not measurement
        actual_return=actual,
    )

    # An outcome inherits the weakest provenance of its two endpoints: a return
    # measured from one live and one simulated price is not a live result.
    data_source = _weakest(entry.source, exit_.source)
    settled_at = utcnow()

    conn.execute(
        """
        insert into prediction_outcomes
            (prediction_id, actual_return, error, direction_correct,
             evaluation_score, settled_at, data_source)
        values (%s, %s, %s, %s, NULL, %s, %s)
        """,
        (pid, actual, measurement.error, measurement.direction_correct,
         settled_at, data_source),
    )
    conn.execute("update predictions set status = 'SETTLED' where id = %s", (pid,))

    return Settlement(
        prediction_id=str(pid),
        agent_id=agent_id,
        asset=asset,
        direction=direction,
        expected_return=expected,
        actual_return=actual,
        error=measurement.error,
        direction_correct=measurement.direction_correct,
        entry_price=entry.price,
        exit_price=exit_.price,
        data_source=data_source,
        settled_at=settled_at,
    )


_PROVENANCE_ORDER = {"SIMULATION": 0, "TESTNET": 1, "LIVE": 2}


def _weakest(*sources: str) -> str:
    """The least trustworthy label wins — a chain is as honest as its weakest link."""
    return min(sources, key=lambda s: _PROVENANCE_ORDER.get(s, 0))


# ─────────────────────────────────────────────────────────────────────────────
# Pass 2 — score
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_settled(conn: psycopg.Connection, *, limit: int = 500) -> int:
    """
    Score every settled-but-unscored outcome. Returns how many were scored.

    Re-runnable: it selects on `evaluation_score is null`, so a failed sweep
    leaves measured-but-unscored rows that the next run picks up, rather than a
    half-written batch that needs manual repair.
    """
    rows = conn.execute(
        """
        select o.prediction_id, p.direction, p.expected_return, p.confidence,
               o.actual_return
          from prediction_outcomes o
          join predictions p on p.id = o.prediction_id
         where o.evaluation_score is null
         limit %s
        """,
        (limit,),
    ).fetchall()

    for pid, direction, expected_return, confidence, actual_return in rows:
        score: Score = score_prediction(
            direction=direction,
            expected_return=float(expected_return),
            confidence=float(confidence),
            actual_return=float(actual_return),
        )
        conn.execute(
            "update prediction_outcomes set evaluation_score = %s where prediction_id = %s",
            (round(score.value, 5), pid),
        )
        conn.execute(
            "update predictions set status = 'EVALUATED' where id = %s", (pid,)
        )

    return len(rows)


# ─────────────────────────────────────────────────────────────────────────────
# The sweep
# ─────────────────────────────────────────────────────────────────────────────

def run_sweep(
    conn: psycopg.Connection,
    *,
    now: Optional[datetime] = None,
    tolerance: timedelta = DEFAULT_TOLERANCE,
    limit: int = 500,
) -> SweepResult:
    """Measure everything due, then score everything measured."""
    rows = due_predictions(conn, now=now, limit=limit)

    settled: list[Settlement] = []
    waiting: list[str] = []
    for row in rows:
        outcome = settle_one(conn, row, tolerance=tolerance)
        if outcome is None:
            waiting.append(str(row[0]))
        else:
            settled.append(outcome)

    evaluated = evaluate_settled(conn, limit=limit)
    return SweepResult(
        settled=settled, waiting=waiting, evaluated=evaluated, scanned=len(rows)
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """
    Run one sweep against the live database.

    Prints what it settled *and* what it refused to settle. The waiting list is
    not a warning to be tidied away — it is the set of predictions the system
    is declining to score because it has no evidence, and it belongs in the
    output next to the results rather than in a log nobody reads.

        python -m agents.evaluation.settlement
    """
    import argparse

    from agents.runtime.persistence import connection

    parser = argparse.ArgumentParser(description="Settle and score due predictions.")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what is due without writing anything")
    parser.add_argument(
        "--as-of", default=None,
        help=(
            "treat this ISO timestamp as now when selecting what is due. For "
            "backfilling a gap in the sweep, not for settling early: "
            "`settled_at` still comes from the real clock, and the database "
            "rejects any outcome whose settled_at precedes its horizon_end."
        ),
    )
    args = parser.parse_args(argv)

    as_of = datetime.fromisoformat(args.as_of) if args.as_of else None

    with connection() as conn:
        if args.dry_run:
            rows = due_predictions(conn, now=as_of, limit=args.limit)
            print(f"{len(rows)} prediction(s) due for settlement")
            for r in rows:
                print(f"  {r[0]}  {r[1]:<14} {r[2]:<8} {r[3]:<5} horizon ended {r[7]}")
            conn.rollback()
            return 0

        result = run_sweep(conn, now=as_of, limit=args.limit)

    print(result.summary())
    for s in result.settled:
        mark = "correct" if s.direction_correct else "wrong  "
        print(
            f"  {s.agent_id:<14} {s.asset:<8} {s.direction:<5} {mark} "
            f"actual {s.actual_return:+.4%} error {s.error:.5f}  [{s.data_source}]"
        )
    if result.waiting:
        print(f"\n  {len(result.waiting)} left unsettled — no price evidence at the "
              f"horizon. They are NOT scored and count toward nothing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
