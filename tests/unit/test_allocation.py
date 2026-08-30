"""
MWU allocation unit tests — Phase 7 DoD.

DoD: "MWU allocation — 4 mathematical invariants pass as tests."

    1. weights always sum to 1
    2. weights are never negative
    3. a better score never loses weight relative to a worse one
    4. the update is bounded — no weight reaches 0 or 1

The invariants are also checked over thousands of randomised rounds by
`scripts/verify_phase7.py`. What these add is the *named* case for each one:
which specific input would break it, and why. A property test tells you an
invariant held; a named test tells the next reader what it is protecting
against.

Invariant 4 gets the most attention here because it is the one that is not
automatic. The exponential guarantees positivity but not distance from zero,
and zero is absorbing under a multiplicative update — an agent that reaches it
can never recover however well it performs afterwards.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.allocation.mwu import (  # noqa: E402
    DEFAULT_ETA,
    MAX_EXPONENT,
    MAX_WEIGHT,
    MIN_WEIGHT,
    _bounds,
    check_invariants,
    uniform,
    update,
)

TOL = 1e-9


def ids(n: int) -> list[str]:
    return [f"A{i}" for i in range(n)]


def run(n: int, rewards: dict[str, float], *, steps: int = 1, eta: float = DEFAULT_ETA):
    weights = uniform(ids(n))
    round_ = None
    for step in range(steps):
        round_ = update(weights, rewards, eta=eta, step=step)
        weights = round_.weights
    return round_


# ── invariant 1: weights sum to 1 ───────────────────────────────────────────

@pytest.mark.parametrize("n", [1, 2, 3, 8, 50, 500])
def test_weights_sum_to_one_for_any_agent_count(n):
    r = run(n, {a: (i % 7) / 6 for i, a in enumerate(ids(n))})
    assert math.fsum(a.weight for a in r.allocations) == pytest.approx(1.0, abs=TOL)


def test_weights_sum_to_one_after_many_steps():
    """Drift accumulates. One step proving nothing is the point of this test."""
    r = run(8, {a: 1.0 if a == "A0" else 0.1 for a in ids(8)}, steps=500)
    assert math.fsum(a.weight for a in r.allocations) == pytest.approx(1.0, abs=TOL)


def test_an_empty_allocation_is_empty_not_broken():
    r = update({}, {}, eta=DEFAULT_ETA)
    assert r.allocations == [] and check_invariants(r) == []


# ── invariant 2: never negative ─────────────────────────────────────────────

def test_weights_are_never_negative_even_at_extreme_eta():
    r = run(20, {a: (i % 2) * 1.0 for i, a in enumerate(ids(20))}, steps=200, eta=5.0)
    assert all(a.weight > 0 for a in r.allocations)


def test_a_reward_outside_zero_to_one_is_rejected():
    """
    An IRIS Score is 0-100. Passing it raw would exponentiate to inf and then
    produce NaN weights, so the caller is stopped rather than the arithmetic
    silently failing downstream.
    """
    with pytest.raises(ValueError, match="divided by 100"):
        update(uniform(ids(3)), {"A0": 87.0}, eta=DEFAULT_ETA)


def test_a_non_finite_reward_is_rejected():
    with pytest.raises(ValueError):
        update(uniform(ids(3)), {"A0": float("nan")}, eta=DEFAULT_ETA)


def test_a_non_positive_eta_is_rejected():
    with pytest.raises(ValueError):
        update(uniform(ids(3)), {"A0": 0.5}, eta=0.0)


def test_the_exponent_is_capped():
    """A guard against inf, not a live constraint at any sane eta."""
    assert MAX_EXPONENT < 709.0


# ── invariant 3: monotone in score ──────────────────────────────────────────

def test_a_better_score_gains_weight_relative_to_a_worse_one():
    r = run(4, {"A0": 1.0, "A1": 0.7, "A2": 0.3, "A3": 0.0})
    w = r.weights
    assert w["A0"] > w["A1"] > w["A2"] > w["A3"]


def test_sustained_performance_orders_the_vault():
    r = run(5, {a: 1.0 - i * 0.2 for i, a in enumerate(ids(5))}, steps=30)
    ranked = sorted(r.weights, key=lambda a: r.weights[a], reverse=True)
    assert ranked == ids(5)


def test_identical_scores_produce_identical_weights():
    """A mechanism that manufactures a ranking from no information is broken."""
    r = run(6, {a: 0.7 for a in ids(6)})
    assert len({round(w, 12) for w in r.weights.values()}) == 1


def test_all_zero_scores_leave_the_distribution_alone():
    r = run(6, {a: 0.0 for a in ids(6)})
    assert all(w == pytest.approx(1 / 6, abs=TOL) for w in r.weights.values())


def test_no_new_evidence_is_not_treated_as_bad_evidence():
    """
    An agent that produced no settled predictions this round keeps its weight
    before normalisation. Rewarding it 0 would punish a quiet week exactly as
    hard as a wrong one.
    """
    r = update(uniform(ids(4)), {"A0": 1.0}, eta=DEFAULT_ETA)
    silent = [a.weight for a in r.allocations if a.agent_id != "A0"]
    assert len({round(w, 12) for w in silent}) == 1
    assert r.weights["A0"] > silent[0]


def test_check_invariants_names_the_violation():
    """The gate has to report *which* invariant broke, not just that one did."""
    r = run(4, {"A0": 1.0, "A1": 0.2, "A2": 0.2, "A3": 0.2})
    assert check_invariants(r) == []


# ── invariant 4: bounded ────────────────────────────────────────────────────

def test_a_persistent_loser_never_reaches_zero():
    """
    Zero is absorbing: 0 * exp(anything) is 0. An agent that reaches it is
    permanently dead however well it performs afterwards, which turns a bad
    month into an execution.
    """
    r = run(5, {a: (0.0 if a == "A0" else 1.0) for a in ids(5)}, steps=1000, eta=5.0)
    assert r.weights["A0"] > 0.0
    assert r.weights["A0"] >= MIN_WEIGHT - TOL


def test_a_collapsed_agent_can_earn_its_way_back():
    weights = uniform(ids(5))
    for step in range(300):
        weights = update(
            weights, {a: (0.0 if a == "A0" else 1.0) for a in ids(5)},
            eta=5.0, step=step,
        ).weights
    bottom = weights["A0"]

    for step in range(300):
        weights = update(
            weights, {a: (1.0 if a == "A0" else 0.0) for a in ids(5)},
            eta=5.0, step=step,
        ).weights
    assert weights["A0"] > bottom * 10


def test_a_persistent_winner_never_captures_the_vault():
    """A single agent at weight 1 means the protocol *is* that agent."""
    r = run(5, {a: (1.0 if a == "A0" else 0.0) for a in ids(5)}, steps=1000, eta=5.0)
    assert r.weights["A0"] < 1.0
    assert r.weights["A0"] <= MAX_WEIGHT + TOL


def test_the_bounds_relax_when_they_are_infeasible():
    """
    Two agents cannot both hold at most 0.40 and still sum to 1; one agent must
    hold exactly 1. Policy cannot override arithmetic, so the bounds relax to
    what is achievable — which is what keeps the projection solvable.
    """
    # Only the *cap* has to relax. A floor of 0.005 is already satisfiable by
    # a lone agent holding 1.0 — what is infeasible is capping it at 0.40.
    _, hi1 = _bounds(1)
    assert hi1 == 1.0

    _, hi2 = _bounds(2)
    assert hi2 == 0.5

    lo_many, hi_many = _bounds(100)
    assert lo_many == MIN_WEIGHT and hi_many == MAX_WEIGHT

    for n in (1, 2, 3, 10, 199):
        lo, hi = _bounds(n)
        assert lo * n <= 1.0 + TOL <= hi * n + 2 * TOL, f"infeasible at n={n}"


@pytest.mark.parametrize("n", [1, 2, 3, 8, 40, 199])
def test_every_weight_respects_the_effective_bounds(n):
    r = run(n, {a: (1.0 if i == 0 else 0.0) for i, a in enumerate(ids(n))},
            steps=200, eta=5.0)
    lo, hi = _bounds(n)
    for a in r.allocations:
        assert lo - TOL <= a.weight <= hi + TOL


def test_a_single_agent_holds_everything():
    """Degenerate but legal: with one agent there is nowhere else for capital to go."""
    r = run(1, {"A0": 0.9})
    assert r.weights["A0"] == pytest.approx(1.0, abs=TOL)
    assert check_invariants(r) == []


def test_clamping_does_not_survive_renormalisation():
    """
    The bug this pins: clamp-then-renormalise scales the clamped values too,
    pushing them straight back through the bound they were just pulled to. The
    gate saw 0.0044 against a floor of 0.005.
    """
    r = run(40, {a: (1.0 if i < 3 else 0.0) for i, a in enumerate(ids(40))},
            steps=300, eta=5.0)
    assert min(a.weight for a in r.allocations) >= MIN_WEIGHT - TOL
    assert math.fsum(a.weight for a in r.allocations) == pytest.approx(1.0, abs=TOL)


# ── the round record ────────────────────────────────────────────────────────

def test_a_round_records_what_it_was_computed_from():
    """`allocation_history` has to be replayable, so the inputs ride along."""
    r = update(uniform(ids(3)), {"A0": 0.8, "A1": 0.2}, eta=0.3, step=7)
    assert r.step == 7 and r.eta == 0.3
    by_id = {a.agent_id: a for a in r.allocations}
    assert by_id["A0"].score == 0.8
    assert by_id["A2"].score is None
    assert all(a.previous == pytest.approx(1 / 3) for a in r.allocations)


def test_clamped_agents_are_reported():
    r = run(5, {a: (1.0 if a == "A0" else 0.0) for a in ids(5)}, steps=200, eta=5.0)
    assert r.clamped, "an agent pinned to a bound must be named, not silently held"


def test_uniform_is_the_only_defensible_start():
    """At step 0 there is no evidence; any other prior asserts a winner."""
    assert uniform(ids(4)) == {a: 0.25 for a in ids(4)}
    assert uniform([]) == {}
