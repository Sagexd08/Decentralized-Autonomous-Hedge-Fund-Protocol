"""
Settlement and evaluation tests — Phase 5 DoD.

DoD: "Hash committed pre-horizon, settled post-horizon, error and score
computed and stored."

The tests are grouped by the failure they exist to prevent, because "does it
compute a number" is the least interesting property a settlement system has.
What matters is whether it ever computes a number it shouldn't:

  * a prediction with no price evidence must not be settled;
  * a committed claim must not be rewritable;
  * an outcome must not exist before the horizon it judges;
  * the lifecycle must not run backwards.

Every database test runs inside a transaction that is rolled back, so the
suite is repeatable and leaves nothing behind.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.evaluation.prices import (  # noqa: E402
    DEFAULT_TOLERANCE,
    fill_price_gaps,
    price_at,
    realised_return,
    record_price,
    seed_simulated_prices,
    simulated_tape,
)
from agents.evaluation.scoring import (  # noqa: E402
    CONFIDENCE_SWING,
    realised_direction,
    score_prediction,
)
from agents.evaluation.settlement import (  # noqa: E402
    _weakest,
    due_predictions,
    evaluate_settled,
    run_sweep,
)

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")
AGENT = "AGT-AXIOM"


@pytest.fixture
def conn():
    """A connection whose work is always discarded."""
    c = psycopg.connect(DSN)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


def commit_prediction(
    conn,
    *,
    asset: str,
    direction: str = "BUY",
    expected_return: float = 0.01,
    confidence: float = 0.7,
    committed_at: datetime,
    horizon_seconds: int = 1800,
) -> str:
    model_version_id = conn.execute(
        "select id from model_versions where agent_id = %s limit 1", (AGENT,)
    ).fetchone()[0]
    pid = str(uuid.uuid4())
    conn.execute(
        """
        insert into predictions
            (id, agent_id, model_version_id, asset, direction, expected_return,
             confidence, horizon_seconds, prediction_hash, status,
             predicted_at, committed_at, horizon_end)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'COMMITTED', %s, %s, %s)
        """,
        (pid, AGENT, model_version_id, asset, direction, expected_return,
         confidence, horizon_seconds,
         uuid.uuid4().hex + uuid.uuid4().hex[:32],
         committed_at, committed_at,
         committed_at + timedelta(seconds=horizon_seconds)),
    )
    return pid


def unique_asset(tag: str) -> str:
    """
    Isolate each test's tape — a shared asset would leak prices between them.

    Kept under `predictions.asset`'s VARCHAR(16), so the tag is truncated
    rather than allowed to blow up the insert.
    """
    return f"{tag[:6]}-{uuid.uuid4().hex[:8]}"


# ── the price source ────────────────────────────────────────────────────────

def test_price_at_finds_the_nearest_observation(conn, now):
    asset = unique_asset("near")
    record_price(conn, asset=asset, price=100.0, at=now - timedelta(seconds=120))
    record_price(conn, asset=asset, price=105.0, at=now - timedelta(seconds=10))

    found = price_at(conn, asset=asset, at=now)
    assert found is not None and found.price == 105.0


def test_price_at_returns_none_beyond_the_tolerance(conn, now):
    """
    The single most important behaviour here: no evidence, no number.

    Falling back to the last price at any distance would manufacture the ground
    truth an agent's reputation is computed from.
    """
    asset = unique_asset("stale")
    record_price(conn, asset=asset, price=100.0, at=now - timedelta(hours=6))
    assert price_at(conn, asset=asset, at=now, tolerance=DEFAULT_TOLERANCE) is None


def test_price_at_is_scoped_to_the_asset(conn, now):
    a, b = unique_asset("a"), unique_asset("b")
    record_price(conn, asset=a, price=100.0, at=now)
    assert price_at(conn, asset=b, at=now) is None


def test_the_simulated_tape_is_reproducible():
    """Section 18: a settlement sweep you cannot replay is one you cannot audit."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(minutes=30)
    first = list(simulated_tape(start=start, end=end, seed=3))
    second = list(simulated_tape(start=start, end=end, seed=3))
    assert first == second
    assert first != list(simulated_tape(start=start, end=end, seed=4))


def test_filling_gaps_twice_writes_nothing_the_second_time(conn, now):
    """
    The feed has to be re-runnable. Duplicate ticks at nearly the same instant
    make `price_at` pick arbitrarily between them, and settlement stops being
    reproducible.
    """
    asset = unique_asset("gap")
    start, end = now - timedelta(minutes=30), now
    step = timedelta(minutes=1)

    first = fill_price_gaps(conn, asset=asset, start=start, end=end, step=step)
    assert first > 0
    assert fill_price_gaps(conn, asset=asset, start=start, end=end, step=step) == 0


def test_filling_gaps_extends_a_tape_that_stops_short(conn, now):
    """
    The case that matters: an open prediction's horizon lands past the end of
    the tape. A feed that refuses to write because the range is "mostly
    covered" leaves exactly that gap, and the prediction never settles.
    """
    asset = unique_asset("tail")
    step = timedelta(minutes=1)
    fill_price_gaps(conn, asset=asset, start=now - timedelta(minutes=30),
                    end=now - timedelta(minutes=10), step=step)

    written = fill_price_gaps(conn, asset=asset, start=now - timedelta(minutes=30),
                              end=now, step=step)
    assert written > 0, "the missing tail must be filled"
    assert price_at(conn, asset=asset, at=now) is not None


def test_filling_gaps_does_not_disturb_an_existing_observation(conn, now):
    """An agent's or a real feed's price must not be overwritten by the simulator."""
    asset = unique_asset("keep")
    at = now - timedelta(minutes=15)
    record_price(conn, asset=asset, price=1234.5, at=at, source="LIVE")
    fill_price_gaps(conn, asset=asset, start=now - timedelta(minutes=30),
                    end=now, step=timedelta(minutes=1))

    found = price_at(conn, asset=asset, at=at)
    assert found.price == 1234.5 and found.source == "LIVE"


def test_realised_return_refuses_a_broken_entry_price():
    with pytest.raises(ValueError):
        realised_return(0.0, 105.0)


# ── the lifecycle ───────────────────────────────────────────────────────────

def test_a_prediction_settles_after_its_horizon(conn, now):
    asset = unique_asset("happy")
    t0 = now - timedelta(hours=2)
    t1 = t0 + timedelta(seconds=1800)
    record_price(conn, asset=asset, price=100.0, at=t0)
    record_price(conn, asset=asset, price=102.0, at=t1)

    pid = commit_prediction(conn, asset=asset, expected_return=0.018, committed_at=t0)
    result = run_sweep(conn, now=now)

    assert pid in [s.prediction_id for s in result.settled]
    status, actual, error, correct, score = conn.execute(
        """select p.status, o.actual_return, o.error, o.direction_correct,
                  o.evaluation_score
             from predictions p join prediction_outcomes o on o.prediction_id = p.id
            where p.id = %s""",
        (pid,),
    ).fetchone()

    assert status == "EVALUATED"
    assert float(actual) == pytest.approx(0.02)
    assert float(error) == pytest.approx(0.002, abs=1e-6)
    assert correct is True
    assert score is not None and 0 <= float(score) <= 100


def test_a_prediction_before_its_horizon_is_not_due(conn, now):
    asset = unique_asset("early")
    pid = commit_prediction(conn, asset=asset, committed_at=now, horizon_seconds=3600)
    assert pid not in [str(r[0]) for r in due_predictions(conn, now=now)]


def test_a_wrong_direction_is_recorded_as_wrong(conn, now):
    asset = unique_asset("wrong")
    t0 = now - timedelta(hours=2)
    t1 = t0 + timedelta(seconds=1800)
    record_price(conn, asset=asset, price=100.0, at=t0)
    record_price(conn, asset=asset, price=97.0, at=t1)

    pid = commit_prediction(conn, asset=asset, direction="BUY", committed_at=t0)
    run_sweep(conn, now=now)

    correct = conn.execute(
        "select direction_correct from prediction_outcomes where prediction_id = %s",
        (pid,),
    ).fetchone()[0]
    assert correct is False


def test_the_sweep_is_idempotent(conn, now):
    """A second sweep must not re-settle or double-score anything."""
    asset = unique_asset("twice")
    t0 = now - timedelta(hours=2)
    record_price(conn, asset=asset, price=100.0, at=t0)
    record_price(conn, asset=asset, price=102.0, at=t0 + timedelta(seconds=1800))
    commit_prediction(conn, asset=asset, committed_at=t0)

    run_sweep(conn, now=now)
    second = run_sweep(conn, now=now)
    assert second.settled == [] and second.evaluated == 0


def test_scoring_is_re_runnable_over_unscored_outcomes(conn, now):
    """
    Measurement and scoring are separate passes so a scoring-policy change can
    be replayed without re-measuring the market.
    """
    asset = unique_asset("rescore")
    t0 = now - timedelta(hours=2)
    record_price(conn, asset=asset, price=100.0, at=t0)
    record_price(conn, asset=asset, price=102.0, at=t0 + timedelta(seconds=1800))
    pid = commit_prediction(conn, asset=asset, committed_at=t0)
    run_sweep(conn, now=now)

    conn.execute(
        "update prediction_outcomes set evaluation_score = null where prediction_id = %s",
        (pid,),
    )
    assert evaluate_settled(conn) == 1


# ── refusing to invent ──────────────────────────────────────────────────────

def test_no_price_evidence_means_no_settlement(conn, now):
    asset = unique_asset("blind")
    pid = commit_prediction(conn, asset=asset, committed_at=now - timedelta(hours=2))
    result = run_sweep(conn, now=now)

    assert pid in result.waiting
    assert conn.execute(
        "select count(*) from prediction_outcomes where prediction_id = %s", (pid,)
    ).fetchone()[0] == 0
    assert conn.execute(
        "select status from predictions where id = %s", (pid,)
    ).fetchone()[0] == "WAITING_FOR_OUTCOME"


def test_half_the_evidence_is_still_no_evidence(conn, now):
    """An entry price without an exit price cannot produce a return."""
    asset = unique_asset("half")
    t0 = now - timedelta(hours=2)
    record_price(conn, asset=asset, price=100.0, at=t0)   # entry only
    pid = commit_prediction(conn, asset=asset, committed_at=t0)
    assert pid in run_sweep(conn, now=now).waiting


def test_a_waiting_prediction_settles_when_evidence_arrives(conn, now):
    asset = unique_asset("later")
    t0 = now - timedelta(hours=2)
    t1 = t0 + timedelta(seconds=1800)
    pid = commit_prediction(conn, asset=asset, committed_at=t0)
    run_sweep(conn, now=now)

    record_price(conn, asset=asset, price=100.0, at=t0)
    record_price(conn, asset=asset, price=101.0, at=t1)
    run_sweep(conn, now=now)

    status, actual = conn.execute(
        """select p.status, o.actual_return from predictions p
             join prediction_outcomes o on o.prediction_id = p.id where p.id = %s""",
        (pid,),
    ).fetchone()
    assert status == "EVALUATED" and float(actual) == pytest.approx(0.01)


# ── provenance ──────────────────────────────────────────────────────────────

def test_an_outcome_carries_the_provenance_of_its_evidence(conn, now):
    asset = unique_asset("prov")
    t0 = now - timedelta(hours=2)
    seed_simulated_prices(
        conn, asset=asset, start=t0 - timedelta(minutes=1),
        end=t0 + timedelta(minutes=35), step=timedelta(minutes=1),
    )
    pid = commit_prediction(conn, asset=asset, committed_at=t0)
    run_sweep(conn, now=now)

    source = conn.execute(
        "select data_source from prediction_outcomes where prediction_id = %s", (pid,)
    ).fetchone()[0]
    assert source == "SIMULATION"


def test_mixed_provenance_takes_the_weaker_label():
    """A return measured from one live and one simulated price is not a live result."""
    assert _weakest("LIVE", "SIMULATION") == "SIMULATION"
    assert _weakest("LIVE", "TESTNET") == "TESTNET"
    assert _weakest("LIVE", "LIVE") == "LIVE"


# ── invariant 2, enforced by the database ───────────────────────────────────

def rejected(conn, sql: str, params: tuple) -> bool:
    conn.execute("savepoint probe")
    try:
        conn.execute(sql, params)
    except psycopg.errors.IntegrityConstraintViolation:
        conn.execute("rollback to savepoint probe")
        return True
    conn.execute("rollback to savepoint probe")
    return False


@pytest.mark.parametrize(
    "column,value",
    [
        ("expected_return", 0.99),
        ("direction", "SELL"),
        ("confidence", 0.01),
        ("horizon_seconds", 99999),
        ("prediction_hash", "0" * 64),
        ("committed_at", datetime(2020, 1, 1, tzinfo=timezone.utc)),
    ],
)
def test_a_committed_claim_cannot_be_rewritten(conn, now, column, value):
    pid = commit_prediction(conn, asset=unique_asset("frozen"), committed_at=now)
    assert rejected(conn, f"update predictions set {column} = %s where id = %s", (value, pid))


def test_a_committed_prediction_cannot_be_deleted(conn, now):
    pid = commit_prediction(conn, asset=unique_asset("undel"), committed_at=now)
    assert rejected(conn, "delete from predictions where id = %s", (pid,))


def test_status_may_still_advance(conn, now):
    """The claim is frozen; the lifecycle is not."""
    pid = commit_prediction(conn, asset=unique_asset("adv"), committed_at=now)
    conn.execute("update predictions set status = 'WAITING_FOR_OUTCOME' where id = %s", (pid,))
    assert conn.execute(
        "select status from predictions where id = %s", (pid,)
    ).fetchone()[0] == "WAITING_FOR_OUTCOME"


def test_the_lifecycle_cannot_run_backwards(conn, now):
    pid = commit_prediction(conn, asset=unique_asset("back"), committed_at=now)
    conn.execute("update predictions set status = 'SETTLED' where id = %s", (pid,))
    assert rejected(conn, "update predictions set status = 'COMMITTED' where id = %s", (pid,))


def test_an_outcome_cannot_precede_its_horizon(conn, now):
    pid = commit_prediction(conn, asset=unique_asset("pre"), committed_at=now,
                            horizon_seconds=3600)
    assert rejected(
        conn,
        """insert into prediction_outcomes
               (prediction_id, actual_return, error, direction_correct, settled_at)
           values (%s, 0.01, 0.0, true, %s)""",
        (pid, now + timedelta(seconds=60)),
    )


def test_a_measurement_cannot_be_restated(conn, now):
    asset = unique_asset("restate")
    t0 = now - timedelta(hours=2)
    record_price(conn, asset=asset, price=100.0, at=t0)
    record_price(conn, asset=asset, price=102.0, at=t0 + timedelta(seconds=1800))
    pid = commit_prediction(conn, asset=asset, committed_at=t0)
    run_sweep(conn, now=now)

    assert rejected(
        conn,
        "update prediction_outcomes set actual_return = 0.5 where prediction_id = %s",
        (pid,),
    )


def test_the_score_may_still_be_rewritten(conn, now):
    """Scoring is policy and must stay re-runnable; the measurement is not."""
    asset = unique_asset("score")
    t0 = now - timedelta(hours=2)
    record_price(conn, asset=asset, price=100.0, at=t0)
    record_price(conn, asset=asset, price=102.0, at=t0 + timedelta(seconds=1800))
    pid = commit_prediction(conn, asset=asset, committed_at=t0)
    run_sweep(conn, now=now)

    conn.execute(
        "update prediction_outcomes set evaluation_score = 42 where prediction_id = %s",
        (pid,),
    )
    assert float(conn.execute(
        "select evaluation_score from prediction_outcomes where prediction_id = %s", (pid,)
    ).fetchone()[0]) == 42.0


# ── the scoring rule ────────────────────────────────────────────────────────

def test_score_is_bounded():
    for expected, actual, conf in [
        (0.0, 0.0, 0.0), (10.0, -10.0, 1.0), (-0.5, 0.5, 1.0), (0.001, 0.001, 1.0)
    ]:
        s = score_prediction(direction="BUY", expected_return=expected,
                             confidence=conf, actual_return=actual)
        assert 0.0 <= s.value <= 100.0


def test_confidence_cuts_both_ways():
    """
    A model rewarded only for being right learns to be confident always. Being
    confidently wrong has to cost more than being hedged and wrong, or the
    calibration dimension in section 12 measures nothing.
    """
    confident = score_prediction(direction="BUY", expected_return=0.02,
                                 confidence=0.95, actual_return=-0.02)
    hedged = score_prediction(direction="BUY", expected_return=0.02,
                              confidence=0.05, actual_return=-0.02)
    assert confident.value < hedged.value

    # A *perfect* call saturates at 100 with no headroom left for confidence to
    # act on, so the reward direction is asserted on a realistic call — right
    # about direction, slightly off on magnitude, which is every real
    # prediction.
    confident_right = score_prediction(direction="BUY", expected_return=0.02,
                                       confidence=0.95, actual_return=0.017)
    hedged_right = score_prediction(direction="BUY", expected_return=0.02,
                                    confidence=0.05, actual_return=0.017)
    assert confident_right.value > hedged_right.value


def test_magnitude_matters_even_when_direction_is_right():
    """Magnitude sizes the position, so it cannot be free."""
    precise = score_prediction(direction="BUY", expected_return=0.02,
                               confidence=0.5, actual_return=0.02)
    sloppy = score_prediction(direction="BUY", expected_return=0.20,
                              confidence=0.5, actual_return=0.02)
    assert precise.value > sloppy.value


def test_a_correct_call_outscores_a_wrong_one_at_equal_confidence():
    right = score_prediction(direction="BUY", expected_return=0.01,
                             confidence=0.6, actual_return=0.01)
    wrong = score_prediction(direction="BUY", expected_return=0.01,
                             confidence=0.6, actual_return=-0.01)
    assert right.value > wrong.value


def test_hold_is_a_real_prediction():
    """"It will not move" is a claim, and is judged like any other."""
    right = score_prediction(direction="HOLD", expected_return=0.0,
                             confidence=0.8, actual_return=0.0001)
    wrong = score_prediction(direction="HOLD", expected_return=0.0,
                             confidence=0.8, actual_return=0.05)
    assert right.direction_correct and not wrong.direction_correct
    assert right.value > wrong.value


def test_realised_direction_uses_the_hold_band():
    assert realised_direction(0.01) == "BUY"
    assert realised_direction(-0.01) == "SELL"
    assert realised_direction(0.0) == "HOLD"
    assert realised_direction(0.0001) == "HOLD"


def test_scoring_rejects_impossible_inputs():
    with pytest.raises(ValueError):
        score_prediction(direction="BUY", expected_return=float("nan"),
                         confidence=0.5, actual_return=0.0)
    with pytest.raises(ValueError):
        score_prediction(direction="BUY", expected_return=0.0,
                         confidence=1.5, actual_return=0.0)


def test_the_confidence_swing_is_bounded():
    """A swing >= 1 would let confidence alone drive a score to 0 or 100."""
    assert 0.0 < CONFIDENCE_SWING < 1.0
