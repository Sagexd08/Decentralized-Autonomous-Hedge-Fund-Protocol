"""
Scoring a settled prediction — Phase 5, feeding the IRIS Score in Phase 6.

A prediction makes three claims at once, and a score that collapses them into
one number has to be explicit about how:

  * **direction** — the claim that decides whether capital moves at all;
  * **magnitude** — the claim that sizes the position;
  * **confidence** — the claim about how much to trust the other two.

The weighting below says direction dominates, magnitude matters, and confidence
is a multiplier that cuts both ways. That last part is the piece worth arguing
for: a model rewarded only for being right learns to be confident always. Here,
being confidently wrong scores *below* being uncertainly wrong, so calibration
is something an agent can lose points for — which is what makes the calibration
dimension in section 12 measurable rather than decorative.

The output is 0-100, matching the IRIS Score scale so Phase 6 aggregates like
with like. 50 is the score of a prediction that carried no information: wrong
direction, at stated indifference.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Weights. Named, because a magic 0.6 buried in an expression is a policy
# decision disguised as arithmetic.
W_DIRECTION = 0.60
W_MAGNITUDE = 0.40

# The confidence multiplier's reach. At full confidence a correct call earns
# CONFIDENCE_SWING more of the remaining headroom and a wrong one loses that
# much — so a confident mistake is punished harder than a hedged one.
CONFIDENCE_SWING = 0.35

# Magnitude error is scored relative to this. An error of one MAGNITUDE_SCALE
# (1%) scores half marks on the magnitude component; the curve is smooth, so
# there is no cliff an agent can sit just inside of.
MAGNITUDE_SCALE = 0.01

# HOLD is a real prediction — "this will not move" — and is judged against the
# same band the decision layer uses to call a move worth taking.
HOLD_BAND = 0.0005


@dataclass(frozen=True)
class Score:
    """A scored prediction, with its parts kept so a score can be explained."""

    value: float                # 0-100
    direction_correct: bool
    error: float                # |predicted - actual|, fractional
    direction_component: float  # 0-1
    magnitude_component: float  # 0-1
    confidence_multiplier: float

    def explain(self) -> str:
        return (
            f"{self.value:.2f}/100 — direction "
            f"{'correct' if self.direction_correct else 'wrong'} "
            f"({self.direction_component:.2f}), magnitude "
            f"{self.magnitude_component:.2f} (error {self.error:.5f}), "
            f"confidence x{self.confidence_multiplier:.2f}"
        )


def realised_direction(actual_return: float, band: float = HOLD_BAND) -> str:
    """The direction the market actually took, on the same band the agent used."""
    if actual_return > band:
        return "BUY"
    if actual_return < -band:
        return "SELL"
    return "HOLD"


def score_prediction(
    *,
    direction: str,
    expected_return: float,
    confidence: float,
    actual_return: float,
) -> Score:
    """
    Score one settled prediction.

    Deterministic and total: every finite input produces a score in [0, 100].
    Phase 6 reads these; a NaN escaping here would poison an agent's reputation
    silently, so the inputs are checked rather than assumed.
    """
    if not math.isfinite(expected_return) or not math.isfinite(actual_return):
        raise ValueError("cannot score a non-finite return")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"confidence {confidence} is outside [0, 1]")

    correct = direction == realised_direction(actual_return)
    error = abs(expected_return - actual_return)

    direction_component = 1.0 if correct else 0.0

    # Smooth decay rather than a threshold: 0 error scores 1.0, one scale of
    # error scores 0.5, and it approaches 0 without ever reaching it, so a
    # wildly wrong magnitude is always distinguishable from a merely bad one.
    magnitude_component = 1.0 / (1.0 + error / MAGNITUDE_SCALE)

    base = W_DIRECTION * direction_component + W_MAGNITUDE * magnitude_component

    # Confidence pulls the score toward 100 when correct and toward 0 when
    # wrong, in proportion to how much was staked on it. At confidence 0 the
    # multiplier is inert, which is the honest treatment of "I don't know".
    if correct:
        adjusted = base + CONFIDENCE_SWING * confidence * (1.0 - base)
    else:
        adjusted = base - CONFIDENCE_SWING * confidence * base

    value = max(0.0, min(100.0, adjusted * 100.0))
    return Score(
        value=value,
        direction_correct=correct,
        error=error,
        direction_component=direction_component,
        magnitude_component=magnitude_component,
        confidence_multiplier=(
            1.0 + CONFIDENCE_SWING * confidence
            if correct
            else 1.0 - CONFIDENCE_SWING * confidence
        ),
    )
