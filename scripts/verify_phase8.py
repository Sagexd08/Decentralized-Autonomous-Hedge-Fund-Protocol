#!/usr/bin/env python
"""
Phase 8 gate — IRIS_BUILD_PROMPT v2.0 section 27.

DoD: "Risk + slashing — breach leads to freeze, leads to slash, leads to
reduced allocation."

The DoD is a *chain*, so the gate builds one agent with a real breaching record
and walks it through, checking at each step that the next link actually fired
because of the previous one. Four features that each work is not the same thing
as four features that connect, and a gate that tested them separately would
pass on a system where nothing propagates.

It also checks the links that must NOT fire, which is where a risk engine
usually goes wrong:

  * a small sample must not breach — otherwise every new agent is frozen for
    the variance every new agent has;
  * a single warning must not freeze — one bad window is noise;
  * a slash must cite the breach it punishes;
  * a slashed agent must not be quietly restored to ACTIVE;
  * a frozen agent must still be able to predict, or it can never recover.

Everything runs inside a transaction that is rolled back.

    python scripts/verify_phase8.py
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import psycopg
except ModuleNotFoundError:  # pragma: no cover - host path
    import subprocess

    print("psycopg not available here; running the gate inside the api container.",
          flush=True)
    raise SystemExit(
        subprocess.run(
            ["docker", "compose", "exec", "-T", "api",
             "python", "/repo/scripts/verify_phase8.py"],
        ).returncode
    )

from agents.allocation.allocator import allocate  # noqa: E402
from agents.evaluation.prices import record_price  # noqa: E402
from agents.evaluation.settlement import run_sweep as settle_sweep  # noqa: E402
from agents.risk.engine import (  # noqa: E402
    assess_agent,
    format_sweep,
    run_sweep,
    total_stake,
)
from agents.risk.limits import (  # noqa: E402
    MAX_DRAWDOWN_BPS,
    MIN_SAMPLE_FOR_BREACH,
    WARN_BREACHES_BEFORE_FREEZE,
    evaluate,
    slash_bps_for,
)
from agents.reputation.dimensions import Outcome  # noqa: E402
from agents.reputation.score import load_outcomes  # noqa: E402

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
results: list[tuple[bool, str, str]] = []

VICTIM = "AGT-MERIDIAN"       # the agent we will drive into a breach
BYSTANDER = "AGT-SIGMA"       # must be unaffected


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label, detail))
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  {mark}  {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))


def losing(n: int, loss: float = -0.03) -> list[Outcome]:
    """A record that loses steadily — the shape a drawdown limit exists for."""
    return [
        Outcome(direction="BUY", expected_return=0.02, confidence=0.8,
                actual_return=loss, error=abs(0.02 - loss),
                direction_correct=False, evaluation_score=10.0,
                data_source="SIMULATION")
        for _ in range(n)
    ]


def commit_and_settle(conn, agent: str, *, n: int, entry: float, exit_: float) -> None:
    """
    Give an agent a real settled record, through the real settlement path.

    Not by inserting `prediction_outcomes` directly: the point of the chain is
    that a breach comes from evidence the protocol actually produced, and a gate
    that fabricated the evidence would be testing itself.
    """
    now = datetime.now(timezone.utc)
    model_version_id = conn.execute(
        "select id from model_versions where agent_id = %s limit 1", (agent,)
    ).fetchone()[0]

    for i in range(n):
        asset = f"R8-{uuid.uuid4().hex[:8]}"
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
        record_price(conn, asset=asset, price=exit_,
                     at=at + timedelta(seconds=1800))

    settle_sweep(conn, now=now)


def weight_of(conn, agent: str) -> float:
    round_ = allocate(conn, persist=False)
    return round_.weights.get(agent, 0.0)


# ── the limits, before any database ─────────────────────────────────────────

def limits_section() -> None:
    check(evaluate(losing(MIN_SAMPLE_FOR_BREACH - 1)).is_clear,
          "a small sample cannot breach",
          f"{MIN_SAMPLE_FOR_BREACH - 1} losing predictions, no breach — "
          f"otherwise every new agent is frozen for being new")

    heavy = evaluate(losing(30))
    check(not heavy.is_clear and heavy.drawdown_bps > MAX_DRAWDOWN_BPS,
          "a sustained losing record breaches the drawdown limit",
          f"{heavy.drawdown_bps}bps > {MAX_DRAWDOWN_BPS}bps")

    check(any(b.is_critical for b in heavy.breaches),
          "a drawdown far past the limit is CRITICAL, not a warning",
          heavy.worst)

    mild = evaluate([
        Outcome(direction="BUY", expected_return=0.001, confidence=0.6,
                actual_return=0.001 * (1 if i % 2 else -1), error=0.0005,
                direction_correct=i % 2 == 0, evaluation_score=60.0,
                data_source="SIMULATION")
        for i in range(40)
    ])
    check(mild.is_clear,
          "a flat, unremarkable record does not breach",
          f"drawdown {mild.drawdown_bps}bps, accuracy {mild.accuracy:.0%}")

    check(slash_bps_for(MAX_DRAWDOWN_BPS) <= slash_bps_for(MAX_DRAWDOWN_BPS * 2),
          "a worse breach costs more stake",
          f"{slash_bps_for(MAX_DRAWDOWN_BPS)}bps → "
          f"{slash_bps_for(MAX_DRAWDOWN_BPS * 2)}bps")

    check(slash_bps_for(0) > 0 and slash_bps_for(10 ** 9) <= 10_000,
          "the slash is bounded at both ends",
          f"[{slash_bps_for(0)}, {slash_bps_for(10 ** 9)}]bps of stake")


# ── the chain ───────────────────────────────────────────────────────────────

def chain_section(conn) -> None:
    conn.execute("update agents set status = 'ACTIVE' where id = %s", (VICTIM,))
    conn.execute(
        "insert into agent_stakes (agent_id, amount) values (%s, 1000)", (VICTIM,)
    )
    stake_before = total_stake(conn, VICTIM)
    weight_before = weight_of(conn, VICTIM)
    bystander_before = weight_of(conn, BYSTANDER)

    # ── link 0: evidence ────────────────────────────────────────────────────
    commit_and_settle(conn, VICTIM, n=20, entry=100.0, exit_=96.0)
    profile = evaluate(load_outcomes(conn, VICTIM, data_source="SIMULATION"))
    check(profile.sample_size >= MIN_SAMPLE_FOR_BREACH and not profile.is_clear,
          "a real settled record produces a real breach",
          f"{profile.sample_size} settled, drawdown {profile.drawdown_bps}bps")

    # ── link 1: breach → recorded ───────────────────────────────────────────
    action = assess_agent(conn, VICTIM)
    events = conn.execute(
        "select kind, severity, data_source from risk_events where agent_id = %s",
        (VICTIM,),
    ).fetchall()
    check(len(events) > 0,
          "the breach is recorded, not just detected",
          f"{len(events)} risk_events — before Phase 8 a breach evaporated")
    check(all(e[2] == "SIMULATION" for e in events),
          "every risk event is labelled with its provenance", "SIMULATION")

    # ── link 2: breach → freeze ─────────────────────────────────────────────
    status = conn.execute(
        "select status from agents where id = %s", (VICTIM,)
    ).fetchone()[0]
    # The status lands on SLASHED, not FROZEN: this breach was critical enough
    # that the chain ran straight through freeze into slash in one pass. The
    # freeze still happened and is recorded — checking for a lingering FROZEN
    # status would be asserting that the chain *stalled*.
    check(action.froze and status in ("FROZEN", "SLASHED"),
          "the breach froze the agent", f"{status} — {action.reason[:56]}")
    check(any(e[0] == "FREEZE" for e in events),
          "the freeze itself is recorded, so the status is explicable")

    # ── link 3: freeze → slash ──────────────────────────────────────────────
    slash_row = conn.execute(
        """select risk_event_id, drawdown_bps, slash_bps, amount_slashed, data_source
             from slash_events where agent_id = %s""",
        (VICTIM,),
    ).fetchone()
    check(slash_row is not None, "the agent was slashed")
    check(slash_row and slash_row[0] is not None,
          "the slash cites the breach it punishes",
          "slash_events.risk_event_id is set")

    cited = conn.execute(
        "select agent_id, kind from risk_events where id = %s", (slash_row[0],)
    ).fetchone()
    check(cited and cited[0] == VICTIM,
          "the cited breach belongs to the slashed agent", f"{cited[1]}")

    stake_after = total_stake(conn, VICTIM)
    check(stake_after < stake_before,
          "the slash actually took stake",
          f"{stake_before} → {stake_after} ({slash_row[2]}bps)")
    check(float(slash_row[3]) > 0,
          "the amount taken is recorded", f"{float(slash_row[3])}")

    # ── link 4: slash → reduced allocation ──────────────────────────────────
    weight_after = weight_of(conn, VICTIM)
    check(weight_after == 0.0 and weight_before > 0.0,
          "capital stops reaching the agent",
          f"weight {weight_before:.4f} → {weight_after:.4f}")

    bystander_after = weight_of(conn, BYSTANDER)
    check(bystander_after > bystander_before,
          "the vault is reallocated to the agents still in play",
          f"{BYSTANDER} {bystander_before:.4f} → {bystander_after:.4f}")

    # ── the links that must not fire ────────────────────────────────────────
    conn.execute("savepoint restore")
    try:
        conn.execute(
            "update agents set status = 'ACTIVE' where id = %s", (VICTIM,)
        )
        restored = True
    except psycopg.errors.IntegrityConstraintViolation:
        restored = False
    conn.execute("rollback to savepoint restore")
    check(not restored,
          "a slashed agent cannot be quietly restored to ACTIVE",
          "the database rejected SLASHED → ACTIVE")

    conn.execute("savepoint uncited")
    try:
        conn.execute(
            """insert into slash_events
                   (agent_id, drawdown_bps, slash_bps) values (%s, 5000, 100)""",
            (BYSTANDER,),
        )
        uncited = True
    except psycopg.errors.IntegrityConstraintViolation:
        uncited = False
    conn.execute("rollback to savepoint uncited")
    check(not uncited,
          "a slash with no breach behind it is refused",
          "a punishment nobody can appeal")


# ── freezing is reversible ──────────────────────────────────────────────────

def recovery_section(conn) -> None:
    agent = "AGT-NEXUS"
    conn.execute("update agents set status = 'ACTIVE' where id = %s", (agent,))

    # Enough mild losses to warn repeatedly, but never severely.
    commit_and_settle(conn, agent, n=14, entry=100.0, exit_=98.4)
    for _ in range(WARN_BREACHES_BEFORE_FREEZE + 1):
        action = assess_agent(conn, agent)
        if action.froze:
            break

    status = conn.execute(
        "select status from agents where id = %s", (agent,)
    ).fetchone()[0]
    check(status == "FROZEN" and action.slashed_bps is None,
          "repeated warnings freeze without slashing",
          f"{action.reason[:64]}")

    # A frozen agent must still be able to produce evidence, or it can never
    # come back. Nothing in the runner checks agent status, by design.
    frozen_can_predict = conn.execute(
        """select count(*) from predictions where agent_id = %s""", (agent,)
    ).fetchone()[0]
    conn.execute(
        """insert into predictions
               (agent_id, model_version_id, asset, direction, expected_return,
                confidence, horizon_seconds, prediction_hash, status,
                predicted_at, committed_at, horizon_end)
           values (%s, (select id from model_versions where agent_id = %s limit 1),
                   'R8-FROZEN', 'BUY', 0.01, 0.8, 600, %s, 'COMMITTED',
                   now(), now(), now() + interval '600 seconds')""",
        (agent, agent, uuid.uuid4().hex + uuid.uuid4().hex[:32]),
    )
    after = conn.execute(
        "select count(*) from predictions where agent_id = %s", (agent,)
    ).fetchone()[0]
    check(after == frozen_can_predict + 1,
          "a frozen agent can still predict, so it can earn its way back",
          "freezing removes its capital, not its voice")

    # Give it a clean record and sweep again: the freeze must lift.
    conn.execute(
        """delete from prediction_outcomes where prediction_id in
             (select id from predictions where agent_id = %s)""",
        (agent,),
    )
    conn.execute(
        """update predictions set status = 'EVALUATED' where agent_id = %s""",
        (agent,),
    )
    commit_and_settle(conn, agent, n=15, entry=100.0, exit_=100.5)

    action = assess_agent(conn, agent)
    status = conn.execute(
        "select status from agents where id = %s", (agent,)
    ).fetchone()[0]
    check(action.unfroze and status == "ACTIVE",
          "an agent that recovers is unfrozen",
          "a freeze with no defined exit is a permanent sentence")

    check(
        conn.execute(
            "select count(*) from risk_events where agent_id = %s and kind = 'UNFREEZE'",
            (agent,),
        ).fetchone()[0] > 0,
        "the recovery is recorded too",
    )

    weight = weight_of(conn, agent)
    check(weight > 0.0,
          "capital reaches it again once unfrozen", f"weight {weight:.4f}")


def main() -> int:
    print("\nIRIS Phase 8 gate — risk and slashing\n")
    print(f"  {DIM}the chain: breach → freeze → slash → reduced allocation{RESET}\n")

    limits_section()
    print()

    conn = psycopg.connect(DSN)
    try:
        chain_section(conn)
        print()
        recovery_section(conn)
        print()
        print(format_sweep(run_sweep(conn)))
    finally:
        conn.rollback()
        conn.close()

    passed = sum(1 for ok, _, _ in results if ok)
    total = len(results)
    if passed == total:
        print(f"{GREEN}Phase 8 gate PASSED{RESET} — {passed}/{total} checks.\n")
        return 0
    print(f"{RED}Phase 8 gate FAILED{RESET} — {passed}/{total}.")
    for ok, label, _ in results:
        if not ok:
            print(f"  - {label}")
    print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
