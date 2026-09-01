"""
Risk engine against the database — Phase 8.

The limits are unit-tested in `tests/unit/test_risk_limits.py`. What is tested
here is the chain, and the constraints that keep it honest:

    breach -> freeze -> slash -> reduced allocation

Plus the refusals, which are the part a risk engine usually gets wrong:
a slash with no breach behind it, a slash citing another agent's breach, a
slashed agent quietly restored, a live slash resting on simulated evidence.

Every test runs inside a transaction that is rolled back.
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

from agents.allocation.allocator import allocate  # noqa: E402
from agents.evaluation.prices import record_price  # noqa: E402
from agents.evaluation.settlement import run_sweep as settle_sweep  # noqa: E402
from agents.reputation.score import load_outcomes  # noqa: E402
from agents.evaluation import settlement  # noqa: E402
from agents.risk.engine import (  # noqa: E402
    assess_agent,
    freeze,
    recent_warnings,
    run_sweep,
    total_stake,
)
from agents.risk.limits import MIN_SAMPLE_FOR_BREACH, Breach, evaluate  # noqa: E402

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")
AGENT = "AGT-HELIX"
OTHER = "AGT-PULSE"


@pytest.fixture
def conn():
    """
    A connection whose work is discarded, over a record this file fully owns.

    Every test here reasons about a **sample size** — "a short record cannot
    trigger anything", "warnings accumulate before a freeze". Those are claims
    about the agent's whole record, not about the rows one test happens to add,
    so the test has to establish its own starting point or it is measuring
    whatever the database happened to be carrying.

    It was not. `give_record` settles through the real sweep, and the sweep
    settles *every* due prediction in the database — so predictions left
    pending for this agent by a phase gate or an earlier session were swept
    into the same sample. `test_a_short_record_cannot_trigger_anything` wrote
    eight outcomes and was handed fourteen, six of which it had never seen.

    So: drain anything already pending, then clear the agent's simulated
    record. Both happen inside the transaction and are rolled back, so nothing
    is actually destroyed — and after them the agent genuinely has the record
    the test says it has.
    """
    c = psycopg.connect(DSN)
    try:
        c.execute("update agents set status = 'ACTIVE' where id in (%s, %s)",
                  (AGENT, OTHER))
        # Drain first: anything still COMMITTED or WAITING would otherwise be
        # settled by the sweep inside `give_record` and counted as this test's.
        settlement.run_sweep(c, now=datetime.now(timezone.utc))
        c.execute(
            """delete from prediction_outcomes o
                using predictions p
                where p.id = o.prediction_id
                  and p.agent_id in (%s, %s)
                  and o.data_source = 'SIMULATION'""",
            (AGENT, OTHER),
        )
        yield c
    finally:
        c.rollback()
        c.close()


def give_record(conn, agent: str, *, n: int, entry: float, exit_: float) -> None:
    """
    A real settled record, through the real settlement path.

    Not by inserting `prediction_outcomes` directly: the chain is supposed to
    start from evidence the protocol produced, and a test that fabricated the
    evidence would be testing itself.
    """
    now = datetime.now(timezone.utc)
    model_version_id = conn.execute(
        "select id from model_versions where agent_id = %s limit 1", (agent,)
    ).fetchone()[0]

    for i in range(n):
        asset = f"K8-{uuid.uuid4().hex[:8]}"
        at = now - timedelta(hours=3) + timedelta(minutes=i)
        conn.execute(
            """
            insert into predictions
                (agent_id, model_version_id, asset, direction, expected_return,
                 confidence, horizon_seconds, prediction_hash, status,
                 predicted_at, committed_at, horizon_end)
            values (%s, %s, %s, 'BUY', 0.02, 0.8, 1800, %s, 'COMMITTED',
                    %s, %s, %s)
            """,
            (agent, model_version_id, asset,
             uuid.uuid4().hex + uuid.uuid4().hex[:32],
             at, at, at + timedelta(seconds=1800)),
        )
        record_price(conn, asset=asset, price=entry, at=at)
        record_price(conn, asset=asset, price=exit_, at=at + timedelta(seconds=1800))

    settle_sweep(conn, now=now)


def status_of(conn, agent: str) -> str:
    return conn.execute(
        "select status from agents where id = %s", (agent,)
    ).fetchone()[0]


# ── the chain ───────────────────────────────────────────────────────────────

def test_a_breach_is_recorded_not_just_detected(conn):
    """
    The link that did not exist before Phase 8. RISK_ANALYSIS has always
    detected breaches, but nothing persisted them — the agent abstained and the
    observation evaporated, so nothing could ever accumulate.
    """
    give_record(conn, AGENT, n=20, entry=100.0, exit_=96.0)
    assess_agent(conn, AGENT)

    events = conn.execute(
        "select kind, severity, data_source from risk_events where agent_id = %s",
        (AGENT,),
    ).fetchall()
    assert events
    assert all(e[2] == "SIMULATION" for e in events)


def test_a_critical_breach_freezes_and_slashes(conn):
    conn.execute("insert into agent_stakes (agent_id, amount) values (%s, 500)",
                 (AGENT,))
    give_record(conn, AGENT, n=20, entry=100.0, exit_=96.0)

    action = assess_agent(conn, AGENT)
    assert action.froze
    assert action.slashed_bps is not None
    assert status_of(conn, AGENT) == "SLASHED"


def test_the_slash_takes_stake(conn):
    conn.execute("insert into agent_stakes (agent_id, amount) values (%s, 1000)",
                 (AGENT,))
    before = total_stake(conn, AGENT)
    give_record(conn, AGENT, n=20, entry=100.0, exit_=96.0)
    assess_agent(conn, AGENT)

    after = total_stake(conn, AGENT)
    assert after < before, "a slash that does not move the stake ledger is a label"

    recorded = conn.execute(
        "select amount_slashed from slash_events where agent_id = %s", (AGENT,)
    ).fetchone()[0]
    assert float(recorded) == pytest.approx(before - after)


def test_a_slash_with_no_stake_is_still_recorded(conn):
    """
    The fact that a slash was warranted is part of the agent's history whether
    or not there was anything to take.
    """
    give_record(conn, AGENT, n=20, entry=100.0, exit_=96.0)
    assess_agent(conn, AGENT)

    row = conn.execute(
        "select slash_bps, amount_slashed from slash_events where agent_id = %s",
        (AGENT,),
    ).fetchone()
    assert row is not None and row[0] > 0
    assert float(row[1]) == 0.0


def test_a_slashed_agent_stops_receiving_capital(conn):
    """The last link. Phase 7 supplies it; this checks it actually fires."""
    before = allocate(conn, persist=False).weights.get(AGENT, 0.0)
    assert before > 0

    give_record(conn, AGENT, n=20, entry=100.0, exit_=96.0)
    assess_agent(conn, AGENT)

    assert allocate(conn, persist=False).weights.get(AGENT, 0.0) == 0.0


def test_capital_moves_to_the_agents_still_in_play(conn):
    before = allocate(conn, persist=False).weights[OTHER]
    give_record(conn, AGENT, n=20, entry=100.0, exit_=96.0)
    assess_agent(conn, AGENT)
    assert allocate(conn, persist=False).weights[OTHER] > before


# ── escalation ──────────────────────────────────────────────────────────────

def test_a_clean_record_is_left_alone(conn):
    give_record(conn, AGENT, n=20, entry=100.0, exit_=100.3)
    action = assess_agent(conn, AGENT)
    assert not action.acted
    assert status_of(conn, AGENT) == "ACTIVE"


def test_a_short_record_cannot_trigger_anything(conn):
    """Freezing on a small sample punishes every agent for being new."""
    give_record(conn, AGENT, n=MIN_SAMPLE_FOR_BREACH - 2, entry=100.0, exit_=80.0)
    action = assess_agent(conn, AGENT)
    assert not action.acted
    assert status_of(conn, AGENT) == "ACTIVE"


def test_warnings_accumulate_before_a_freeze(conn):
    """One bad window is noise. The count is what makes it a trend."""
    give_record(conn, AGENT, n=14, entry=100.0, exit_=98.4)

    froze_on = None
    for attempt in range(1, 6):
        action = assess_agent(conn, AGENT)
        if action.froze:
            froze_on = attempt
            break
    assert froze_on and froze_on > 1, "a single warning must not freeze"
    assert status_of(conn, AGENT) == "FROZEN"


def test_the_warning_count_resets_after_a_freeze(conn):
    """
    Carrying warnings across a completed freeze judges the second offence with
    the first one's weight still attached, after the first was already paid for.
    """
    give_record(conn, AGENT, n=14, entry=100.0, exit_=98.4)
    assess_agent(conn, AGENT)
    before = recent_warnings(conn, AGENT, "DRAWDOWN_BREACH")

    freeze(conn, agent_id=AGENT,
           breach=Breach(kind="DRAWDOWN_BREACH", severity="CRITICAL",
                         measured_bps=9999, limit_bps=2000, detail="test"),
           data_source="SIMULATION")

    assert recent_warnings(conn, AGENT, "DRAWDOWN_BREACH") == 0 < before


# ── recovery ────────────────────────────────────────────────────────────────

def test_a_frozen_agent_that_recovers_is_unfrozen(conn):
    """A freeze with no defined exit is a permanent sentence wearing a soft name."""
    give_record(conn, AGENT, n=14, entry=100.0, exit_=98.4)
    for _ in range(5):
        if assess_agent(conn, AGENT).froze:
            break
    assert status_of(conn, AGENT) == "FROZEN"

    conn.execute(
        """delete from prediction_outcomes where prediction_id in
             (select id from predictions where agent_id = %s)""",
        (AGENT,),
    )
    give_record(conn, AGENT, n=15, entry=100.0, exit_=100.4)

    action = assess_agent(conn, AGENT)
    assert action.unfroze
    assert status_of(conn, AGENT) == "ACTIVE"


def test_a_frozen_agent_that_has_not_recovered_stays_frozen(conn):
    give_record(conn, AGENT, n=14, entry=100.0, exit_=98.4)
    for _ in range(5):
        if assess_agent(conn, AGENT).froze:
            break

    action = assess_agent(conn, AGENT)
    assert not action.unfroze
    assert status_of(conn, AGENT) == "FROZEN"


def test_capital_returns_after_an_unfreeze(conn):
    give_record(conn, AGENT, n=14, entry=100.0, exit_=98.4)
    for _ in range(5):
        if assess_agent(conn, AGENT).froze:
            break
    assert allocate(conn, persist=False).weights.get(AGENT, 0.0) == 0.0

    conn.execute(
        """delete from prediction_outcomes where prediction_id in
             (select id from predictions where agent_id = %s)""",
        (AGENT,),
    )
    give_record(conn, AGENT, n=15, entry=100.0, exit_=100.4)
    assess_agent(conn, AGENT)

    assert allocate(conn, persist=False).weights.get(AGENT, 0.0) > 0.0


# ── what the database refuses ───────────────────────────────────────────────

def test_a_slash_must_cite_a_breach(conn):
    """A punishment nobody can appeal."""
    with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
        conn.execute(
            "insert into slash_events (agent_id, drawdown_bps, slash_bps) "
            "values (%s, 5000, 100)",
            (AGENT,),
        )


def test_a_slash_cannot_cite_another_agents_breach(conn):
    give_record(conn, OTHER, n=20, entry=100.0, exit_=96.0)
    assess_agent(conn, OTHER)
    foreign = conn.execute(
        "select id from risk_events where agent_id = %s limit 1", (OTHER,)
    ).fetchone()[0]

    with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
        conn.execute(
            """insert into slash_events
                   (agent_id, risk_event_id, drawdown_bps, slash_bps)
               values (%s, %s, 5000, 100)""",
            (AGENT, foreign),
        )


def test_a_live_slash_cannot_rest_on_simulated_evidence(conn):
    """
    Everything upstream of a slash is currently simulated. Without this, the
    Model Cemetery becomes a list of agents punished for a synthetic tape, with
    nothing on the row to say so.
    """
    give_record(conn, AGENT, n=20, entry=100.0, exit_=96.0)
    assess_agent(conn, AGENT)
    sim_event = conn.execute(
        "select id from risk_events where agent_id = %s and data_source = 'SIMULATION' limit 1",
        (AGENT,),
    ).fetchone()[0]

    with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
        conn.execute(
            """insert into slash_events
                   (agent_id, risk_event_id, drawdown_bps, slash_bps, data_source)
               values (%s, %s, 5000, 100, 'LIVE')""",
            (AGENT, sim_event),
        )


def test_a_slashed_agent_cannot_be_restored(conn):
    give_record(conn, AGENT, n=20, entry=100.0, exit_=96.0)
    assess_agent(conn, AGENT)
    assert status_of(conn, AGENT) == "SLASHED"

    with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
        conn.execute("update agents set status = 'ACTIVE' where id = %s", (AGENT,))


def test_a_retired_agent_cannot_come_back(conn):
    conn.execute(
        "update agents set status = 'RETIRED', retired_at = now(), "
        "retirement_reason = 'test' where id = %s",
        (AGENT,),
    )
    with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
        conn.execute("update agents set status = 'ACTIVE' where id = %s", (AGENT,))


def test_a_slash_cannot_exceed_the_stake(conn):
    """10,000bps is the whole stake; more is a debt with no way to collect it."""
    give_record(conn, AGENT, n=20, entry=100.0, exit_=96.0)
    assess_agent(conn, AGENT)
    event = conn.execute(
        "select id from risk_events where agent_id = %s limit 1", (AGENT,)
    ).fetchone()[0]

    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            """insert into slash_events
                   (agent_id, risk_event_id, drawdown_bps, slash_bps)
               values (%s, %s, 5000, 10001)""",
            (AGENT, event),
        )


# ── the sweep ───────────────────────────────────────────────────────────────

def test_the_sweep_covers_every_live_agent(conn):
    result = run_sweep(conn)
    live = conn.execute(
        "select count(*) from agents where status <> 'RETIRED'"
    ).fetchone()[0]
    assert result.scanned == live


def test_an_agent_with_no_record_is_untouched_by_the_sweep(conn):
    result = run_sweep(conn)
    quiet = [a for a in result.actions if a.profile.sample_size == 0]
    assert quiet, "this fixture database has agents with no settled record"
    assert not any(a.acted for a in quiet)
