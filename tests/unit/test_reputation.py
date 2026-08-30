"""
IRIS Score unit tests — Phase 6 DoD.

DoD: "IRIS Score computed from at least six dimensions with configurable
weights, unit-tested."

Unit, not integration: every test here is a pure function of a constructed
record, so a dimension's behaviour can be pinned without a database. The
database side lives in `tests/integration/test_reputation_db.py`.

The tests are organised around what each dimension is *for*. A dimension that
cannot be moved independently of the others is not a dimension, it is padding
to reach a count of six — so most of these construct a record that is good on
one axis and bad on another, and assert the two are told apart.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.reputation.dimensions import (  # noqa: E402
    DIMENSIONS,
    EVIDENCE_SATURATION,
    Outcome,
    accuracy,
    calibration,
    compute_dimensions,
    consistency,
    conviction,
    evidence,
    magnitude,
    risk_adjusted,
)
from agents.reputation.score import (  # noqa: E402
    DEFAULT_WEIGHTS,
    compute_score,
    leaderboard,
    validate_weights,
)


def o(
    *,
    correct: bool = True,
    confidence: float = 0.7,
    error: float = 0.002,
    score: float = 80.0,
    actual: float = 0.02,
    direction: str = "BUY",
    source: str = "SIMULATION",
) -> Outcome:
    return Outcome(
        direction=direction, expected_return=actual, confidence=confidence,
        actual_return=actual, error=error, direction_correct=correct,
        evaluation_score=score, data_source=source,
    )


# ── the set of dimensions ───────────────────────────────────────────────────

def test_there_are_at_least_six_dimensions():
    assert len(DIMENSIONS) >= 6


def test_every_dimension_is_bounded_and_finite():
    records = [
        [],
        [o()],
        [o(correct=False, error=1e6, actual=-0.9)] * 3,
        [o(actual=0.0, direction="HOLD")] * 10,
        [o(confidence=0.0), o(confidence=1.0)],
    ]
    for record in records:
        for name, fn in DIMENSIONS.items():
            value = fn(record)
            assert math.isfinite(value), f"{name} produced {value}"
            assert 0.0 <= value <= 1.0, f"{name} produced {value}"


def test_compute_dimensions_rejects_an_out_of_range_value(monkeypatch):
    """
    A NaN reaching `reputation_scores.iris_score` would pass the CHECK
    constraint — NaN comparisons are never true, so `BETWEEN 0 AND 100` does
    not reject it — and poison an agent's reputation silently.
    """
    monkeypatch.setitem(DIMENSIONS, "accuracy", lambda _: float("nan"))
    with pytest.raises(ValueError):
        compute_dimensions([o()])


# ── accuracy ────────────────────────────────────────────────────────────────

def test_accuracy_is_the_hit_rate():
    assert accuracy([o(correct=True)] * 3 + [o(correct=False)]) == 0.75
    assert accuracy([]) == 0.0


# ── calibration ─────────────────────────────────────────────────────────────

def test_a_well_calibrated_agent_beats_an_overconfident_one():
    """Being right 60% of the time while claiming 60% is the good case."""
    honest = [o(confidence=0.6, correct=i < 6) for i in range(10)]
    boastful = [o(confidence=0.95, correct=i < 6) for i in range(10)]
    assert calibration(honest) > calibration(boastful)


def test_calibration_is_not_accuracy():
    """
    A modest agent that is right half the time can be better calibrated than a
    strong agent that is overconfident. If this failed, calibration would be a
    second copy of accuracy wearing a different name.
    """
    modest = [o(confidence=0.5, correct=i % 2 == 0) for i in range(10)]
    strong = [o(confidence=1.0, correct=i < 8) for i in range(10)]
    assert accuracy(modest) < accuracy(strong)
    assert calibration(modest) > calibration(strong)


def test_calibration_bins_rather_than_averaging():
    """
    Overconfidence on strong calls must not cancel against underconfidence on
    weak ones. On a single average this record looks perfectly calibrated; it
    is wrong in both directions.
    """
    record = (
        [o(confidence=0.9, correct=False) for _ in range(10)]     # says 90%, hits 0%
        + [o(confidence=0.1, correct=True) for _ in range(10)]    # says 10%, hits 100%
    )
    assert calibration(record) < 0.3


def test_an_underconfident_agent_is_also_miscalibrated():
    """Calibration is a two-sided measure, not a penalty for boasting."""
    shy = [o(confidence=0.2, correct=True) for _ in range(10)]
    assert calibration(shy) < 0.5


# ── magnitude ───────────────────────────────────────────────────────────────

def test_magnitude_separates_precision_from_direction():
    """
    Both records call every direction correctly. One sizes the move well and
    one does not, and magnitude is the only dimension that can tell them apart.
    """
    precise = [o(correct=True, error=0.0005)] * 10
    sloppy = [o(correct=True, error=0.20)] * 10
    assert accuracy(precise) == accuracy(sloppy) == 1.0
    assert magnitude(precise) > magnitude(sloppy)


# ── consistency ─────────────────────────────────────────────────────────────

def test_consistency_separates_two_records_with_the_same_mean():
    """
    100/0 alternating and a steady 50 have identical means and are not the same
    agent. Without this dimension the score could not say so.
    """
    swinging = [o(score=100.0 if i % 2 else 0.0) for i in range(10)]
    steady = [o(score=50.0) for _ in range(10)]
    assert consistency(steady) > consistency(swinging)


def test_a_single_prediction_has_no_spread_to_measure():
    """Neutral, not perfect: `evidence` is what discounts a short record."""
    assert consistency([o()]) == 0.5


# ── risk-adjusted return ────────────────────────────────────────────────────

def test_leverage_does_not_buy_a_better_risk_adjusted_score():
    """
    Doubling every position doubles the return *and* the volatility. An agent
    that only took more risk must not score higher — that is the whole point of
    dividing by its own volatility.
    """
    modest = [o(actual=0.01 * (1 + (i % 3))) for i in range(20)]
    levered = [o(actual=0.02 * (1 + (i % 3))) for i in range(20)]
    assert risk_adjusted(levered) == pytest.approx(risk_adjusted(modest), abs=0.05)


def test_a_losing_agent_scores_below_a_winning_one():
    winner = [o(direction="BUY", actual=0.01 + 0.001 * (i % 4)) for i in range(20)]
    loser = [o(direction="BUY", actual=-0.01 - 0.001 * (i % 4)) for i in range(20)]
    assert risk_adjusted(winner) > risk_adjusted(loser)


def test_a_correct_short_earns_the_fall():
    """A SELL that was right made money; the sign of the return has to flip."""
    short = [o(direction="SELL", actual=-0.02 - 0.001 * (i % 3)) for i in range(20)]
    long_ = [o(direction="BUY", actual=-0.02 - 0.001 * (i % 3)) for i in range(20)]
    assert risk_adjusted(short) > risk_adjusted(long_)


def test_a_near_constant_return_does_not_produce_an_unbounded_score():
    """
    Identical returns give a volatility of ~0. Without the floor this divides
    by nothing and posts an infinite ratio — the classic way a Sharpe ratio
    lies about a small, lucky sample.
    """
    assert 0.0 <= risk_adjusted([o(actual=0.05)] * 20) <= 1.0


# ── conviction ──────────────────────────────────────────────────────────────

def test_an_agent_that_only_holds_has_no_conviction():
    """Never badly wrong, never worth anything — it occupies a slot and returns nothing."""
    assert conviction([o(direction="HOLD")] * 10) == 0.0
    assert conviction([o(direction="BUY")] * 10) == 1.0


def test_conviction_is_not_accuracy():
    """An agent can be fully committed and fully wrong."""
    reckless = [o(direction="BUY", correct=False)] * 10
    assert conviction(reckless) == 1.0 and accuracy(reckless) == 0.0


# ── evidence ────────────────────────────────────────────────────────────────

def test_evidence_saturates_and_never_reaches_one():
    values = [evidence([o()] * n) for n in (1, 5, 20, 100, 1000)]
    assert values == sorted(values), "more evidence must never mean less"
    assert values[-1] < 1.0, "a record can always be tested further"
    assert evidence([o()] * EVIDENCE_SATURATION) == pytest.approx(0.5)


def test_evidence_is_not_one_of_the_weighted_dimensions():
    """
    It multiplies the score rather than being averaged into it. As a seventh
    weighted dimension at 0.10 it could not discount a sample of one: every
    other dimension maxes out on a single prediction, and that record scored
    79.2. See agents/reputation/dimensions.
    """
    assert "evidence" not in DIMENSIONS


# ── the score ───────────────────────────────────────────────────────────────

def test_an_untested_agent_has_no_score():
    """
    Not 0, not 50 — None. A default would let an agent that has never been
    tested outrank one with a proven bad record, and Phase 7 allocates capital
    by that ranking.
    """
    assert compute_score("A", []) is None


def test_one_lucky_prediction_does_not_produce_a_high_score():
    flawless_once = compute_score("A", [o(correct=True, error=0.0, score=100.0)])
    assert flawless_once.quality > 70.0, "the record itself is excellent"
    assert flawless_once.value < 20.0, "but it has barely been tested"


def test_the_same_quality_over_a_longer_record_scores_higher():
    short = compute_score("A", [o()] * 3)
    long_ = compute_score("A", [o()] * 300)
    assert long_.value > short.value
    assert long_.quality == pytest.approx(short.quality, abs=6.0)


def test_the_score_is_quality_times_evidence():
    s = compute_score("A", [o()] * 40)
    assert s.value == pytest.approx(s.quality * s.evidence, abs=1e-3)


def test_a_better_record_scores_higher_at_equal_length():
    good = compute_score("A", [o(correct=True, error=0.001, score=90.0)] * 40)
    bad = compute_score("A", [o(correct=False, error=0.05, score=20.0)] * 40)
    assert good.value > bad.value


def test_the_score_is_bounded():
    for record in ([o()], [o()] * 5000, [o(correct=False, error=1e9)] * 10):
        s = compute_score("A", record)
        assert 0.0 <= s.value <= 100.0


# ── configurable weights ────────────────────────────────────────────────────

def test_changing_the_weights_changes_the_score():
    record = [o(correct=i % 4 != 0, confidence=0.9, error=0.001) for i in range(40)]
    base = compute_score("A", record)
    tilted = compute_score("A", record, weights={**{k: 0.0 for k in DEFAULT_WEIGHTS},
                                                 "accuracy": 1.0})
    assert base.value != tilted.value


@pytest.mark.parametrize(
    "weights,why",
    [
        ({k: v for k, v in DEFAULT_WEIGHTS.items() if k != "accuracy"},
         "a missing dimension would be silently weighted zero"),
        ({**DEFAULT_WEIGHTS, "vibes": 0.0},
         "an unknown dimension would be silently ignored"),
        ({k: v * 2 for k, v in DEFAULT_WEIGHTS.items()},
         "weights that do not sum to 1 shift every score by a constant factor"),
        ({**DEFAULT_WEIGHTS, "accuracy": -0.28},
         "a negative weight rewards being wrong"),
    ],
)
def test_an_invalid_weighting_is_rejected(weights, why):
    with pytest.raises(ValueError):
        validate_weights(weights)


def test_the_default_weighting_is_valid():
    assert validate_weights(DEFAULT_WEIGHTS) == DEFAULT_WEIGHTS


def test_the_weighting_used_is_returned_with_the_score():
    """`reputation_scores` stores it so a historical score stays re-derivable."""
    s = compute_score("A", [o()] * 10)
    recomputed = 100.0 * math.fsum(
        s.dimensions[name] * w for name, w in s.weights.items()
    )
    assert recomputed == pytest.approx(s.quality, abs=1e-3)


# ── the leaderboard ─────────────────────────────────────────────────────────

def test_unscored_agents_are_unranked_not_ranked_last():
    scores = {
        "GOOD": compute_score("GOOD", [o(correct=True)] * 40),
        "BAD": compute_score("BAD", [o(correct=False, error=0.1)] * 40),
        "UNTESTED": compute_score("UNTESTED", []),
    }
    ranked = [s.agent_id for s in leaderboard(scores)]
    assert ranked == ["GOOD", "BAD"]
    assert "UNTESTED" not in ranked


def test_a_score_names_its_provenance():
    s = compute_score("A", [o()] * 5, data_source="TESTNET")
    assert s.data_source == "TESTNET"
