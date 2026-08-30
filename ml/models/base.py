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
