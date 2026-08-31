"""
Driving the allocator from real reputation — IRIS_BUILD_PROMPT v2.0 section 7.

`mwu.update` is pure arithmetic. This is the part that decides what goes into
it, and every decision here is a policy about capital rather than a detail of
the maths.

**An agent with no IRIS Score is not allocated to.** Phase 6 returns None for
an untested agent precisely so this could not be defaulted. It keeps its weight
unchanged rather than being rewarded zero — no evidence is not bad evidence —
and a brand-new agent starts at the uniform share alongside everyone else.

**Scores are read per provenance.** An allocation computed from SIMULATION
scores directs simulated capital. Mixing a live vault's allocation with
simulated evidence is the same §0c failure as reporting a simulated return as
live, one step further downstream.

**Every round is replayable.** `allocation_history` stores the weight, the
score it came from, and the `eta` in force — so an allocation can be recomputed
and disputed later. `UNIQUE (agent_id, step)` means a step cannot be quietly
rewritten; a corrected allocation is a new step, which is the honest shape.
"""

from __future__ import annotations

from typing import Optional

import psycopg

from agents.allocation.mwu import (
    DEFAULT_ETA,
    AllocationRound,
    check_invariants,
    uniform,
    update,
)
from agents.reputation.score import score_agent


def current_step(conn: psycopg.Connection) -> int:
    row = conn.execute("select max(step) from allocation_history").fetchone()
    return -1 if row is None or row[0] is None else int(row[0])


def current_weights(conn: psycopg.Connection, agent_ids: list[str]) -> dict[str, float]:
    """
    The weights from the most recent step, with new agents seeded uniformly.

    A new agent joining an existing allocation is the awkward case: it cannot
    start at 0 (absorbing), and it must not start large enough to take capital
    from proven agents. It starts at the floor's uniform equivalent and earns
    from there — `_project` renormalises the rest down to make room, which is
    the correct dilution.
    """
    step = current_step(conn)
    if step < 0:
        return uniform(agent_ids)

    rows = conn.execute(
        "select agent_id, weight from allocation_history where step = %s", (step,)
    ).fetchall()
    previous = {r[0]: float(r[1]) for r in rows}

    known = [a for a in agent_ids if a in previous]
    if not known:
        return uniform(agent_ids)

    newcomer_share = 1.0 / max(len(agent_ids), 1)
    return {
        agent_id: previous.get(agent_id, newcomer_share) for agent_id in agent_ids
    }


def rewards_from_reputation(
    conn: psycopg.Connection, agent_ids: list[str], *, data_source: str
) -> dict[str, float]:
    """
    IRIS Scores as rewards on [0, 1]. Unscored agents are simply absent.

    Absent, not zero. `mwu.update` leaves an agent's weight untouched when it
    has no reward, so an agent that produced no settled predictions this round
    is neither punished nor credited. Passing 0 would treat "we have no
    evidence" identically to "it was wrong about everything".

    The score is already discounted by evidence (Phase 6), so no further
    sample-size correction is applied here — doing it twice would penalise a
    short record for being short, twice.
    """
    rewards: dict[str, float] = {}
    for agent_id in agent_ids:
        score = score_agent(conn, agent_id, data_source=data_source)
        if score is not None:
            rewards[agent_id] = score.value / 100.0
    return rewards


def allocatable_agents(conn: psycopg.Connection) -> list[str]:
    """
    Agents eligible for capital.

    FROZEN, SLASHED and RETIRED are excluded — the whole point of those states
    is that they stop capital flowing, and an allocator that ignored them would
    make Phase 8's risk engine advisory.
    """
    return [
        r[0]
        for r in conn.execute(
            "select id from agents where status in ('ACTIVE', 'PROBATION') order by id"
        ).fetchall()
    ]


def allocate(
    conn: psycopg.Connection,
    *,
    eta: float = DEFAULT_ETA,
    data_source: str = "SIMULATION",
    persist: bool = True,
    vault_id: Optional[str] = None,
) -> AllocationRound:
    """
    Run one allocation step against the live database.

    The invariants are checked *before* anything is written. A round that
    violates them is a bug in the allocator, and persisting it would put a
    broken distribution in front of the vault — so it raises rather than
    recording the violation and carrying on.
    """
    agent_ids = allocatable_agents(conn)
    previous = current_weights(conn, agent_ids)
    rewards = rewards_from_reputation(conn, agent_ids, data_source=data_source)

    step = current_step(conn) + 1
    round_ = update(previous, rewards, eta=eta, step=step)

    violations = check_invariants(round_)
    if violations:
        raise AssertionError(
            "allocation violated the section 7 invariants and was not written:\n  "
            + "\n  ".join(violations)
        )

    if persist:
        for a in round_.allocations:
            conn.execute(
                """
                insert into allocation_history
                    (agent_id, vault_id, step, weight, score, eta)
                values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    a.agent_id,
                    vault_id,
                    round_.step,
                    a.weight,
                    # Stored on the 0-100 scale the IRIS Score is reported in,
                    # so the row reads the same as the leaderboard it came from.
                    None if a.score is None else a.score * 100.0,
                    round_.eta,
                ),
            )

    return round_


def format_round(round_: AllocationRound) -> str:
    lines = [
        "",
        "MWU allocation — w_i(t+1) = w_i(t) * exp(eta * R_i(t)) / Z   (section 7)",
        "",
        f"{'agent':<16}{'weight':>10}{'was':>10}{'delta':>10}{'score':>9}   note",
        "-" * 78,
    ]
    for a in sorted(round_.allocations, key=lambda x: x.weight, reverse=True):
        delta = a.weight - a.previous
        note = "clamped" if a.agent_id in round_.clamped else (
            "no new evidence" if a.score is None else ""
        )
        score = f"{a.score * 100:.1f}" if a.score is not None else "—"
        lines.append(
            f"{a.agent_id:<16}{a.weight:>10.4f}{a.previous:>10.4f}"
            f"{delta:>+10.4f}{score:>9}   {note}"
        )
    lines += ["", round_.summary(), ""]
    return "\n".join(lines)


def _resolved_source(conn, requested):
    """
    Which provenance bucket to work in.

    `None` means "whichever the protocol actually has evidence in, strongest
    first". Pinning the default to SIMULATION was right while that was the only
    bucket and became wrong the moment predictions started settling against a
    real market — the scorers kept reading an empty bucket and reported every
    agent with a live record as untested.
    """
    from agents.evaluation.prices import strongest_outcome_source

    return requested or strongest_outcome_source(conn)


def main(argv: list[str] | None = None) -> int:
    """
        python -m agents.allocation.allocator
    """
    import argparse

    from agents.runtime.persistence import connection

    parser = argparse.ArgumentParser(description="Run one MWU allocation step.")
    parser.add_argument("--eta", type=float, default=DEFAULT_ETA)
    parser.add_argument("--source", default=None,
                        choices=("SIMULATION", "TESTNET", "LIVE"),
                        help="default: the strongest provenance with settled outcomes")
    parser.add_argument("--vault", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="compute and print without writing allocation_history")
    args = parser.parse_args(argv)

    with connection() as conn:
        round_ = allocate(
            conn, eta=args.eta, data_source=_resolved_source(conn, args.source),
            persist=not args.dry_run, vault_id=args.vault,
        )
        if args.dry_run:
            conn.rollback()

    print(format_round(round_))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
