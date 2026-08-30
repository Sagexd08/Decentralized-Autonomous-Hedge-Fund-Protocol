"""
Protocol event stream tests — Phase 9.

The socket end-to-end is covered by `scripts/verify_phase9.py`, which connects
a real client while the protocol runs. What is tested here is the layer under
it: the outbox triggers, and the reader that tails them.

The property worth defending is that this layer *cannot* invent an event. Every
frame originates as a row written by a trigger on one of the eight tables
phases 3-8 touch, so these tests mostly assert that doing a real thing produces
exactly the event it should, and that the log cannot be edited afterwards.

Every test runs inside a transaction that is rolled back — including the
trigger writes, since those happen in the same transaction as the row that
caused them.
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
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from agents.allocation.allocator import allocate  # noqa: E402
from agents.evaluation.prices import record_price  # noqa: E402
from agents.evaluation.settlement import run_sweep as settle_sweep  # noqa: E402
from agents.reputation.score import persist_score, score_agent  # noqa: E402
from agents.risk.engine import assess_agent  # noqa: E402
from services.event_stream import (  # noqa: E402
    Event,
    Subscriber,
    backlog,
    fetch_since,
    latest_seq,
)

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")
AGENT = "AGT-VECTOR"


@pytest.fixture
def conn():
    c = psycopg.connect(DSN)
    try:
        c.execute("update agents set status = 'ACTIVE' where id = %s", (AGENT,))
        yield c
    finally:
        c.rollback()
        c.close()


@pytest.fixture
def mark(conn) -> int:
    """The sequence number before this test did anything."""
    return latest_seq(conn)


def since(conn, mark: int) -> list[Event]:
    return fetch_since(conn, mark, limit=500)


def kinds(events: list[Event]) -> set[str]:
    return {e.kind for e in events}


def commit_prediction(conn, *, asset: str, at: datetime) -> str:
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
        values (%s, %s, %s, %s, 'BUY', 0.01, 0.8, 1800, %s, 'COMMITTED',
                %s, %s, %s)
        """,
        (pid, AGENT, model_version_id, asset,
         uuid.uuid4().hex + uuid.uuid4().hex[:32],
         at, at, at + timedelta(seconds=1800)),
    )
    return pid


# ── the outbox emits what happened ──────────────────────────────────────────

def test_committing_a_prediction_emits_an_event(conn, mark):
    pid = commit_prediction(conn, asset="EV-1", at=datetime.now(timezone.utc))
    events = since(conn, mark)

    committed = [e for e in events if e.kind == "PREDICTION_COMMITTED"]
    assert len(committed) == 1
    assert committed[0].source_table == "predictions"
    assert committed[0].source_id == pid
    assert committed[0].agent_id == AGENT


def test_settling_emits_a_settled_then_a_scored_event(conn, mark):
    """
    Two events, not one. Measurement and scoring are separate passes (Phase 5),
    and a stream that collapsed them would make the distinction invisible to
    anyone watching.
    """
    now = datetime.now(timezone.utc)
    at = now - timedelta(hours=2)
    asset = f"EV-{uuid.uuid4().hex[:6]}"
    commit_prediction(conn, asset=asset, at=at)
    record_price(conn, asset=asset, price=100.0, at=at)
    record_price(conn, asset=asset, price=102.0, at=at + timedelta(seconds=1800))

    settle_sweep(conn, now=now)
    seen = kinds(since(conn, mark))
    assert "PREDICTION_SETTLED" in seen
    assert "PREDICTION_SCORED" in seen


def test_scoring_an_agent_emits_a_reputation_event(conn, mark):
    now = datetime.now(timezone.utc)
    at = now - timedelta(hours=2)
    asset = f"EV-{uuid.uuid4().hex[:6]}"
    commit_prediction(conn, asset=asset, at=at)
    record_price(conn, asset=asset, price=100.0, at=at)
    record_price(conn, asset=asset, price=102.0, at=at + timedelta(seconds=1800))
    settle_sweep(conn, now=now)

    score = score_agent(conn, AGENT)
    persist_score(conn, score)

    reputation = [e for e in since(conn, mark) if e.kind == "REPUTATION_UPDATED"]
    assert reputation
    assert float(reputation[-1].payload["iris_score"]) == pytest.approx(score.value)


def test_allocating_emits_one_event_per_agent(conn, mark):
    round_ = allocate(conn, persist=True)
    allocation = [e for e in since(conn, mark) if e.kind == "ALLOCATION_UPDATED"]
    assert len(allocation) == len(round_.allocations)


def test_a_risk_breach_emits_an_event(conn, mark):
    now = datetime.now(timezone.utc)
    for i in range(20):
        asset = f"EV-{uuid.uuid4().hex[:6]}"
        at = now - timedelta(hours=3) + timedelta(minutes=i)
        commit_prediction(conn, asset=asset, at=at)
        record_price(conn, asset=asset, price=100.0, at=at)
        record_price(conn, asset=asset, price=96.0, at=at + timedelta(seconds=1800))
    settle_sweep(conn, now=now)

    assess_agent(conn, AGENT)
    seen = kinds(since(conn, mark))
    assert any(k.startswith("RISK_") for k in seen)
    assert "AGENT_SLASHED" in seen


def test_a_status_change_emits_an_event(conn, mark):
    conn.execute("update agents set status = 'FROZEN' where id = %s", (AGENT,))
    frozen = [e for e in since(conn, mark) if e.kind == "AGENT_FROZEN"]
    assert frozen
    assert frozen[0].payload["from"] == "ACTIVE"
    assert frozen[0].payload["to"] == "FROZEN"


def test_an_unchanged_status_emits_nothing(conn, mark):
    """An UPDATE that changes nothing is not an event."""
    conn.execute("update agents set status = 'ACTIVE' where id = %s", (AGENT,))
    assert not [e for e in since(conn, mark) if e.source_table == "agents"]


# ── every event points at a real row ────────────────────────────────────────

PRIMARY_KEY = {
    "agent_runs": "id", "graph_checkpoints": "id", "predictions": "id",
    "prediction_outcomes": "prediction_id", "reputation_scores": "id",
    "allocation_history": "id", "risk_events": "id", "slash_events": "id",
    "agents": "id",
}


def test_every_event_names_a_row_that_exists(conn, mark):
    """
    The property the whole design exists for. If this can fail, the stream is
    a claim rather than a feed.
    """
    now = datetime.now(timezone.utc)
    at = now - timedelta(hours=2)
    asset = f"EV-{uuid.uuid4().hex[:6]}"
    commit_prediction(conn, asset=asset, at=at)
    record_price(conn, asset=asset, price=100.0, at=at)
    record_price(conn, asset=asset, price=102.0, at=at + timedelta(seconds=1800))
    settle_sweep(conn, now=now)
    allocate(conn, persist=True)

    for event in since(conn, mark):
        key = PRIMARY_KEY[event.source_table]
        found = conn.execute(
            f"select 1 from {event.source_table} where {key}::text = %s",
            (event.source_id,),
        ).fetchone()
        assert found, f"{event.kind} points at a missing {event.source_table} row"


def test_provenance_travels_with_the_event(conn, mark):
    """
    A frame that drops `data_source` hands the UI a number with no way to know
    it came from a simulated tape.
    """
    now = datetime.now(timezone.utc)
    at = now - timedelta(hours=2)
    asset = f"EV-{uuid.uuid4().hex[:6]}"
    commit_prediction(conn, asset=asset, at=at)
    record_price(conn, asset=asset, price=100.0, at=at, source="SIMULATION")
    record_price(conn, asset=asset, price=102.0,
                 at=at + timedelta(seconds=1800), source="SIMULATION")
    settle_sweep(conn, now=now)

    events = since(conn, mark)
    assert events
    assert all(e.data_source in ("SIMULATION", "TESTNET", "LIVE") for e in events)
    settled = [e for e in events if e.kind == "PREDICTION_SETTLED"]
    assert settled and settled[0].data_source == "SIMULATION"


# ── ordering and resumability ───────────────────────────────────────────────

def test_sequence_numbers_are_monotonic_across_sources(conn, mark):
    """
    One log rather than eight means a prediction can never arrive before the
    run that produced it.
    """
    now = datetime.now(timezone.utc)
    at = now - timedelta(hours=2)
    asset = f"EV-{uuid.uuid4().hex[:6]}"
    commit_prediction(conn, asset=asset, at=at)
    record_price(conn, asset=asset, price=100.0, at=at)
    record_price(conn, asset=asset, price=102.0, at=at + timedelta(seconds=1800))
    settle_sweep(conn, now=now)
    allocate(conn, persist=True)

    seqs = [e.seq for e in since(conn, mark)]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)


def test_fetch_since_is_exclusive(conn, mark):
    commit_prediction(conn, asset="EV-X", at=datetime.now(timezone.utc))
    first = since(conn, mark)
    assert first
    assert not [e for e in fetch_since(conn, first[-1].seq) ]


def test_backlog_returns_oldest_first(conn, mark):
    for i in range(3):
        commit_prediction(conn, asset=f"EV-B{i}", at=datetime.now(timezone.utc))
    recent = backlog(conn, limit=3)
    assert [e.seq for e in recent] == sorted(e.seq for e in recent)


def test_backlog_can_be_scoped_to_one_agent(conn, mark):
    commit_prediction(conn, asset="EV-S", at=datetime.now(timezone.utc))
    scoped = backlog(conn, limit=20, agent_id=AGENT)
    assert scoped
    assert all(e.agent_id == AGENT for e in scoped)


# ── the log is a record, not a buffer ───────────────────────────────────────

def test_the_event_log_cannot_be_edited(conn, mark):
    commit_prediction(conn, asset="EV-I", at=datetime.now(timezone.utc))
    seq = since(conn, mark)[0].seq

    with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
        conn.execute("update protocol_events set kind = 'FAKE' where seq = %s", (seq,))


def test_the_event_log_cannot_be_deleted_from(conn, mark):
    commit_prediction(conn, asset="EV-D", at=datetime.now(timezone.utc))
    seq = since(conn, mark)[0].seq

    with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
        conn.execute("delete from protocol_events where seq = %s", (seq,))


# ── fan-out ─────────────────────────────────────────────────────────────────

def event(seq: int, *, agent: str = AGENT, kind: str = "RUN_STARTED") -> Event:
    return Event(seq=seq, kind=kind, source_table="agent_runs", source_id="x",
                 agent_id=agent, data_source="SIMULATION", payload={},
                 created_at="")


def test_a_subscriber_can_filter_by_agent():
    sub = Subscriber(agent_id="AGT-ALPHA")
    assert sub.wants(event(1, agent="AGT-ALPHA"))
    assert not sub.wants(event(2, agent="AGT-BETA"))


def test_a_subscriber_can_filter_by_kind():
    sub = Subscriber(kinds={"AGENT_SLASHED"})
    assert sub.wants(event(1, kind="AGENT_SLASHED"))
    assert not sub.wants(event(2, kind="NODE_COMPLETED"))


def test_an_unfiltered_subscriber_wants_everything():
    sub = Subscriber()
    assert sub.wants(event(1)) and sub.wants(event(2, agent="OTHER"))


def test_a_slow_subscriber_is_dropped_rather_than_buffered_forever():
    """
    An unbounded queue behind a client that has stopped reading is a slow leak
    that only appears under the load it is least able to survive. Dropping is
    safe because `seq` is monotonic — the client reconnects with a watermark
    and loses nothing.
    """
    sub = Subscriber()
    for i in range(Subscriber.MAX_PENDING + 10):
        sub.offer(event(i))
    assert sub.dropped
    assert sub.queue.qsize() <= Subscriber.MAX_PENDING


def test_a_filtered_out_event_does_not_fill_the_queue():
    sub = Subscriber(agent_id="AGT-ALPHA")
    for i in range(Subscriber.MAX_PENDING + 10):
        sub.offer(event(i, agent="AGT-BETA"))
    assert not sub.dropped and sub.queue.qsize() == 0
