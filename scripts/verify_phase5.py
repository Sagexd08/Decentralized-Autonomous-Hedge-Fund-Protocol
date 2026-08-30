#!/usr/bin/env python
"""
Phase 5 gate — IRIS_BUILD_PROMPT v2.0 section 27.

DoD: "Hash committed pre-horizon, settled post-horizon, error and score
computed and stored."

The DoD is a sequence, so the gate checks the sequence rather than the
endpoints. Several checks exist because the characteristic failure of a
settlement system is not a crash — it is producing a number anyway:

  * settlement must be *refused* when the price evidence is missing;
  * a committed claim must be un-rewritable, enforced by the database;
  * an outcome must be un-writable before the horizon it judges;
  * the lifecycle must not run backwards.

A gate that only asserted "an outcome row appeared" would pass on a system that
invented every number in it.

The whole run happens inside one transaction that is rolled back at the end, so
the gate is repeatable and leaves no rows behind.

    python scripts/verify_phase5.py
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The gate needs psycopg and the DSN. On a developer machine neither is
# necessarily present, but the api container has both — so re-exec there rather
# than making the gate's runnability depend on a local virtualenv.
try:
    import psycopg
except ModuleNotFoundError:  # pragma: no cover - host path
    import subprocess

    print("psycopg not available here; running the gate inside the api container.",
          flush=True)
    raise SystemExit(
        subprocess.run(
            ["docker", "compose", "exec", "-T", "api",
             "python", "/repo/scripts/verify_phase5.py"],
        ).returncode
    )

from agents.evaluation.prices import (  # noqa: E402
    price_at,
    record_price,
    seed_simulated_prices,
)
from agents.evaluation.scoring import score_prediction  # noqa: E402
from agents.evaluation.settlement import due_predictions, run_sweep  # noqa: E402

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
results: list[tuple[bool, str, str]] = []

AGENT = "AGT-AXIOM"
ASSET = "PH5"


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label, detail))
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  {mark}  {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))


def rejects(conn, sql: str, params: tuple) -> bool:
    """
    Run a statement that must be refused. True when the database refused it.

    Wrapped in a savepoint so a legitimate rejection doesn't abort the
    surrounding transaction and take every later check with it.
    """
    conn.execute("savepoint probe")
    try:
        conn.execute(sql, params)
    except psycopg.errors.IntegrityConstraintViolation:
        conn.execute("rollback to savepoint probe")
        return True
    conn.execute("rollback to savepoint probe")
    return False


def model_version(conn) -> str:
    row = conn.execute(
        "select id from model_versions where agent_id = %s order by version desc limit 1",
        (AGENT,),
    ).fetchone()
    if row is None:
        raise SystemExit(
            f"no model_versions row for {AGENT} — run `make db-seed` first."
        )
    return str(row[0])


def commit_prediction(
    conn,
    *,
    direction: str,
    expected_return: float,
    confidence: float,
    committed_at: datetime,
    horizon_seconds: int,
    asset: str = ASSET,
) -> str:
    """Write a COMMITTED prediction the way the runtime does."""
    pid = str(uuid.uuid4())
    conn.execute(
        """
        insert into predictions
            (id, agent_id, model_version_id, asset, direction, expected_return,
             confidence, horizon_seconds, prediction_hash, status,
             predicted_at, committed_at, horizon_end)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'COMMITTED', %s, %s, %s)
        """,
        (
            pid, AGENT, model_version(conn), asset, direction, expected_return,
            confidence, horizon_seconds,
            uuid.uuid4().hex + uuid.uuid4().hex[:32],
            committed_at, committed_at,
            committed_at + timedelta(seconds=horizon_seconds),
        ),
    )
    return pid


def lifecycle(conn, now: datetime) -> None:
    """The happy path, end to end: commit -> due -> settled -> evaluated."""
    t0 = now - timedelta(hours=2)
    horizon = 1800
    t1 = t0 + timedelta(seconds=horizon)

    seed_simulated_prices(
        conn, asset=ASSET, start=t0 - timedelta(minutes=5),
        end=t1 + timedelta(minutes=5), step=timedelta(minutes=1), seed=7,
    )
    entry = price_at(conn, asset=ASSET, at=t0)
    exit_ = price_at(conn, asset=ASSET, at=t1)
    true_return = (exit_.price - entry.price) / entry.price

    # Call the direction the tape actually took, so the happy path is a correct
    # prediction and can be told apart from the wrong-call case below.
    called = (
        "BUY" if true_return > 0.0005
        else "SELL" if true_return < -0.0005
        else "HOLD"
    )
    pid = commit_prediction(
        conn, direction=called, expected_return=true_return * 0.8,
        confidence=0.72, committed_at=t0, horizon_seconds=horizon,
    )

    due = due_predictions(conn, now=now)
    check(any(str(r[0]) == pid for r in due),
          "a prediction past its horizon is picked up as due", f"{len(due)} due")

    result = run_sweep(conn, now=now)
    check(len(result.settled) >= 1 and result.evaluated >= 1,
          "the sweep settles and scores in one pass", result.summary())

    status, actual, error, correct, score, settled_at, source, horizon_end = conn.execute(
        """
        select p.status, o.actual_return, o.error, o.direction_correct,
               o.evaluation_score, o.settled_at, o.data_source, p.horizon_end
          from predictions p join prediction_outcomes o on o.prediction_id = p.id
         where p.id = %s
        """,
        (pid,),
    ).fetchone()

    check(status == "EVALUATED", "the prediction reaches EVALUATED", status)
    check(abs(float(actual) - true_return) < 1e-6,
          "the actual return is measured from the recorded tape",
          f"{float(actual):+.6f} vs {true_return:+.6f}")
    check(error is not None and score is not None,
          "error and score are both stored",
          f"error {float(error):.6f}, score {float(score):.2f}")
    check(bool(correct), "a correct call is recorded as correct", called)
    check(settled_at >= horizon_end,
          "settlement happens strictly after the horizon closes",
          f"{settled_at:%H:%M:%S} >= {horizon_end:%H:%M:%S}")
    check(source == "SIMULATION",
          "the outcome is labelled with the provenance of its evidence", source)

    # Invariant 2 — the claim is frozen once committed.
    check(rejects(conn, "update predictions set expected_return = 0.99 where id = %s", (pid,)),
          "a committed claim cannot be rewritten (invariant 2)",
          "database rejected the UPDATE")
    check(rejects(conn, "delete from predictions where id = %s", (pid,)),
          "a committed prediction cannot be deleted",
          "database rejected the DELETE")
    check(rejects(conn,
                  "update prediction_outcomes set actual_return = 0.5 where prediction_id = %s",
                  (pid,)),
          "a measured outcome cannot be restated",
          "database rejected the UPDATE")


def refuses_to_invent(conn, now: datetime) -> None:
    """A prediction with no price evidence must park, not settle."""
    t0 = now - timedelta(hours=2)
    horizon = 1800
    t1 = t0 + timedelta(seconds=horizon)

    blind = commit_prediction(
        conn, direction="BUY", expected_return=0.01, confidence=0.9,
        committed_at=t0, horizon_seconds=horizon, asset="PH5-NODATA",
    )
    result = run_sweep(conn, now=now)
    status = conn.execute(
        "select status from predictions where id = %s", (blind,)
    ).fetchone()[0]
    outcomes = conn.execute(
        "select count(*) from prediction_outcomes where prediction_id = %s", (blind,)
    ).fetchone()[0]

    check(status == "WAITING_FOR_OUTCOME" and outcomes == 0 and blind in result.waiting,
          "a prediction with no price evidence is NOT settled",
          f"status {status}, outcomes {outcomes}")

    record_price(conn, asset="PH5-NODATA", price=100.0, at=t0)
    record_price(conn, asset="PH5-NODATA", price=103.0, at=t1)
    run_sweep(conn, now=now)
    row = conn.execute(
        """select p.status, o.actual_return from predictions p
             join prediction_outcomes o on o.prediction_id = p.id where p.id = %s""",
        (blind,),
    ).fetchone()
    check(row is not None and row[0] == "EVALUATED" and abs(float(row[1]) - 0.03) < 1e-9,
          "a waiting prediction settles once the evidence arrives",
          f"{row[0]} at {float(row[1]):+.4f}" if row else "never settled")


def ordering(conn, now: datetime) -> None:
    """Commit-before-outcome, and a lifecycle that only runs forwards."""
    early = commit_prediction(
        conn, direction="BUY", expected_return=0.01, confidence=0.5,
        committed_at=now, horizon_seconds=3600, asset="PH5-EARLY",
    )
    check(
        rejects(
            conn,
            """insert into prediction_outcomes
                   (prediction_id, actual_return, error, direction_correct, settled_at)
               values (%s, 0.01, 0.0, true, %s)""",
            (early, now + timedelta(seconds=60)),
        ),
        "an outcome cannot be written before its horizon closes",
        "database rejected the INSERT",
    )

    back = commit_prediction(
        conn, direction="BUY", expected_return=0.01, confidence=0.5,
        committed_at=now - timedelta(hours=1), horizon_seconds=60, asset="PH5-BACK",
    )
    conn.execute("update predictions set status = 'SETTLED' where id = %s", (back,))
    check(rejects(conn, "update predictions set status = 'COMMITTED' where id = %s", (back,)),
          "the prediction lifecycle cannot run backwards",
          "SETTLED -> COMMITTED rejected")


def scoring_policy() -> None:
    """Calibration has to cost something, or every agent learns to shout."""
    confident_wrong = score_prediction(
        direction="BUY", expected_return=0.02, confidence=0.95, actual_return=-0.02
    )
    hedged_wrong = score_prediction(
        direction="BUY", expected_return=0.02, confidence=0.05, actual_return=-0.02
    )
    check(confident_wrong.value < hedged_wrong.value,
          "being confidently wrong scores worse than being hedged and wrong",
          f"{confident_wrong.value:.1f} < {hedged_wrong.value:.1f}")

    right = score_prediction(
        direction="BUY", expected_return=0.02, confidence=0.9, actual_return=0.02
    )
    check(right.value > confident_wrong.value and 0.0 <= right.value <= 100.0,
          "a correct, well-sized call outscores a wrong one",
          f"{right.value:.1f} vs {confident_wrong.value:.1f}")


def main() -> int:
    print("\nIRIS Phase 5 gate — prediction settlement and evaluation\n")
    now = datetime.now(timezone.utc)

    conn = psycopg.connect(DSN)
    try:
        lifecycle(conn, now)
        refuses_to_invent(conn, now)
        ordering(conn, now)
    finally:
        # Nothing the gate wrote survives it.
        conn.rollback()
        conn.close()

    scoring_policy()

    passed = sum(1 for ok, _, _ in results if ok)
    total = len(results)
    print()
    if passed == total:
        print(f"{GREEN}Phase 5 gate PASSED{RESET} — {passed}/{total} checks.\n")
        return 0
    print(f"{RED}Phase 5 gate FAILED{RESET} — {passed}/{total}.")
    for ok, label, _ in results:
        if not ok:
            print(f"  - {label}")
    print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
