#!/usr/bin/env python
"""
Phase 7 gate — IRIS_BUILD_PROMPT v2.0 section 27.

DoD: "MWU allocation — 4 mathematical invariants pass as tests."

    w_i(t+1) = w_i(t) * exp(eta * R_i(t)) / Z

The four invariants:

    1. weights always sum to 1
    2. weights are never negative
    3. a better score never loses weight relative to a worse one
    4. the update is bounded — no weight reaches 0 or 1

Each is checked as a *property over randomised inputs*, not on one hand-picked
example. Three of the four hold trivially on a well-behaved round and fail only
on the inputs nobody writes a fixture for: identical scores, all-zero scores,
one agent, five hundred agents, a weight already at the floor, a thousand
consecutive rounds of the same agent winning. So the gate generates those.

Invariant 3 also gets an adversarial pass: does a *worse* record ever end up
with more capital? That is the entire claim of the mechanism, and a version
that fails it would still pass invariants 1, 2 and 4 while allocating at random.

    python scripts/verify_phase7.py
"""

from __future__ import annotations

import math
import os
import random
import sys
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
             "python", "/repo/scripts/verify_phase7.py"],
        ).returncode
    )

from agents.allocation.allocator import allocate, format_round  # noqa: E402
from agents.allocation.mwu import (  # noqa: E402
    DEFAULT_ETA,
    MAX_WEIGHT,
    MIN_WEIGHT,
    _bounds,
    check_invariants,
    uniform,
    update,
)

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
results: list[tuple[bool, str, str]] = []

TOLERANCE = 1e-9


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label, detail))
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  {mark}  {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))


def agents(n: int) -> list[str]:
    return [f"AGT-{i:03d}" for i in range(n)]


def random_rounds(seed: int = 0, trials: int = 400):
    """
    Rounds spanning the cases a fixture would not cover.

    Deliberately includes degenerate shapes: one agent, hundreds of agents,
    every score identical, every score zero, and long chains where one agent
    wins every round — which is how a weight reaches an absorbing 0 or 1.
    """
    rng = random.Random(seed)
    for t in range(trials):
        n = rng.choice([1, 2, 3, 8, 40, 150])
        ids = agents(n)
        weights = uniform(ids)
        eta = rng.choice([0.01, 0.1, DEFAULT_ETA, 1.0, 5.0])
        chain = rng.choice([1, 1, 1, 5, 50])
        mode = rng.choice(["random", "identical", "zero", "one_winner", "extreme"])

        for step in range(chain):
            if mode == "identical":
                rewards = {a: 0.5 for a in ids}
            elif mode == "zero":
                rewards = {a: 0.0 for a in ids}
            elif mode == "one_winner":
                rewards = {a: (1.0 if a == ids[0] else 0.0) for a in ids}
            elif mode == "extreme":
                rewards = {a: rng.choice([0.0, 1.0]) for a in ids}
            else:
                rewards = {a: rng.random() for a in ids}
                # Some agents produce no evidence at all in a given round.
                for a in list(rewards):
                    if rng.random() < 0.2:
                        del rewards[a]

            round_ = update(weights, rewards, eta=eta, step=step)
            weights = round_.weights
            yield t, mode, eta, round_


def invariant_section() -> None:
    rounds = list(random_rounds())
    print(f"  {DIM}{len(rounds)} randomised rounds, 1-150 agents, eta 0.01-5.0, "
          f"chains up to 50 steps{RESET}\n")

    # 1 — sums to 1
    worst, worst_case = 0.0, ""
    for _, mode, eta, r in rounds:
        total = math.fsum(a.weight for a in r.allocations)
        if abs(total - 1.0) > worst:
            worst, worst_case = abs(total - 1.0), f"{mode}, eta {eta}"
    check(worst <= TOLERANCE,
          "1. weights always sum to 1",
          f"worst deviation {worst:.2e} ({worst_case})")

    # 2 — never negative, always finite
    bad = [
        (mode, a.agent_id, a.weight)
        for _, mode, _, r in rounds
        for a in r.allocations
        if a.weight < 0 or not math.isfinite(a.weight)
    ]
    check(not bad,
          "2. weights are never negative or non-finite",
          f"{len(rounds)} rounds clean" if not bad else str(bad[:3]))

    # 3 — monotone in score
    violations = [
        v for _, _, _, r in rounds for v in check_invariants(r) if v.startswith("3.")
    ]
    check(not violations,
          "3. a better score never loses weight to a worse one",
          "monotone in every round" if not violations else violations[0])

    # 4 — bounded
    lowest = min(a.weight for _, _, _, r in rounds for a in r.allocations)
    highest = max(
        a.weight for _, _, _, r in rounds
        for a in r.allocations if len(r.allocations) > 1
    )
    check(lowest > 0.0 and highest < 1.0,
          "4. no weight reaches 0 or 1",
          f"range [{lowest:.4f}, {highest:.4f}]")

    # Against the *effective* bounds, not the policy constants. Two agents
    # cannot both hold at most 0.40 and still sum to 1, and one agent must hold
    # exactly 1 — so `_bounds` relaxes the policy to what is achievable, and
    # the invariant is that no agent exceeds what is achievable.
    floor_breaks, cap_breaks = [], []
    for _, mode, eta, r in rounds:
        lo, hi = _bounds(len(r.allocations))
        for a in r.allocations:
            if a.weight < lo - TOLERANCE:
                floor_breaks.append((mode, a.agent_id, a.weight, lo))
            if a.weight > hi + TOLERANCE:
                cap_breaks.append((mode, a.agent_id, a.weight, hi))

    check(not floor_breaks,
          "4a. the floor holds — a wiped-out agent can still recover",
          f"lowest {lowest:.4f}, policy floor {MIN_WEIGHT}"
          if not floor_breaks else str(floor_breaks[:2]))
    check(not cap_breaks,
          "4b. the cap holds — no agent captures the vault",
          f"highest {highest:.4f}, policy cap {MAX_WEIGHT} "
          f"(relaxed to 1/n where fewer than {math.ceil(1 / MAX_WEIGHT)} agents)"
          if not cap_breaks else str(cap_breaks[:2]))


def adversarial_section() -> None:
    """Invariant 3 is the mechanism's whole claim; spot-check it directly."""
    ids = agents(5)
    weights = uniform(ids)
    # AGT-000 is the best, AGT-004 the worst, held steady for 30 rounds.
    rewards = {a: 1.0 - i * 0.2 for i, a in enumerate(ids)}
    for step in range(30):
        weights = update(weights, rewards, eta=DEFAULT_ETA, step=step).weights

    ranked = sorted(weights, key=lambda a: weights[a], reverse=True)
    check(ranked == ids,
          "sustained performance orders the vault",
          " > ".join(f"{a}:{weights[a]:.3f}" for a in ranked))

    # A collapse must be survivable: the mechanism is multiplicative, so a
    # weight of exactly 0 can never grow again however good the agent becomes.
    weights = uniform(ids)
    for step in range(200):
        weights = update(
            weights, {a: (0.0 if a == "AGT-000" else 1.0) for a in ids},
            eta=5.0, step=step,
        ).weights
    floored = weights["AGT-000"]

    for step in range(200):
        weights = update(
            weights, {a: (1.0 if a == "AGT-000" else 0.0) for a in ids},
            eta=5.0, step=step,
        ).weights
    check(floored > 0.0 and weights["AGT-000"] > floored * 5,
          "an agent that collapses can earn its way back",
          f"{floored:.4f} after 200 losing rounds → "
          f"{weights['AGT-000']:.4f} after 200 winning ones")

    # No evidence must not be treated as bad evidence.
    weights = uniform(ids)
    after = update(weights, {"AGT-000": 1.0}, eta=DEFAULT_ETA).weights
    silent = [a for a in ids if a != "AGT-000"]
    check(len({round(after[a], 12) for a in silent}) == 1,
          "agents with no new evidence move together, not down",
          f"all at {after[silent[0]]:.4f}")

    # Identical scores must not manufacture a ranking.
    flat = update(uniform(ids), {a: 0.7 for a in ids}, eta=DEFAULT_ETA).weights
    check(len({round(w, 12) for w in flat.values()}) == 1,
          "identical scores produce identical weights",
          f"all at {list(flat.values())[0]:.4f}")


def database_section(conn) -> None:
    round_ = allocate(conn, persist=True)
    check(not check_invariants(round_),
          "a live allocation satisfies every invariant",
          round_.summary())

    rows = conn.execute(
        "select agent_id, weight, eta, score from allocation_history where step = %s",
        (round_.step,),
    ).fetchall()
    check(len(rows) == len(round_.allocations),
          "every agent's weight is recorded", f"{len(rows)} rows")

    total = math.fsum(float(r[1]) for r in rows)
    check(abs(total - 1.0) < 1e-6,
          "the persisted weights still sum to 1",
          f"{total:.10f} (NUMERIC(12,10) round-trip)")

    check(all(r[2] is not None for r in rows),
          "eta is stored with every row, so a step is replayable")

    # UNIQUE (agent_id, step) is what stops a step being quietly rewritten.
    conn.execute("savepoint dup")
    try:
        conn.execute(
            """insert into allocation_history (agent_id, step, weight, eta)
               values (%s, %s, 0.5, 0.5)""",
            (rows[0][0], round_.step),
        )
        rewrote = True
    except psycopg.errors.UniqueViolation:
        rewrote = False
    conn.execute("rollback to savepoint dup")
    check(not rewrote,
          "a completed step cannot be rewritten",
          "UNIQUE (agent_id, step) rejected the second row")

    # Frozen agents must not be allocated to, or Phase 8's risk engine is advisory.
    victim = rows[0][0]
    conn.execute("update agents set status = 'FROZEN' where id = %s", (victim,))
    frozen_round = allocate(conn, persist=False)
    check(victim not in frozen_round.weights,
          "a FROZEN agent receives no allocation", victim)
    check(abs(math.fsum(frozen_round.weights.values()) - 1.0) < TOLERANCE,
          "the vault is fully reallocated after an agent is removed",
          f"{len(frozen_round.weights)} agents still sum to 1")

    print(format_round(round_))


def main() -> int:
    print("\nIRIS Phase 7 gate — MWU allocation\n")
    invariant_section()
    print()
    adversarial_section()
    print()

    conn = psycopg.connect(DSN)
    try:
        database_section(conn)
    finally:
        conn.rollback()
        conn.close()

    passed = sum(1 for ok, _, _ in results if ok)
    total = len(results)
    if passed == total:
        print(f"{GREEN}Phase 7 gate PASSED{RESET} — {passed}/{total} checks.\n")
        return 0
    print(f"{RED}Phase 7 gate FAILED{RESET} — {passed}/{total}.")
    for ok, label, _ in results:
        if not ok:
            print(f"  - {label}")
    print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
