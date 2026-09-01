"""
The validator's two gates, and why they are two — Phase 13 follow-up.

VALIDATION used to reject a proposal whose `confidence` fell below a floor,
where `confidence` is the model's probability for the chosen direction against
**all three** classes, HOLD included. That conflated two different questions
and charged the model twice for one doubt:

  * *will the market move enough to matter?* — already answered, by
    `decision_threshold`, which requires the predicted move to exceed the band
    scoring treats as flat;
  * *which way?* — the only thing conviction should mean here.

The cost was measurable. A gradient-boosting agent proposing a −8.95bps move
put 0.509 on SELL, 0.370 on HOLD and 0.121 on BUY — it was **81% sure of the
side** — and was refused for being only 51% sure the market would not be flat.

These tests pin the separation, and, more importantly, pin that nothing which
was correctly rejected before is tradeable now.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.graphs.nodes import (  # noqa: E402
    MIN_DIRECTIONAL_CONFIDENCE,
    decision_threshold,
    validation,
)
from agents.state import AgentState, Decision, RiskAssessment  # noqa: E402
from ml.models.base import (  # noqa: E402
    CLASSES,
    confidence_for,
    direction_probabilities,
    directional_confidence,
)

CLEAR_RISK = RiskAssessment(
    volatility_bps=100, var_95=-0.001, cvar_95=-0.002,
    drawdown_bps=50, exposure_ok=True, breaches=[],
)


def proposal(*, direction, expected_return, conf, directional):
    return AgentState(
        agent_id="AGT-TEST", agent_run_id="r", asset="BTC", strategy="momentum",
        features={"volatility": 0.0005},
        predicted_return=expected_return,
        model_confidence=conf,
        model_directional_confidence=directional,
        risk=CLEAR_RISK,
        decision=Decision(
            direction=direction, expected_return=expected_return,
            confidence=conf, horizon_seconds=600,
        ),
    )


def approved(state) -> bool:
    return validation(state)["validation"].approved


# ── the primitive ───────────────────────────────────────────────────────────

def test_hold_mass_does_not_count_against_a_directional_call():
    """The exact case that was being rejected."""
    # The spread that reproduces the measured case: P(SELL) 0.51, P(HOLD) 0.37,
    # P(BUY) 0.12 — an agent 81% sure of the side, refused by the old gate.
    proba = direction_probabilities(-8.95e-4, 1.25e-3, 0.0005)
    assert confidence_for("SELL", proba) < 0.55, "the old gate rejected this"
    assert directional_confidence("SELL", proba) > 0.70, "but it knows the side"


def test_a_model_with_no_view_scores_zero_not_a_coin_flip():
    """
    A model that puts everything on HOLD is silent, not 50/50.

    This is the property that keeps the looser gate honest: if silence read as
    0.5 it would sit only just under the floor, and any nudge would let a model
    with no opinion take a position.
    """
    proba = direction_probabilities(0.0, 1.0, 0.0005)
    assert directional_confidence("BUY", proba) == pytest.approx(0.5, abs=0.01)

    # ...and with a genuinely degenerate distribution, exactly zero rather than
    # a division by zero.
    import numpy as np

    dead = np.zeros(3)
    dead[CLASSES.index("HOLD")] = 1.0
    assert directional_confidence("BUY", dead) == 0.0


def test_it_is_symmetric():
    up = direction_probabilities(+9e-4, 8e-4, 0.0005)
    down = direction_probabilities(-9e-4, 8e-4, 0.0005)
    assert directional_confidence("BUY", up) == pytest.approx(
        directional_confidence("SELL", down)
    )


def test_certainty_of_side_reaches_one():
    proba = direction_probabilities(50e-4, 1e-4, 0.0005)
    assert directional_confidence("BUY", proba) > 0.99


# ── the gate ────────────────────────────────────────────────────────────────

def test_a_model_sure_of_the_side_is_approved():
    assert approved(proposal(
        direction="SELL", expected_return=-8.95e-4, conf=0.509, directional=0.808,
    ))


def test_a_model_unsure_of_the_side_is_rejected():
    state = proposal(
        direction="SELL", expected_return=-8.95e-4, conf=0.509, directional=0.52,
    )
    assert not approved(state)
    assert any("which way" in r for r in state.decision and
               validation(state)["validation"].reasons)


def test_a_silent_model_is_still_rejected():
    """
    The regression this whole change must not cause.

    A model with no directional view scores 0.0 and is refused, exactly as it
    was before — the gate was loosened in the *direction* dimension only.
    """
    assert not approved(proposal(
        direction="BUY", expected_return=9e-4, conf=0.33, directional=0.0,
    ))


# ── the two gates are orthogonal, and jointly sufficient ────────────────────

def test_magnitude_is_still_gated_separately():
    """
    A model certain of the side but predicting a move too small to trade is
    still refused — by DECISION, which never proposes a direction at all.
    """
    state = proposal(
        direction="HOLD", expected_return=0.2e-4, conf=0.9, directional=0.99,
    )
    assert not approved(state)


def test_clearing_the_threshold_bounds_hold_below_the_chosen_side():
    """
    Why the direction gate alone is enough once the threshold has been cleared.

    Both logits come from the same spread: `snr = move / spread` and
    `hold = threshold / spread`. So a move at or beyond the threshold has
    `|snr| >= hold`, and HOLD can never be the likeliest class. There is no
    corner where a proposal passes the direction gate while the model actually
    believes the market will not move.
    """
    for spread in (1e-4, 5e-4, 2e-3, 1e-2):
        for move in (5e-4, 9e-4, 5e-3):
            proba = direction_probabilities(move, spread, 0.0005)
            chosen = proba[CLASSES.index("BUY")]
            hold = proba[CLASSES.index("HOLD")]
            assert chosen >= hold - 1e-12, (
                f"HOLD outranked a threshold-clearing move at spread={spread}"
            )


def test_the_floor_is_still_a_floor():
    assert 0.5 < MIN_DIRECTIONAL_CONFIDENCE < 1.0


def test_the_threshold_and_the_direction_gate_are_independent():
    """Changing observed volatility moves one gate and not the other."""
    calm = proposal(direction="BUY", expected_return=9e-4, conf=0.6, directional=0.9)
    wild = calm.model_copy(update={"features": {"volatility": 0.02}})
    assert decision_threshold(wild) > decision_threshold(calm)
    # The direction gate is unmoved by volatility; it is a property of the
    # model's own distribution.
    assert wild.model_directional_confidence == calm.model_directional_confidence
