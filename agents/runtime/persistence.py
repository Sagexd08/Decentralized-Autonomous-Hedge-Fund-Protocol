"""
Run persistence — IRIS_BUILD_PROMPT v2.0 sections 13 and 19.

Writes the two tables the schema already defines for exactly this:

  * `agent_runs`        one row per graph execution
  * `graph_checkpoints` one row per node, with the state after it ran

Section 19 asks every agent action to emit a structured event carrying the run
id, node, latency, model version, input/output hashes and decision. Those are
the columns here, so the AI Observatory (section 15) reads real rows rather
than a fixture.

This is separate from LangGraph's own checkpointer, which is about *resuming*
a run. These rows are about *auditing* one, and they outlive it.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from typing import Any, Iterator, Optional

import psycopg
from psycopg.types.json import Json

from agents.state import AgentState

DEFAULT_DSN = "postgresql://iris:iris@localhost:5432/iris"


def dsn() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DSN)


@contextmanager
def connection(dsn_override: Optional[str] = None) -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(dsn_override or dsn())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def state_digest(state: AgentState) -> str:
    """
    A stable fingerprint of the state, for the input/output hash columns.

    Excludes latency, which is wall-clock and would make two otherwise
    identical runs hash differently — the digest is meant to answer "was the
    state the same?", not "did it take the same time?".
    """
    payload = state.model_dump(mode="json", exclude={"node_latency_ms"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def start_run(conn: psycopg.Connection, *, agent_id: str) -> str:
    """Open an agent_runs row and return its id."""
    run_id = str(uuid.uuid4())
    conn.execute(
        "insert into agent_runs (id, agent_id, status) values (%s, %s, 'RUNNING')",
        (run_id, agent_id),
    )
    return run_id


def record_node(
    conn: psycopg.Connection,
    *,
    agent_run_id: str,
    seq: int,
    node: str,
    state: AgentState,
    input_hash: str,
) -> None:
    """Write one graph_checkpoints row for a node that has just run."""
    conn.execute(
        """
        insert into graph_checkpoints
            (agent_run_id, node, seq, state, input_hash, output_hash, latency_ms)
        values (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            agent_run_id,
            node,
            seq,
            Json(state.model_dump(mode="json")),
            input_hash,
            state_digest(state),
            state.node_latency_ms.get(node),
        ),
    )


def finish_run(
    conn: psycopg.Connection,
    *,
    agent_run_id: str,
    state: AgentState,
    latency_ms: int,
) -> None:
    """
    Close the run.

    An abstention is COMPLETED, not FAILED: declining to trade because the risk
    layer objected is the system working. FAILED is reserved for a graph that
    could not finish.
    """
    if state.errors:
        status, error = "FAILED", "; ".join(state.errors)
    elif state.abstained:
        status, error = "ABSTAINED", None
    else:
        status, error = "COMPLETED", None

    conn.execute(
        """
        update agent_runs
           set status = %s, finished_at = now(), latency_ms = %s, error = %s
         where id = %s
        """,
        (status, latency_ms, error, agent_run_id),
    )


def persist_prediction(
    conn: psycopg.Connection, *, state: AgentState
) -> Optional[str]:
    """
    Write the committed prediction.

    Inserted as COMMITTED with `committed_at` and `horizon_end` exactly as the
    node computed them, so the database's own
    `CHECK (committed_at <= horizon_end)` is doing real work here rather than
    being satisfied by construction — if PREDICTION_COMMIT ever produced an
    inverted pair, this insert would fail rather than record a lie.

    Returns the prediction id, or None if the run abstained.
    """
    if not state.prediction_hash or state.decision is None:
        return None

    prediction_id = str(uuid.uuid4())

    # Deliberately NOT writing the agent's observed price into `market_events`.
    #
    # An earlier version did, so settlement would have an entry price. Two
    # things were wrong with it. The narrow one: `market_observation` generates
    # a private tape seeded from the run, unrelated to the shared feed, so the
    # entry and exit legs came from two different price universes and produced
    # returns that measured nothing (every agent wrote the identical 98.372476,
    # and settlement read +2.6% off the disagreement between the series).
    #
    # The broad one is the reason it stays out: an agent that records the price
    # it will later be settled against is an agent grading its own exam. The
    # feed writes the market; the agent observes it; settlement measures it.
    # What the agent saw is preserved in `graph_checkpoints` as what the agent
    # saw, which is the honest place for it.

    conn.execute(
        """
        insert into predictions
            (id, agent_id, model_version_id, asset, direction, expected_return,
             confidence, horizon_seconds, prediction_hash, status,
             predicted_at, committed_at, horizon_end)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'COMMITTED', %s, %s, %s)
        """,
        (
            prediction_id,
            state.agent_id,
            state.model_version_id,
            state.asset,
            state.decision.direction,
            state.decision.expected_return,
            state.decision.confidence,
            state.decision.horizon_seconds,
            state.prediction_hash,
            state.committed_at,
            state.committed_at,
            state.horizon_end,
        ),
    )
    conn.execute(
        "update agent_runs set prediction_id = %s where id = %s",
        (prediction_id, state.agent_run_id),
    )
    return prediction_id


def active_model_version(conn: psycopg.Connection, agent_id: str) -> Optional[str]:
    row = conn.execute(
        "select id from model_versions where agent_id = %s and is_active limit 1",
        (agent_id,),
    ).fetchone()
    return str(row[0]) if row else None


def agent_strategy(conn: psycopg.Connection, agent_id: str) -> str:
    row = conn.execute(
        "select strategy from agents where id = %s", (agent_id,)
    ).fetchone()
    return row[0] if row else "momentum"
