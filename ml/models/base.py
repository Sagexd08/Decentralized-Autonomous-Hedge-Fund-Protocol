"""
The common model interface — IRIS_BUILD_PROMPT v2.0 section 11.

Every model in this layer implements the same three things:

    predict(features)       -> Prediction
    predict_proba(features) -> array over (SELL, HOLD, BUY)
    model_version / model_hash

`model_hash` is not decoration. Invariant 3 says model identity must be
persistent and versioned, and the registry enforces that on-chain by refusing
an `update_model` whose hash is unchanged. So the hash has to be a real
function of the model's parameters: two models that would predict differently
must hash differently, and re-instantiating the same model must reproduce the
same hash. Hashing an object id or a timestamp would satisfy the type checker
and defeat the invariant.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

import numpy as np

Direction = Literal["SELL", "HOLD", "BUY"]

# Fixed class order. Everything downstream — predict_proba, the confusion
# matrix, the evaluation report — indexes into this, so it must never be
# reordered casually.
CLASSES: tuple[Direction, Direction, Direction] = ("SELL", "HOLD", "BUY")
SELL, HOLD, BUY = 0, 1, 2


@dataclass(frozen=True)
class Prediction:
    """
    One model's view of one instant.

    `direction` is derived from `expected_return` against the model's own
    threshold rather than argmax over probabilities, so a model that is
    confident about a move too small to trade still says HOLD.
    """

    direction: Direction
    expected_return: float
    confidence: float
    model_version: str
    model_hash: str
    features_used: int = 0
    # How sure the model is of the *side*, given that it takes one at all.
    # Distinct from `confidence`, which also carries the model's uncertainty
    # about whether the market moves enough to matter. See
    # `directional_confidence` below for why the two must not be conflated.
    directional_confidence: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence out of range: {self.confidence}")
        if self.direction not in CLASSES:
            raise ValueError(f"unknown direction: {self.direction}")


@runtime_checkable
class BaseModel(Protocol):
    """Structural interface — a model need only satisfy this shape."""

    model_version: str
    model_hash: str

    def predict(self, features: np.ndarray) -> Prediction: ...

    def predict_proba(self, features: np.ndarray) -> np.ndarray: ...


def hash_params(name: str, params: dict) -> str:
    """
    Deterministic hash over a model's defining parameters.

    Sorted keys and coerced floats so two runs of the same configuration agree,
    on any platform, in any order.
    """
    payload = json.dumps(
        {"model": name, **{k: _stable(v) for k, v in params.items()}},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hash_weights(name: str, arrays: list[np.ndarray]) -> str:
    """
    Hash over trained weights.

    Rounded to 6 decimals before hashing: bit-level float noise between runs
    would otherwise produce a different identity for an identical model, and
    `update_model` would accept a "new version" that is the same model.
    """
    digest = hashlib.sha256(name.encode("utf-8"))
    for arr in arrays:
        digest.update(np.ascontiguousarray(np.round(arr, 6), dtype=np.float64).tobytes())
    return digest.hexdigest()


def _stable(value: object) -> object:
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, (list, tuple)):
        return [_stable(v) for v in value]
    return value


def direction_from_return(expected_return: float, threshold: float) -> Direction:
    if expected_return > threshold:
        return "BUY"
    if expected_return < -threshold:
        return "SELL"
    return "HOLD"


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    exp = np.exp(shifted)
    return exp / exp.sum()

# ─────────────────────────────────────────────────────────────────────────────
# Confidence
# ─────────────────────────────────────────────────────────────────────────────
# Two bugs lived in the previous version of this, and both were invisible to
# the type checker and to Phase 4's evaluation, which never looked at
# confidence at all.
#
#   1. `confidence` was `max(proba)` — the probability of the *most likely*
#      class, which is not necessarily the class being predicted. A model
#      proposing BUY could report the probability it assigned to HOLD. The
#      validation floor in the agent graph then compared that number against a
#      threshold as though it meant "how sure are you about this trade".
#
#   2. The HOLD logit was a hardcoded 0.35, so `max(proba)` had a floor near
#      0.415 and a ceiling that depended on a magic constant rather than on
#      anything the model knew. Confidence was not comparable between models,
#      which made a shared validation floor meaningless — and in practice
#      pinned every CNN-LSTM agent below it, so that strategy could never
#      commit a prediction at all.
#
# The fix is to derive both from quantities the model actually has: its own
# error spread, and the size of the move that would be worth trading.


def direction_probabilities(
    expected_return: float, spread: float, threshold: float
) -> np.ndarray:
    """
    A distribution over (SELL, HOLD, BUY) from a predicted move and its spread.

    Everything is measured in units of the model's own uncertainty:

      * `snr` — how many spreads the predicted move is worth. This is the case
        for taking a side.
      * the HOLD logit — how many spreads away the tradeable band sits. This is
        the case for standing still, and it rises when the model is precise
        enough to be sure the move is too small to trade.

    So a model with wide errors reports low confidence in either direction, and
    a precise model predicting nothing reports *high* confidence in HOLD. Both
    are true statements, which the fixed constant this replaced could not make.
    """
    scale = max(float(spread), 1e-9)
    snr = float(expected_return) / scale
    hold = abs(float(threshold)) / scale

    logits = np.empty(3, dtype=np.float64)
    logits[SELL] = -snr
    logits[HOLD] = hold
    logits[BUY] = snr
    return softmax(logits)


def confidence_for(direction: Direction, proba: np.ndarray) -> float:
    """
    The probability the model assigned to the call it actually made.

    Not `max(proba)`. A BUY carrying HOLD's probability is a number that reads
    like confidence and isn't one.
    """
    return float(proba[CLASSES.index(direction)])


def directional_confidence(direction: Direction, proba: np.ndarray) -> float:
    """
    Given the model takes a side at all, how sure is it of *which* side.

    `P(chosen) / (P(chosen) + P(opposite))`, with HOLD's mass excluded.

    This exists because the validator was gating on `confidence_for`, which
    measures something subtly different: the probability of the chosen
    direction against **all three** classes, HOLD included. Uncertainty about
    whether the market moves therefore counted against a directional call — and
    it is already accounted for, by the decision threshold, which requires the
    predicted move to clear the band scoring treats as flat. Charging a model
    twice for the same doubt rejected agents that were sure of the direction:
    one predicted a move at 0.81 directional confidence and was refused for
    being only 0.51 sure the market would not be flat.

    Returns 0.0 when the model has no directional view at all — a model that
    puts everything on HOLD is not 50/50 between up and down, it is silent, and
    silence must not read as a coin flip.
    """
    chosen = float(proba[CLASSES.index(direction)])
    opposite_name = "SELL" if direction == "BUY" else "BUY"
    opposite = float(proba[CLASSES.index(opposite_name)])
    total = chosen + opposite
    if total <= 1e-12:
        return 0.0
    return chosen / total

