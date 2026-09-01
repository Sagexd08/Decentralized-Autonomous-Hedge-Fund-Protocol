"""
Reputation against the database — Phase 6.

The pure scoring logic is unit-tested in `tests/unit/test_reputation.py`. What
is tested here is the part that can only go wrong once real rows are involved,
and every one of these is a way the score could quietly stop meaning what it
says:

  * unsettled predictions leaking into a record;
  * simulated and live outcomes being aggregated together;
  * a stored score that cannot be recomputed from its own row;
  * scoring overwriting history instead of appending to it.

Every test runs inside a transaction that is rolled back.
"""

from __future__ import annotations

import math
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.evaluation.prices import record_price  # noqa: E402
from agents.evaluation.settlement import run_sweep  # noqa: E402
from agents.reputation.score import (  # noqa: E402
    load_outcomes,
    persist_score,
    score_agent,
    score_all,
)

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")
AGENT = "AGT-MERIDIAN"


@pytest.fixture
def conn():
    """
    A connection whose work is discarded, over a record this file owns.

    Every test here counts an agent's outcomes — "a settled prediction enters
    the record", "another agent's predictions do not". Those are claims about
    the agent's *whole* simulated record, so a leftover outcome from a phase
    gate or an earlier session does not merely add noise, it changes the number
    being asserted. Four of these tests broke exactly that way, and they are
    the fifth set in this suite to do so.

    So the agent starts from a known state: anything still pending is drained
    through the real sweep (otherwise `run_sweep` inside a test would settle it
    and count it as that test's), then its simulated outcomes are cleared. Both
    happen inside the transaction and are rolled back, so nothing is destroyed
    — the agent simply has, for the length of one test, the record the test
    says it has.
    """
    c = psycopg.connect(DSN)
    try:
        run_sweep(c, now=datetime.now(timezone.utc))
        c.execute(
            """delete from prediction_outcomes o
                using predictions p
                where p.id = o.prediction_id
                  and o.data_source = 'SIMULATION'""",
        )
        yield c
    finally:
        c.rollback()
        c.close()


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


def asset(tag: str) -> str:
    return f"{tag[:5]}-{uuid.uuid4().hex[:8]}"


def commit(
    conn, *, at: datetime, asset_name: str, direction: str = "BUY",
    expected_return: float = 0.01, confidence: float = 0.7,
    horizon_seconds: int = 1800, agent: str = AGENT, status: str = "COMMITTED",
) -> str:
    model_version_id = conn.execute(
        "select id from model_versions where agent_id = %s limit 1", (agent,)
    ).fetchone()[0]
    pid = str(uuid.uuid4())
    conn.execute(
        """
        insert into predictions
            (id, agent_id, model_version_id, asset, direction, expected_return,
             confidence, horizon_seconds, prediction_hash, status,
             predicted_at, committed_at, horizon_end)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (pid, agent, model_version_id, asset_name, direction, expected_return,
         confidence, horizon_seconds,
         uuid.uuid4().hex + uuid.uuid4().hex[:32], status,
         at, at, at + timedelta(seconds=horizon_seconds)),
    )
    return pid


def settle(conn, *, now: datetime, at: datetime, asset_name: str,
           entry: float = 100.0, exit_: float = 102.0, source: str = "SIMULATION"):
    # A LIVE observation must name the venue it came from — migration 0005
    # makes that structural, so that relabelling synthetic data as real
    # requires asserting a specific exchange said so.
    venue = "binance" if source == "LIVE" else None
    record_price(conn, asset=asset_name, price=entry, at=at,
                 source=source, provider=venue)
    record_price(conn, asset=asset_name, price=exit_,
                 at=at + timedelta(seconds=1800), source=source, provider=venue)
    return run_sweep(conn, now=now)


# ── what enters a record ────────────────────────────────────────────────────

def test_a_settled_prediction_enters_the_record(conn, now):
    a = asset("in")
    at = now - timedelta(hours=2)
    commit(conn, at=at, asset_name=a)
    settle(conn, now=now, at=at, asset_name=a)

    outcomes = load_outcomes(conn, AGENT, data_source="SIMULATION")
    assert len(outcomes) == 1
    assert outcomes[0].direction_correct is True


def test_an_unsettled_prediction_never_enters_the_record(conn, now):
    """
    WAITING_FOR_OUTCOME exists so predictions with no evidence stay out of
    every reputation number. Counting them as neutral would let an agent dilute
    a bad record by predicting on assets that have no price feed.
    """
    before = len(load_outcomes(conn, AGENT, data_source="SIMULATION"))
    commit(conn, at=now - timedelta(hours=2), asset_name=asset("wait"))
    run_sweep(conn, now=now)   # no prices recorded: parks in WAITING_FOR_OUTCOME
    assert len(load_outcomes(conn, AGENT, data_source="SIMULATION")) == before


def test_a_measured_but_unscored_outcome_does_not_count(conn, now):
    """
    Measurement is a fact; scoring is a policy. A row that has been measured
    but not yet scored is a half-finished sweep, not a result.
    """
    a = asset("half")
    at = now - timedelta(hours=2)
    pid = commit(conn, at=at, asset_name=a)
    settle(conn, now=now, at=at, asset_name=a)

    assert len(load_outcomes(conn, AGENT, data_source="SIMULATION")) == 1

    conn.execute(
        "update prediction_outcomes set evaluation_score = null where prediction_id = %s",
        (pid,),
    )
    assert load_outcomes(conn, AGENT, data_source="SIMULATION") == [], (
        "an outcome with no evaluation_score must drop out of the record"
    )


def test_another_agents_predictions_do_not_enter_this_record(conn, now):
    a = asset("other")
    at = now - timedelta(hours=2)
    commit(conn, at=at, asset_name=a, agent="AGT-SIGMA")
    settle(conn, now=now, at=at, asset_name=a)
    assert load_outcomes(conn, AGENT, data_source="SIMULATION") == []


# ── provenance ──────────────────────────────────────────────────────────────

def test_records_are_never_aggregated_across_provenance(conn, now):
    """
    An agent with simulated outcomes and live ones does not have a reputation;
    it has two records. Merging them would present a simulated track record as
    live performance (section 0c).
    """
    at = now - timedelta(hours=2)

    sim, live = asset("sim"), asset("live")
    commit(conn, at=at, asset_name=sim)
    commit(conn, at=at, asset_name=live)
    settle(conn, now=now, at=at, asset_name=sim, source="SIMULATION")
    settle(conn, now=now, at=at, asset_name=live, source="LIVE")

    simulated = load_outcomes(conn, AGENT, data_source="SIMULATION")
    real = load_outcomes(conn, AGENT, data_source="LIVE")

    # Scoped to the two assets this test created rather than counted in total.
    # `run_sweep` settles every prediction that is due, not only this test's,
    # so once the protocol runs against a real feed the agent accumulates
    # genuine LIVE outcomes and any absolute count here is a race with it.
    landed = dict(
        conn.execute(
            """select p.asset, o.data_source
                 from prediction_outcomes o
                 join predictions p on p.id = o.prediction_id
                where p.asset = any(%s)""",
            ([sim, live],),
        ).fetchall()
    )
    assert landed == {sim: "SIMULATION", live: "LIVE"}

    # And each bucket stays homogeneous — the property the split exists for.
    assert all(o.data_source == "SIMULATION" for o in simulated)
    assert all(o.data_source == "LIVE" for o in real)


def test_an_agent_with_no_record_under_a_provenance_has_no_score_under_it(conn, now):
    """
    A score exists per provenance or not at all — never as a default.

    TESTNET is used as the empty side rather than LIVE, which the agent now
    genuinely has a record under. The property under test is that an absent
    record yields None rather than a zero; which label happens to be empty is
    incidental, and pinning it to LIVE made the test depend on the protocol
    never having run.
    """
    at = now - timedelta(hours=2)
    a = asset("simo")
    commit(conn, at=at, asset_name=a)
    settle(conn, now=now, at=at, asset_name=a)

    assert score_agent(conn, AGENT, data_source="SIMULATION") is not None
    assert score_agent(conn, AGENT, data_source="TESTNET") is None


# ── persistence ─────────────────────────────────────────────────────────────

def test_a_stored_score_is_re_derivable_from_its_own_row(conn, now):
    """
    `reputation_scores` keeps `dimensions` and `weights` side by side for
    exactly this. A reputation number nobody can reproduce is one nobody can
    dispute.
    """
    at = now - timedelta(hours=2)
    a = asset("derv")
    commit(conn, at=at, asset_name=a)
    settle(conn, now=now, at=at, asset_name=a)

    score = score_agent(conn, AGENT)
    persist_score(conn, score)

    value, dimensions, weights = conn.execute(
        """select iris_score, dimensions, weights from reputation_scores
            where agent_id = %s order by computed_at desc limit 1""",
        (AGENT,),
    ).fetchone()

    recomputed = float(dimensions["_evidence"]) * 100.0 * math.fsum(
        float(dimensions[name]) * float(w) for name, w in weights.items()
    )
    assert recomputed == pytest.approx(float(value), abs=1e-2)


def test_provenance_and_sample_size_are_stored_with_the_score(conn, now):
    """Without them the stored number cannot be interpreted later."""
    at = now - timedelta(hours=2)
    a = asset("meta")
    commit(conn, at=at, asset_name=a)
    settle(conn, now=now, at=at, asset_name=a)

    score = score_agent(conn, AGENT)
    persist_score(conn, score)

    dimensions = conn.execute(
        """select dimensions from reputation_scores
            where agent_id = %s order by computed_at desc limit 1""",
        (AGENT,),
    ).fetchone()[0]

    assert dimensions["_data_source"] == "SIMULATION"
    assert dimensions["_sample_size"] == score.sample_size
    assert dimensions["_evidence"] == pytest.approx(score.evidence)


def test_scoring_appends_rather_than_overwriting(conn, now):
    """
    `reputation_scores` is a history. The Observatory plots how standing moved,
    and Phase 7's allocator has to be auditable against the score it saw.
    """
    at = now - timedelta(hours=2)
    a = asset("hist")
    commit(conn, at=at, asset_name=a)
    settle(conn, now=now, at=at, asset_name=a)

    before = conn.execute(
        "select count(*) from reputation_scores where agent_id = %s", (AGENT,)
    ).fetchone()[0]

    score = score_agent(conn, AGENT)
    persist_score(conn, score)
    persist_score(conn, score)

    after = conn.execute(
        "select count(*) from reputation_scores where agent_id = %s", (AGENT,)
    ).fetchone()[0]
    assert after == before + 2


def test_score_all_returns_untested_agents_as_none(conn, now):
    """
    Returned rather than dropped, so the Arena can render "not scored yet" as
    exactly that instead of as a zero.
    """
    scores = score_all(conn, persist=False)
    agent_count = conn.execute("select count(*) from agents").fetchone()[0]

    assert len(scores) == agent_count
    assert any(s is None for s in scores.values()), (
        "this fixture database has some agents with no settled predictions"
    )
    assert all(s is None or s.agent_id in scores for s in scores.values())


def test_a_stored_score_satisfies_the_schema_constraint(conn, now):
    """`iris_score` is CHECK (BETWEEN 0 AND 100); the code must never test it."""
    at = now - timedelta(hours=2)
    a = asset("bound")
    commit(conn, at=at, asset_name=a, expected_return=999.0, confidence=1.0)
    settle(conn, now=now, at=at, asset_name=a)

    score = score_agent(conn, AGENT)
    persist_score(conn, score)   # would raise if the value were out of range
    assert 0.0 <= score.value <= 100.0
