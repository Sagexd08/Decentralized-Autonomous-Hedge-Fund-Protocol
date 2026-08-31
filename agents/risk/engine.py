"""
The risk engine — IRIS_BUILD_PROMPT v2.0 section 8.

Phase 8's DoD is a chain, not a feature list:

    breach -> freeze -> slash -> reduced allocation

Each link has to *cause* the next, and each is recorded so the chain can be
read back afterwards. `slash_events.risk_event_id` is not decoration: a slash
that cannot name the breach it punishes is a punishment nobody can appeal, and
the database refuses to record one (see `db/migrations/0003_risk.sql`).

The last link already exists. Phase 7's `allocatable_agents` excludes FROZEN,
SLASHED and RETIRED, and the Phase 7 gate proves the vault is fully reallocated
around a removed agent. So this module owns detection, freezing and slashing,
and the gate's job is to show that an allocation actually moves as a result.

**A frozen agent keeps predicting.** Freezing removes its capital, not its
voice. That is deliberate: the MWU floor in Phase 7 exists so an agent can earn
its way back, and it can only do that by producing new settled outcomes. A
freeze that also stopped the agent running would be a permanent sentence
wearing a reversible name.

**Freezing is reversible; slashing is not.** A frozen agent whose drawdown
recovers below the limit is unfrozen by the same sweep that froze it. A slashed
agent is not restored — the database rejects SLASHED -> ACTIVE. It can be
retired, or its operator can register a new agent, which is the honest way to
start over.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

import psycopg
from psycopg.types.json import Json

from agents.reputation.score import load_outcomes
from agents.risk.limits import (
    CRITICAL_MULTIPLE,
    MAX_DRAWDOWN_BPS,
    WARN_BREACHES_BEFORE_FREEZE,
    Breach,
    RiskProfile,
    evaluate,
    slash_bps_for,
)


@dataclass
class AgentAction:
    """What the engine did about one agent, and why."""

    agent_id: str
    profile: RiskProfile
    recorded: list[str] = field(default_factory=list)   # risk_event ids
    froze: bool = False
    unfroze: bool = False
    slashed_bps: Optional[int] = None
    slash_event_id: Optional[str] = None
    reason: str = ""

    @property
    def acted(self) -> bool:
        return self.froze or self.unfroze or self.slashed_bps is not None


@dataclass
class SweepResult:
    actions: list[AgentAction]
    scanned: int

    @property
    def frozen(self) -> list[str]:
        return [a.agent_id for a in self.actions if a.froze]

    @property
    def unfrozen(self) -> list[str]:
        return [a.agent_id for a in self.actions if a.unfroze]

    @property
    def slashed(self) -> list[str]:
        return [a.agent_id for a in self.actions if a.slashed_bps is not None]

    def summary(self) -> str:
        return (
            f"scanned {self.scanned}, froze {len(self.frozen)}, "
            f"unfroze {len(self.unfrozen)}, slashed {len(self.slashed)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Recording
# ─────────────────────────────────────────────────────────────────────────────

def record_breach(
    conn: psycopg.Connection,
    *,
    agent_id: str,
    breach: Breach,
    data_source: str,
    detail: Optional[dict] = None,
) -> str:
    """
    Write one risk event and return its id.

    This is the link that did not exist before Phase 8. `RISK_ANALYSIS` has
    always detected breaches, but nothing persisted them — the agent abstained
    and the observation evaporated, so nothing could ever accumulate and nothing
    could be slashed for it.
    """
    event_id = str(uuid.uuid4())
    conn.execute(
        """
        insert into risk_events
            (id, agent_id, kind, severity, measured_bps, limit_bps, detail, data_source)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            event_id, agent_id, breach.kind, breach.severity,
            breach.measured_bps, breach.limit_bps,
            Json({"detail": breach.detail, **(detail or {})}),
            data_source,
        ),
    )
    return event_id


def recent_warnings(conn: psycopg.Connection, agent_id: str, kind: str) -> int:
    """
    How many unresolved warnings of this kind the agent has collected.

    Counted since the last FREEZE, so an agent that was frozen, recovered and
    was unfrozen starts its count again. Carrying warnings across a completed
    freeze would mean the second offence is judged with the first one's weight
    still attached, after the first was already paid for.
    """
    return conn.execute(
        """
        select count(*) from risk_events
         where agent_id = %s and kind = %s and severity = 'WARN'
           and created_at > coalesce(
               (select max(created_at) from risk_events
                 where agent_id = %s and kind = 'FREEZE'),
               '-infinity'::timestamptz)
        """,
        (agent_id, kind, agent_id),
    ).fetchone()[0]


def total_stake(conn: psycopg.Connection, agent_id: str) -> float:
    """Net stake: deposits less unstakes."""
    row = conn.execute(
        """
        select coalesce(sum(case when is_unstake then -amount else amount end), 0)
          from agent_stakes where agent_id = %s
        """,
        (agent_id,),
    ).fetchone()
    return float(row[0]) if row else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# The chain
# ─────────────────────────────────────────────────────────────────────────────

def freeze(
    conn: psycopg.Connection, *, agent_id: str, breach: Breach, data_source: str
) -> str:
    """
    Stop capital reaching this agent, and record that it happened.

    The status change is what Phase 7's allocator reads; the FREEZE risk event
    is what makes the change explicable afterwards. Writing one without the
    other would leave either an unexplained status or an unenforced warning.
    """
    conn.execute(
        "update agents set status = 'FROZEN' where id = %s and status <> 'RETIRED'",
        (agent_id,),
    )
    return record_breach(
        conn,
        agent_id=agent_id,
        breach=Breach(
            kind="FREEZE", severity="CRITICAL",
            measured_bps=breach.measured_bps, limit_bps=breach.limit_bps,
            detail=f"frozen after {breach.kind}: {breach.detail}",
        ),
        data_source=data_source,
    )


def unfreeze(
    conn: psycopg.Connection, *, agent_id: str, profile: RiskProfile, data_source: str
) -> str:
    """
    Restore an agent whose record has come back inside its limits.

    The defined exit. Without one, a freeze is a permanent sentence with a
    reversible-sounding name, and the MWU floor that lets an agent earn its way
    back becomes decorative.
    """
    conn.execute(
        "update agents set status = 'ACTIVE' where id = %s and status = 'FROZEN'",
        (agent_id,),
    )
    return record_breach(
        conn,
        agent_id=agent_id,
        breach=Breach(
            kind="UNFREEZE", severity="INFO",
            measured_bps=profile.drawdown_bps, limit_bps=MAX_DRAWDOWN_BPS,
            detail=(
                f"recovered: drawdown {profile.drawdown_bps}bps back within "
                f"{MAX_DRAWDOWN_BPS}bps over {profile.sample_size} predictions"
            ),
        ),
        data_source=data_source,
    )


def slash(
    conn: psycopg.Connection,
    *,
    agent_id: str,
    profile: RiskProfile,
    risk_event_id: str,
    data_source: str,
) -> tuple[str, int, float]:
    """
    Take a share of the agent's stake, and mark it SLASHED.

    Returns (slash_event_id, bps, amount). The amount may be 0 when the agent
    has no stake — the event is still recorded, because the fact that a slash
    was warranted is part of the agent's history whether or not there was
    anything to take.
    """
    bps = slash_bps_for(profile.drawdown_bps)
    stake = total_stake(conn, agent_id)
    amount = round(stake * bps / 10_000, 6)

    event_id = str(uuid.uuid4())
    conn.execute(
        """
        insert into slash_events
            (id, agent_id, risk_event_id, drawdown_bps, slash_bps,
             amount_slashed, data_source)
        values (%s, %s, %s, %s, %s, %s, %s)
        """,
        (event_id, agent_id, risk_event_id, profile.drawdown_bps, bps,
         amount, data_source),
    )

    if amount > 0:
        # Recorded as an unstake so the stake ledger stays a single source of
        # truth. A slash that only wrote slash_events would leave `total_stake`
        # reporting money the agent no longer has.
        conn.execute(
            """
            insert into agent_stakes (agent_id, amount, is_unstake)
            values (%s, %s, true)
            """,
            (agent_id, amount),
        )

    conn.execute(
        "update agents set status = 'SLASHED' where id = %s and status <> 'RETIRED'",
        (agent_id,),
    )
    return event_id, bps, amount


def assess_agent(
    conn: psycopg.Connection, agent_id: str, *, data_source: str = "SIMULATION"
) -> AgentAction:
    """
    Run the whole chain for one agent.

    Order matters and is not arbitrary: recovery is checked before escalation,
    so an agent that has already come back inside its limits is unfrozen rather
    than re-examined for a breach it no longer has.
    """
    outcomes = load_outcomes(conn, agent_id, data_source=data_source)
    profile = evaluate(outcomes)
    action = AgentAction(agent_id=agent_id, profile=profile)

    status = conn.execute(
        "select status from agents where id = %s", (agent_id,)
    ).fetchone()
    if status is None:
        action.reason = "no such agent"
        return action
    status = status[0]

    if status in ("SLASHED", "RETIRED"):
        action.reason = f"{status.lower()}; nothing further to do"
        return action

    # ── recovery ────────────────────────────────────────────────────────────
    if status == "FROZEN":
        if profile.is_clear:
            action.recorded.append(
                unfreeze(conn, agent_id=agent_id, profile=profile,
                         data_source=data_source)
            )
            action.unfroze = True
            action.reason = "recovered inside its limits"
        else:
            action.reason = f"still breaching: {profile.breaches[0].kind}"
        return action

    if profile.is_clear:
        action.reason = (
            "within limits"
            if profile.sample_size else "no settled record"
        )
        return action

    # ── record every breach ─────────────────────────────────────────────────
    event_ids: dict[str, str] = {}
    for breach in profile.breaches:
        event_id = record_breach(
            conn, agent_id=agent_id, breach=breach, data_source=data_source,
            detail={"sample_size": profile.sample_size,
                    "cumulative_return": round(profile.cumulative_return, 8)},
        )
        action.recorded.append(event_id)
        event_ids[breach.kind] = event_id

    critical = next((b for b in profile.breaches if b.is_critical), None)

    # ── escalate ────────────────────────────────────────────────────────────
    if critical is not None:
        # A drawdown this far past the limit is not a warning to accumulate.
        action.recorded.append(
            freeze(conn, agent_id=agent_id, breach=critical, data_source=data_source)
        )
        action.froze = True

        event_id, bps, amount = slash(
            conn, agent_id=agent_id, profile=profile,
            risk_event_id=event_ids[critical.kind], data_source=data_source,
        )
        action.slashed_bps = bps
        action.slash_event_id = event_id
        action.reason = (
            f"{critical.kind} at {critical.measured_bps}bps "
            f"({CRITICAL_MULTIPLE}x the {critical.limit_bps}bps limit) — "
            f"frozen and slashed {bps}bps ({amount})"
        )
        return action

    # A WARN has to repeat. One bad window is noise; enough of them is a trend.
    worst = profile.breaches[0]
    count = recent_warnings(conn, agent_id, worst.kind)
    if count >= WARN_BREACHES_BEFORE_FREEZE:
        action.recorded.append(
            freeze(conn, agent_id=agent_id, breach=worst, data_source=data_source)
        )
        action.froze = True
        action.reason = (
            f"{count} {worst.kind} warnings since its last freeze — frozen, "
            f"not slashed: the limit was exceeded repeatedly but never severely"
        )
    else:
        action.reason = (
            f"{worst.kind} warning {count}/{WARN_BREACHES_BEFORE_FREEZE} "
            f"before a freeze"
        )
    return action


def run_sweep(
    conn: psycopg.Connection, *, data_source: str = "SIMULATION"
) -> SweepResult:
    """Assess every agent that is still in play."""
    agent_ids = [
        r[0] for r in conn.execute(
            "select id from agents where status not in ('RETIRED') order by id"
        ).fetchall()
    ]
    return SweepResult(
        actions=[
            assess_agent(conn, agent_id, data_source=data_source)
            for agent_id in agent_ids
        ],
        scanned=len(agent_ids),
    )


def format_sweep(result: SweepResult) -> str:
    lines = [
        "",
        "Risk sweep — breach → freeze → slash (section 8).",
        "Everything below is measured on SIMULATION evidence and recorded as such.",
        "",
        f"{'agent':<16}{'n':>5}{'drawdown':>10}{'vol':>8}{'cvar':>8}{'acc':>7}   action",
        "-" * 96,
    ]
    for a in result.actions:
        p = a.profile
        mark = (
            "SLASHED" if a.slashed_bps is not None
            else "FROZEN" if a.froze
            else "UNFROZEN" if a.unfroze
            else ""
        )
        lines.append(
            f"{a.agent_id:<16}{p.sample_size:>5}{p.drawdown_bps:>9}b"
            f"{p.volatility_bps:>7}b{p.cvar_bps:>7}b{p.accuracy:>7.2f}   "
            f"{mark + ' — ' if mark else ''}{a.reason}"
        )
    lines += ["", result.summary(), ""]
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
        python -m agents.risk.engine
    """
    import argparse

    from agents.runtime.persistence import connection

    parser = argparse.ArgumentParser(description="Run one risk sweep.")
    parser.add_argument("--source", default=None,
                        choices=("SIMULATION", "TESTNET", "LIVE"),
                        help="default: the strongest provenance with settled outcomes")
    parser.add_argument("--dry-run", action="store_true",
                        help="assess without freezing, slashing or recording")
    args = parser.parse_args(argv)

    with connection() as conn:
        source = _resolved_source(conn, args.source)
        result = run_sweep(conn, data_source=source)
        if args.dry_run:
            conn.rollback()

    print(format_sweep(result))
    if not args.dry_run and (result.frozen or result.slashed):
        print("  Run `make allocate` to see capital move away from them.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
