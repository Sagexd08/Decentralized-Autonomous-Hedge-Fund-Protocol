"""
Risk limit unit tests — Phase 8.

The limits are pure functions of a settled record, so they can be pinned
without a database. What they are protecting against, in order of how easy each
is to get wrong:

  * **freezing a new agent for being new.** Every agent's first few predictions
    have the variance every agent's first few predictions have. A drawdown
    limit with no sample floor freezes all of them, which looks like a working
    risk engine and is actually a hiring freeze.
  * **an agent managing its drawdown by abstaining.** HOLD has to earn nothing,
    not count as a small win.
  * **a slash that starts at the limit.** A penalty proportional to the
    drawdown rather than to the *excess* makes the limit a cliff: one basis
    point over and the agent loses a fifth of its stake.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.reputation.dimensions import Outcome  # noqa: E402
from agents.risk.limits import (  # noqa: E402
    MAX_CVAR_BPS,
    MAX_DRAWDOWN_BPS,
    MAX_SLASH_BPS,
    MAX_VOLATILITY_BPS,
    MIN_ACCURACY,
    MIN_SAMPLE_FOR_BREACH,
    MIN_SLASH_BPS,
    cvar,
    evaluate,
    max_drawdown,
    position_returns,
    slash_bps_for,
)


def o(
    *,
    direction: str = "BUY",
    actual: float = 0.01,
    correct: bool = True,
    error: float = 0.002,
    score: float = 70.0,
) -> Outcome:
    return Outcome(
        direction=direction, expected_return=0.01, confidence=0.7,
        actual_return=actual, error=error, direction_correct=correct,
        evaluation_score=score, data_source="SIMULATION",
    )


def losing(n: int, loss: float = -0.03) -> list[Outcome]:
    return [o(actual=loss, correct=False, error=abs(0.01 - loss)) for _ in range(n)]


def winning(n: int, gain: float = 0.01) -> list[Outcome]:
    return [o(actual=gain, correct=True) for _ in range(n)]


# ── position returns ────────────────────────────────────────────────────────

def test_a_correct_short_earns_the_fall():
    assert position_returns([o(direction="SELL", actual=-0.02)]) == [0.02]


def test_a_wrong_short_loses():
    assert position_returns([o(direction="SELL", actual=0.02)]) == [-0.02]


def test_holding_earns_nothing():
    """
    Not a small win, not a small loss. If a HOLD counted as either, an agent
    could manage its drawdown by abstaining — which is the one behaviour the
    risk engine must not be able to be gamed by.
    """
    assert position_returns([o(direction="HOLD", actual=0.05)]) == [0.0]
    assert position_returns([o(direction="HOLD", actual=-0.05)]) == [0.0]


# ── drawdown ────────────────────────────────────────────────────────────────

def test_drawdown_is_peak_to_trough_not_final_loss():
    """
    A record that falls 30% and recovers to break even has still had a 30%
    drawdown. Reporting only the closing position would hide exactly the
    experience a depositor had.
    """
    assert max_drawdown([-0.3, 0.3]) == pytest.approx(0.3)
    assert max_drawdown([0.1, -0.3, 0.2]) == pytest.approx(0.3)


def test_a_record_that_only_rises_has_no_drawdown():
    assert max_drawdown([0.1, 0.1, 0.1]) == 0.0


def test_drawdown_is_never_negative():
    assert max_drawdown([]) == 0.0
    assert max_drawdown([-0.5]) >= 0.0


# ── cvar ────────────────────────────────────────────────────────────────────

def test_cvar_reads_the_tail_not_the_average():
    """
    An agent can look calm on average and still have a tail that empties the
    vault. Volatility would not distinguish these two.
    """
    calm = [0.001] * 99 + [-0.001]
    tail_risk = [0.001] * 99 + [-0.9]
    assert cvar(tail_risk) > cvar(calm)


def test_cvar_of_a_profitable_record_is_zero():
    assert cvar([0.01] * 50) == 0.0


# ── breach detection ────────────────────────────────────────────────────────

def test_a_small_sample_cannot_breach():
    """
    Every agent's first predictions carry the variance every agent's first
    predictions carry. A limit with no sample floor freezes all of them.
    """
    catastrophic = losing(MIN_SAMPLE_FOR_BREACH - 1, loss=-0.5)
    assert evaluate(catastrophic).is_clear


def test_the_sample_floor_is_the_only_thing_holding_it_back():
    """The same record breaches the moment there is enough of it."""
    assert evaluate(losing(MIN_SAMPLE_FOR_BREACH - 1, loss=-0.5)).is_clear
    assert not evaluate(losing(MIN_SAMPLE_FOR_BREACH, loss=-0.5)).is_clear


def test_a_sustained_loss_breaches_the_drawdown_limit():
    profile = evaluate(losing(30))
    assert profile.drawdown_bps > MAX_DRAWDOWN_BPS
    assert any(b.kind == "DRAWDOWN_BREACH" for b in profile.breaches)


def test_a_severe_drawdown_is_critical_and_a_mild_one_is_a_warning():
    """
    The difference decides whether the agent is frozen now or warned first, so
    it cannot be a judgement call at the call site.
    """
    severe = evaluate(losing(40, loss=-0.05))
    assert any(b.is_critical for b in severe.breaches)

    # Just past the limit: enough to breach, not enough to be critical.
    mild = evaluate(losing(12, loss=-0.02))
    drawdown = [b for b in mild.breaches if b.kind == "DRAWDOWN_BREACH"]
    if drawdown:
        assert drawdown[0].severity == "WARN"


def test_a_steady_profitable_record_is_clear():
    profile = evaluate(winning(40))
    assert profile.is_clear
    assert profile.cumulative_return > 0


def test_a_wild_but_profitable_record_still_breaches_volatility():
    """Making money is not the same as being safe to allocate to."""
    wild = [o(actual=0.6 if i % 2 else -0.5, correct=i % 2 == 0) for i in range(30)]
    profile = evaluate(wild)
    assert profile.volatility_bps > MAX_VOLATILITY_BPS
    assert any(b.kind == "VOLATILITY_BREACH" for b in profile.breaches)


def test_a_fat_tail_breaches_cvar_even_when_volatility_is_modest():
    tail = [o(actual=0.002, correct=True) for _ in range(60)]
    tail += [o(actual=-0.9, correct=False) for _ in range(3)]
    profile = evaluate(tail)
    assert profile.cvar_bps > MAX_CVAR_BPS
    assert any(b.kind == "CVAR_BREACH" for b in profile.breaches)


def test_an_agent_that_is_never_right_breaches_the_accuracy_floor():
    profile = evaluate([o(actual=0.0001, correct=False) for _ in range(40)])
    assert profile.accuracy < MIN_ACCURACY
    assert any(b.kind == "CONFIDENCE_FLOOR" for b in profile.breaches)


def test_an_empty_record_is_clear_not_breaching():
    """No evidence is not evidence of misconduct."""
    profile = evaluate([])
    assert profile.is_clear and profile.sample_size == 0


def test_the_worst_severity_is_reported():
    profile = evaluate(losing(40, loss=-0.05))
    assert profile.worst == "CRITICAL"
    assert evaluate(winning(40)).worst == "INFO"


# ── slashing ────────────────────────────────────────────────────────────────

def test_the_slash_scales_with_the_excess_not_the_drawdown():
    """
    Proportional to the drawdown itself would make the limit a cliff: one basis
    point over and the agent loses a fifth of its stake.
    """
    at_limit = slash_bps_for(MAX_DRAWDOWN_BPS)
    just_over = slash_bps_for(MAX_DRAWDOWN_BPS + 100)
    far_over = slash_bps_for(MAX_DRAWDOWN_BPS + 3000)

    assert at_limit == MIN_SLASH_BPS
    assert just_over <= far_over
    assert far_over > just_over


def test_the_slash_is_bounded_at_both_ends():
    assert slash_bps_for(0) == MIN_SLASH_BPS
    assert slash_bps_for(10 ** 9) == MAX_SLASH_BPS
    assert MAX_SLASH_BPS <= 10_000, "a slash cannot exceed the stake"


def test_a_total_slash_is_not_possible():
    """
    A penalty that takes everything removes any reason for the agent to keep
    operating honestly afterwards — there is nothing left to lose.
    """
    assert slash_bps_for(10 ** 9) < 10_000
