"""
Allocation against the database — Phase 7.

The update rule is unit-tested in `tests/unit/test_allocation.py`. What is
tested here is what happens when it meets real rows: which agents are eligible,
what a stored round can be replayed from, and the two ways an allocation could
quietly stop meaning what it says —

  * capital flowing to an agent that is frozen or slashed, which would make
    Phase 8's risk engine advisory rather than binding;
  * a completed step being rewritten, so the allocation an agent was judged on
    no longer matches the one on record.

Every test runs inside a transaction that is rolled back.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.allocation.allocator import (  # noqa: E402
    allocatable_agents,
    allocate,
    current_step,
    current_weights,
    rewards_from_reputation,
)
from agents.allocation.mwu import check_invariants, uniform  # noqa: E402

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")
TOL = 1e-9


@pytest.fixture
def conn():
    c = psycopg.connect(DSN)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


# ── eligibility ─────────────────────────────────────────────────────────────

def test_only_active_and_probation_agents_are_allocatable(conn):
    statuses = conn.execute(
        """select distinct status from agents
            where id = any(%s)""",
        (allocatable_agents(conn),),
    ).fetchall()
    assert {r[0] for r in statuses} <= {"ACTIVE", "PROBATION"}


@pytest.mark.parametrize("status", ["FROZEN", "SLASHED"])
def test_a_frozen_or_slashed_agent_receives_no_allocation(conn, status):
    """
    If capital kept flowing to a frozen agent, freezing would be a label rather
    than a control, and Phase 8's risk engine would be advisory.
    """
    victim = allocatable_agents(conn)[0]
    if status == "SLASHED":
        conn.execute("update agents set status = 'SLASHED' where id = %s", (victim,))
    else:
        conn.execute("update agents set status = 'FROZEN' where id = %s", (victim,))

    round_ = allocate(conn, persist=False)
    assert victim not in round_.weights


def test_a_retired_agent_receives_no_allocation(conn):
    victim = allocatable_agents(conn)[0]
    conn.execute(
        "update agents set status = 'RETIRED', retired_at = now(), "
        "retirement_reason = 'test' where id = %s",
        (victim,),
    )
    assert victim not in allocate(conn, persist=False).weights


def test_the_vault_is_fully_reallocated_after_an_agent_is_removed(conn):
    """Removing an agent must not leave its share stranded."""
    victim = allocatable_agents(conn)[0]
    conn.execute("update agents set status = 'FROZEN' where id = %s", (victim,))

    round_ = allocate(conn, persist=False)
    assert math.fsum(round_.weights.values()) == pytest.approx(1.0, abs=TOL)


# ── what feeds the update ───────────────────────────────────────────────────

def test_an_unscored_agent_contributes_no_reward(conn):
    """
    Absent, not zero. `update` leaves an agent's weight untouched when it has
    no reward, so an agent with no settled predictions is neither punished nor
    credited — passing 0 would treat "no evidence" as "wrong about everything".
    """
    ids = allocatable_agents(conn)
    rewards = rewards_from_reputation(conn, ids, data_source="SIMULATION")
    assert set(rewards) <= set(ids)
    assert all(0.0 <= v <= 1.0 for v in rewards.values())


def test_rewards_are_read_per_provenance(conn):
    """
    An allocation computed from simulated evidence directs simulated capital.
    Mixing it into a live vault is the same §0c failure as reporting a
    simulated return as live, one step downstream.
    """
    ids = allocatable_agents(conn)
    # TESTNET rather than LIVE as the empty side. The property under test is
    # that a bucket with no record yields no reward — not a zero — and pinning
    # it to LIVE made the test depend on the protocol never having settled a
    # real prediction, which it now does on every cycle.
    assert rewards_from_reputation(conn, ids, data_source="TESTNET") == {}


def test_rewards_are_on_the_zero_to_one_scale(conn):
    """
    The IRIS Score is 0-100 and `update` rejects anything outside [0, 1] — the
    division has to happen here or the exponential produces inf.
    """
    ids = allocatable_agents(conn)
    for value in rewards_from_reputation(conn, ids, data_source="SIMULATION").values():
        assert 0.0 <= value <= 1.0


def test_the_first_allocation_starts_uniform(conn):
    """At step 0 there is no evidence; any other prior asserts a winner."""
    conn.execute("delete from allocation_history")
    ids = allocatable_agents(conn)
    assert current_step(conn) == -1
    assert current_weights(conn, ids) == uniform(ids)


def test_a_new_agent_joins_without_starting_at_zero(conn):
    """
    Zero is absorbing under a multiplicative update, so a newcomer seeded at 0
    could never earn anything at all.
    """
    conn.execute("delete from allocation_history")
    ids = allocatable_agents(conn)
    allocate(conn, persist=True)

    weights = current_weights(conn, ids + ["AGT-BRANDNEW"])
    assert weights["AGT-BRANDNEW"] > 0.0


# ── the round, on disk ──────────────────────────────────────────────────────

def test_a_live_allocation_satisfies_every_invariant(conn):
    assert check_invariants(allocate(conn, persist=False)) == []


def test_every_agent_gets_a_row(conn):
    round_ = allocate(conn, persist=True)
    rows = conn.execute(
        "select count(*) from allocation_history where step = %s", (round_.step,)
    ).fetchone()[0]
    assert rows == len(round_.allocations)


def test_the_persisted_weights_still_sum_to_one(conn):
    """
    `weight` is NUMERIC(12,10). A distribution that sums to 1 in float and to
    0.9999999998 on disk is a distribution that leaks capital every round.
    """
    round_ = allocate(conn, persist=True)
    total = conn.execute(
        "select sum(weight) from allocation_history where step = %s", (round_.step,)
    ).fetchone()[0]
    assert float(total) == pytest.approx(1.0, abs=1e-6)


def test_eta_and_score_are_stored_so_a_step_can_be_replayed(conn):
    round_ = allocate(conn, persist=True)
    rows = conn.execute(
        "select eta, score, weight from allocation_history where step = %s",
        (round_.step,),
    ).fetchall()
    assert all(r[0] is not None for r in rows), "eta must be on every row"
    assert all(0.0 <= float(r[2]) <= 1.0 for r in rows)
    # Scores are stored on the 0-100 scale the leaderboard reports.
    assert all(r[1] is None or 0.0 <= float(r[1]) <= 100.0 for r in rows)


def test_a_completed_step_cannot_be_rewritten(conn):
    """
    UNIQUE (agent_id, step). A corrected allocation is a new step — otherwise
    the allocation an agent was judged on stops matching the one on record.
    """
    round_ = allocate(conn, persist=True)
    agent_id = round_.allocations[0].agent_id

    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(
            """insert into allocation_history (agent_id, step, weight, eta)
               values (%s, %s, 0.5, 0.5)""",
            (agent_id, round_.step),
        )


def test_steps_advance(conn):
    first = allocate(conn, persist=True)
    second = allocate(conn, persist=True)
    assert second.step == first.step + 1


def test_the_next_round_continues_from_the_stored_weights(conn):
    """Not from uniform — otherwise every round discards the last one's evidence."""
    first = allocate(conn, persist=True)
    ids = allocatable_agents(conn)
    resumed = current_weights(conn, ids)
    for agent_id, weight in first.weights.items():
        assert resumed[agent_id] == pytest.approx(weight, abs=1e-9)


def test_an_out_of_range_weight_would_be_rejected_by_the_schema(conn):
    """`weight` is CHECK (>= 0 AND <= 1); the allocator must never test it."""
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            """insert into allocation_history (agent_id, step, weight, eta)
               values (%s, 9999, 1.5, 0.5)""",
            (allocatable_agents(conn)[0],),
        )
