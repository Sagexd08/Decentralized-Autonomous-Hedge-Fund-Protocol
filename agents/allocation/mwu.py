"""
Multiplicative-weights allocation — IRIS_BUILD_PROMPT v2.0 section 7.

    w_i(t+1) = w_i(t) * exp(eta * R_i(t)) / Z

Capital follows performance, continuously and without a vote. An agent that
predicts well compounds its share; one that predicts badly loses it. No agent
ever holds a key — this decides how much of the vault each agent may *direct*,
which is a different thing from custody (section 5, and the Phase 2 gate).

The four invariants in the Phase 7 DoD are properties of this function, and
each one is a way the mechanism could be decorative rather than real:

  1. **Weights sum to 1.** Otherwise the allocator is inventing or destroying
     capital between rounds.
  2. **Weights are never negative.** The exponential guarantees this on paper;
     underflow and division by a near-zero Z are how it fails in practice.
  3. **A better score never loses weight relative to a worse one.** This is the
     entire claim of the algorithm. If it can be violated, the mechanism is
     theatre.
  4. **The update is bounded.** One catastrophic round must not drive a weight
     to exactly 0 or 1. At 0 an agent can never recover, however well it
     performs afterwards — the update is multiplicative, so zero is absorbing.
     At 1 one agent holds the entire vault after a single step.

Invariant 4 is not automatic and is the one most likely to be left out. The
exponential alone will happily produce 1e-300, so a floor and a cap are applied
by projecting onto the simplex under those bounds — see `_project`, and note
that the obvious "clamp then renormalise" is wrong.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

# Learning rate. How hard one round of evidence moves capital.
#
# Too high and a single bad week wipes an agent out; too low and the mechanism
# does nothing and the protocol is a fixed allocation with extra steps. 0.5
# means a full-marks round roughly triples an agent's weight against a
# zero-marks one, which takes a handful of rounds to matter and is recoverable.
DEFAULT_ETA = 0.5

# Invariant 4, floor half. No agent's weight may fall below this share.
#
# Zero is absorbing under a multiplicative update: w=0 stays 0 forever, however
# well the agent performs afterwards, because 0 * exp(anything) is 0. An agent
# that has a bad month must be able to earn its way back, so the floor is the
# difference between demotion and permanent execution. It also keeps the agent
# producing predictions, which is the only way new evidence about it arrives.
MIN_WEIGHT = 0.005

# Invariant 4, cap half. No agent may hold more than this share of a vault.
#
# Concentration risk: a single agent at weight 1.0 means the protocol *is* that
# agent, and its next mistake is the vault's. This is a risk limit, deliberately
# blunt, and it binds before the exponential has a chance to run away.
MAX_WEIGHT = 0.40

# exp() overflows around 709. Scores are bounded to [0, 1] and eta is small, so
# this should be unreachable — it is a guard against a future caller passing a
# raw 0-100 score, which would silently produce inf and then NaN weights.
MAX_EXPONENT = 50.0


@dataclass(frozen=True)
class Allocation:
    """One agent's share of a vault at one step."""

    agent_id: str
    weight: float
    score: Optional[float]     # the 0-1 reward this step was computed from
    previous: float


@dataclass(frozen=True)
class AllocationRound:
    """One step of the update, with everything needed to replay it."""

    step: int
    eta: float
    allocations: list[Allocation]
    clamped: list[str]         # agents whose weight hit the floor or the cap

    @property
    def weights(self) -> dict[str, float]:
        return {a.agent_id: a.weight for a in self.allocations}

    def summary(self) -> str:
        moved = sum(abs(a.weight - a.previous) for a in self.allocations) / 2.0
        return (
            f"step {self.step}: {len(self.allocations)} agents, eta {self.eta}, "
            f"{moved:.1%} of the vault reallocated"
            + (f", clamped {', '.join(self.clamped)}" if self.clamped else "")
        )


def uniform(agent_ids: Sequence[str]) -> dict[str, float]:
    """
    The starting distribution: everyone equal.

    Uniform rather than seeded by anything, because at step 0 there is no
    evidence. Any other starting point is a prior about which agent is better,
    asserted before any of them has predicted anything.
    """
    if not agent_ids:
        return {}
    share = 1.0 / len(agent_ids)
    return {agent_id: share for agent_id in agent_ids}


def _bounds(n: int) -> tuple[float, float]:
    """
    The floor and cap, made feasible for this many agents.

    MIN_WEIGHT and MAX_WEIGHT are policy, but policy cannot override
    arithmetic: two agents cannot both hold at most 0.40 of a vault and still
    sum to 1, and a single agent must hold exactly 1. So the bounds are relaxed
    to whatever is actually achievable — `n * lo <= 1 <= n * hi` always holds
    afterwards, which is exactly the condition that makes the projection below
    solvable.

    The Phase 7 gate caught this by running the invariants over 1, 2, 3, 8, 40
    and 150 agents. On a hand-picked eight-agent example the bounds are
    comfortably feasible and nothing looks wrong.
    """
    return min(MIN_WEIGHT, 1.0 / n), max(MAX_WEIGHT, 1.0 / n)


def _project(weights: Mapping[str, float]) -> tuple[dict[str, float], list[str]]:
    """
    Project raw weights onto the simplex, subject to the floor and the cap.

    Solved by bisection on a single scale factor: find theta such that

        sum_i clamp(w_i * theta, lo, hi) = 1

    That sum is monotone non-decreasing in theta, and the relaxed bounds
    guarantee it is <= 1 at theta = 0 and >= 1 as theta grows — so a solution
    exists and bisection finds it.

    The obvious alternative — clamp, then renormalise — is what this replaced,
    and it is wrong in a way that is easy to miss: renormalising *after*
    clamping scales the clamped values too, pushing them straight back through
    the bound they were just pulled to. The gate saw weights of 0.0044 against
    a floor of 0.005.

    Scaling by a single factor also preserves invariant 3 for free: `clamp` is
    monotone in its argument, so a larger raw weight can never end up smaller
    than a smaller one.

    Returns the projected weights and the agents that ended up on a bound.
    """
    if not weights:
        return {}, []

    n = len(weights)
    lo, hi = _bounds(n)

    raw = {k: max(0.0, float(v)) for k, v in weights.items()}
    if math.fsum(raw.values()) <= 0.0 or any(
        not math.isfinite(v) for v in raw.values()
    ):
        # Every weight underflowed, or one went non-finite. The update carries
        # no usable information, so it must not pick a winner.
        return uniform(list(raw)), sorted(raw)

    def total_at(theta: float) -> float:
        return math.fsum(min(hi, max(lo, w * theta)) for w in raw.values())

    # Bracket. total_at(0) == n * lo <= 1, so only the upper end needs finding.
    high = 1.0
    for _ in range(2000):
        if total_at(high) >= 1.0:
            break
        high *= 2.0
    low = 0.0

    for _ in range(200):
        mid = (low + high) / 2.0
        if total_at(mid) < 1.0:
            low = mid
        else:
            high = mid
    theta = (low + high) / 2.0

    projected = {k: min(hi, max(lo, w * theta)) for k, w in raw.items()}
    clamped = sorted(
        k for k, v in projected.items()
        if v <= lo + 1e-12 or v >= hi - 1e-12
    )

    # Bisection lands within ~1e-16 of 1. Absorb the remainder into the largest
    # unclamped agent, which cannot push it through a bound at that scale, so
    # the sum is exact rather than nearly exact.
    residual = 1.0 - math.fsum(projected.values())
    free = [k for k in projected if k not in set(clamped)]
    if free and abs(residual) > 0:
        target = max(free, key=lambda k: projected[k])
        projected[target] = min(hi, max(lo, projected[target] + residual))

    return projected, clamped


def update(
    previous: Mapping[str, float],
    rewards: Mapping[str, float],
    *,
    eta: float = DEFAULT_ETA,
    step: int = 0,
) -> AllocationRound:
    """
    One multiplicative-weights step.

    `rewards` are on [0, 1] — the IRIS Score divided by 100. An agent absent
    from `rewards` has produced no new evidence this round and keeps its weight
    unchanged *before* normalisation, which is not the same as being rewarded
    zero: no evidence is not bad evidence, and treating the two alike would
    punish an agent for a quiet week.
    """
    if eta <= 0:
        raise ValueError(f"eta must be positive, got {eta}")
    if not previous:
        return AllocationRound(step=step, eta=eta, allocations=[], clamped=[])

    raw: dict[str, float] = {}
    for agent_id, weight in previous.items():
        reward = rewards.get(agent_id)
        if reward is None:
            raw[agent_id] = weight
            continue
        if not math.isfinite(reward):
            raise ValueError(f"reward for {agent_id} is {reward}")
        if not 0.0 <= reward <= 1.0:
            raise ValueError(
                f"reward for {agent_id} is {reward}, outside [0, 1] — "
                f"an IRIS Score must be divided by 100 before it gets here"
            )
        exponent = max(-MAX_EXPONENT, min(MAX_EXPONENT, eta * reward))
        raw[agent_id] = weight * math.exp(exponent)

    projected, clamped = _project(raw)

    return AllocationRound(
        step=step,
        eta=eta,
        allocations=[
            Allocation(
                agent_id=agent_id,
                weight=projected[agent_id],
                score=rewards.get(agent_id),
                previous=previous[agent_id],
            )
            for agent_id in sorted(projected)
        ],
        clamped=clamped,
    )


def check_invariants(round_: AllocationRound, tolerance: float = 1e-9) -> list[str]:
    """
    The four §7 invariants, checked against a computed round.

    Returned as a list of violations rather than raised, so a caller can decide
    whether a violation is fatal — and so the Phase 7 gate can report *which*
    invariant broke rather than just that something did.
    """
    violations: list[str] = []
    weights = [a.weight for a in round_.allocations]
    if not weights:
        return violations

    total = math.fsum(weights)
    if abs(total - 1.0) > tolerance:
        violations.append(f"1. weights sum to {total}, not 1")

    if any(w < 0 for w in weights):
        violations.append("2. a weight is negative")
    if any(not math.isfinite(w) for w in weights):
        violations.append("2. a weight is not finite")

    scored = [a for a in round_.allocations if a.score is not None]
    for a in scored:
        for b in scored:
            # Same starting weight, better score, less weight afterwards.
            if (
                abs(a.previous - b.previous) < tolerance
                and a.score > b.score + tolerance
                and a.weight < b.weight - tolerance
                and a.agent_id not in round_.clamped
                and b.agent_id not in round_.clamped
            ):
                violations.append(
                    f"3. {a.agent_id} scored {a.score:.3f} but holds "
                    f"{a.weight:.4f} against {b.agent_id}'s {b.weight:.4f} "
                    f"at score {b.score:.3f}"
                )

    if any(w <= 0.0 for w in weights):
        violations.append("4. a weight reached 0, which is absorbing")
    if any(w >= 1.0 for w in weights) and len(weights) > 1:
        violations.append("4. one agent holds the entire vault")

    return violations
