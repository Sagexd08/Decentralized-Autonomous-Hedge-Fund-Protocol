"""
Schema invariant tests — IRIS_BUILD_PROMPT v2.0 sections 13 and 17.

The v2 invariants (section 1) are only real if the database refuses to violate
them. These tests assert that the constraints in db/migrations/0001_init.sql
actually fire, rather than trusting that application code will always do the
right thing.

Requires a running stack:

    docker compose up -d db
    pytest tests/integration/test_schema_invariants.py -v

Every test runs inside a transaction that is rolled back, so the database is
left exactly as it was found.
"""

from __future__ import annotations

import os

import pytest

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")

psycopg2 = pytest.importorskip(
    "psycopg2", reason="psycopg2 is required for the schema invariant tests"
)
from psycopg2 import errors  # noqa: E402  (import needs the skip above to run first)


# Every table required by v2 section 13.
REQUIRED_TABLES = {
    "users", "agents", "model_versions", "agent_stakes", "vaults", "deposits",
    "predictions", "prediction_outcomes", "agent_performance",
    "reputation_scores", "allocation_history", "trades", "positions",
    "risk_events", "slash_events", "agent_runs", "graph_checkpoints",
    "market_events", "news_events", "governance_proposals", "governance_votes",
}


@pytest.fixture(scope="session")
def connection():
    try:
        conn = psycopg2.connect(DSN)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"database unreachable at {DSN}: {exc}")
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture
def cur(connection):
    """A cursor whose work is always rolled back."""
    with connection.cursor() as cursor:
        yield cursor
    connection.rollback()


def _agent_and_model(cur) -> tuple[str, str]:
    cur.execute(
        "select a.id, mv.id from agents a "
        "join model_versions mv on mv.agent_id = a.id and mv.is_active "
        "order by a.id limit 1"
    )
    row = cur.fetchone()
    assert row, "seed data missing: expected at least one agent with an active model"
    return row


# ── Structure ────────────────────────────────────────────────────────────────

def test_all_required_tables_exist(cur):
    cur.execute(
        "select table_name from information_schema.tables where table_schema = 'public'"
    )
    present = {r[0] for r in cur.fetchall()}
    missing = REQUIRED_TABLES - present
    assert not missing, f"missing tables: {sorted(missing)}"


def test_pgvector_is_available(cur):
    """Historical memory (v2 section 12) needs the vector type."""
    cur.execute("select 1 from pg_extension where extname = 'vector'")
    assert cur.fetchone(), "pgvector extension is not installed"


# ── Invariant 2: predictions are measurable and immutable once committed ─────

def test_prediction_cannot_be_committed_after_its_horizon(cur):
    """
    The whole Web3 x ML claim rests on a prediction provably predating its
    outcome. Committing after the horizon has passed must be impossible.
    """
    agent_id, model_id = _agent_and_model(cur)
    with pytest.raises(errors.CheckViolation):
        cur.execute(
            """
            insert into predictions
                (agent_id, model_version_id, asset, direction, expected_return,
                 confidence, horizon_seconds, prediction_hash, committed_at, horizon_end)
            values (%s, %s, 'BTC', 'BUY', 0.01, 0.7, 600, repeat('a', 64),
                    now() + interval '2 hours', now() + interval '1 hour')
            """,
            (agent_id, model_id),
        )


def test_prediction_committed_before_horizon_is_accepted(cur):
    agent_id, model_id = _agent_and_model(cur)
    cur.execute(
        """
        insert into predictions
            (agent_id, model_version_id, asset, direction, expected_return,
             confidence, horizon_seconds, prediction_hash, committed_at, horizon_end)
        values (%s, %s, 'BTC', 'BUY', 0.01, 0.7, 600, repeat('b', 64),
                now(), now() + interval '10 minutes')
        returning status
        """,
        (agent_id, model_id),
    )
    assert cur.fetchone()[0] == "PREDICTED"


def test_prediction_hash_is_unique(cur):
    """Two agents cannot claim the same commitment."""
    agent_id, model_id = _agent_and_model(cur)
    stmt = """
        insert into predictions
            (agent_id, model_version_id, asset, direction, expected_return,
             confidence, horizon_seconds, prediction_hash, horizon_end)
        values (%s, %s, 'ETH', 'SELL', -0.01, 0.6, 600, repeat('c', 64),
                now() + interval '10 minutes')
    """
    cur.execute(stmt, (agent_id, model_id))
    with pytest.raises(errors.UniqueViolation):
        cur.execute(stmt, (agent_id, model_id))


def test_confidence_is_bounded(cur):
    agent_id, model_id = _agent_and_model(cur)
    with pytest.raises(errors.CheckViolation):
        cur.execute(
            """
            insert into predictions
                (agent_id, model_version_id, asset, direction, expected_return,
                 confidence, horizon_seconds, prediction_hash, horizon_end)
            values (%s, %s, 'BTC', 'BUY', 0.01, 1.5, 600, repeat('d', 64),
                    now() + interval '10 minutes')
            """,
            (agent_id, model_id),
        )


# ── Section 0c: never fake production readiness ──────────────────────────────

def test_trade_execution_mode_must_be_labelled(cur):
    """
    A trade is SIMULATION, TESTNET or LIVE. There is no unlabelled state, so a
    simulated fill cannot be presented as a real one.
    """
    cur.execute("select id from agents order by id limit 1")
    agent_id = cur.fetchone()[0]
    with pytest.raises(errors.CheckViolation):
        cur.execute(
            "insert into trades (agent_id, asset, side, quantity, price, execution_mode) "
            "values (%s, 'BTC', 'BUY', 1, 100, 'REAL')",
            (agent_id,),
        )


def test_trade_defaults_to_simulation(cur):
    """An unspecified execution mode must default to the honest one."""
    cur.execute("select id from agents order by id limit 1")
    agent_id = cur.fetchone()[0]
    cur.execute(
        "insert into trades (agent_id, asset, side, quantity, price) "
        "values (%s, 'BTC', 'BUY', 1, 100) returning execution_mode",
        (agent_id,),
    )
    assert cur.fetchone()[0] == "SIMULATION"


# ── Section 9: allocation weights ────────────────────────────────────────────

@pytest.mark.parametrize("weight", [-0.1, 1.5])
def test_allocation_weight_stays_in_the_unit_interval(cur, weight):
    cur.execute("select id from agents order by id limit 1")
    agent_id = cur.fetchone()[0]
    with pytest.raises(errors.CheckViolation):
        cur.execute(
            "insert into allocation_history (agent_id, step, weight, eta) "
            "values (%s, 0, %s, 0.01)",
            (agent_id, weight),
        )


def test_one_allocation_row_per_agent_per_step(cur):
    cur.execute("select id from agents order by id limit 1")
    agent_id = cur.fetchone()[0]
    # A step no real allocation will ever reach. Hardcoding step 0 made this
    # test depend on `allocation_history` being empty, so it started failing
    # the moment Phase 7's allocator wrote a real step 0 — for the right
    # reason, which is the worst kind of false failure.
    cur.execute("select coalesce(max(step), -1) + 1000 from allocation_history")
    step = cur.fetchone()[0]
    stmt = ("insert into allocation_history (agent_id, step, weight, eta) "
            "values (%s, %s, 0.25, 0.01)")
    cur.execute(stmt, (agent_id, step))
    with pytest.raises(errors.UniqueViolation):
        cur.execute(stmt, (agent_id, step))


# ── Section 5: risk profiles are constraints ─────────────────────────────────

def test_vault_allocation_bounds_are_ordered(cur):
    with pytest.raises(errors.CheckViolation):
        cur.execute(
            "insert into vaults (id, name, risk_profile, volatility_cap_bps, "
            "min_allocation_bps, max_allocation_bps) "
            "values ('bad', 'Bad', 'BALANCED', 1000, 3000, 1000)"
        )


# ── Model identity (invariant 3) ─────────────────────────────────────────────

def test_only_one_active_model_version_per_agent(cur):
    agent_id, _ = _agent_and_model(cur)
    with pytest.raises(errors.UniqueViolation):
        cur.execute(
            "insert into model_versions (agent_id, version, model_family, model_hash, is_active) "
            "values (%s, 99, 'baseline', repeat('e', 64), true)",
            (agent_id,),
        )


def test_agent_version_numbers_are_unique(cur):
    agent_id, _ = _agent_and_model(cur)
    with pytest.raises(errors.UniqueViolation):
        cur.execute(
            "insert into model_versions (agent_id, version, model_family, model_hash) "
            "values (%s, 1, 'baseline', repeat('f', 64))",
            (agent_id,),
        )


# ── Retirement drives the Model Cemetery (section 15) ────────────────────────

def test_retired_agent_must_carry_a_retirement_timestamp(cur):
    with pytest.raises(errors.CheckViolation):
        cur.execute("update agents set status = 'RETIRED' where id = "
                    "(select id from agents order by id limit 1)")


def test_retirement_with_a_timestamp_is_accepted(cur):
    cur.execute(
        "update agents set status = 'RETIRED', retired_at = now(), "
        "retirement_reason = 'drawdown breach' "
        "where id = (select id from agents order by id limit 1) "
        "returning status"
    )
    assert cur.fetchone()[0] == "RETIRED"
