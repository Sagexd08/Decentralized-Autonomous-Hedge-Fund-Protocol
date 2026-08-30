"""
Rule-based baseline — IRIS_BUILD_PROMPT v2.0 section 11.

"Baseline exists so ML has something to beat — track this comparison
explicitly in the evaluation output, don't bury it."

A strawman baseline would make the ML models look good and teach us nothing,
so this is a real, defensible rule: momentum damped by realised volatility.
It has no parameters to fit, cannot overfit, and costs nothing to run. If a
trained model cannot beat it, the honest conclusion is that the trained model
is not earning its complexity — which is exactly what the comparison is for.
"""

from __future__ import annotations

import numpy as np

from ml.models.base import (
    Prediction,
    confidence_for,
    direction_from_return,
    direction_probabilities,
    hash_params,
)

# Index into the feature vector produced by ml.features.
F_MOMENTUM, F_VOLATILITY, F_ZSCORE = 0, 1, 2


class BaselineModel:
    """Deterministic, untrained, and deliberately hard to beat by accident."""

    name = "baseline"

    def __init__(self, threshold: float = 0.0005, damping: float = 0.5) -> None:
        self.threshold = threshold
        self.damping = damping
        self.model_version = "baseline-1.0.0"
        self.model_hash = hash_params(
            self.name, {"threshold": threshold, "damping": damping}
        )

    def predict(self, features: np.ndarray) -> Prediction:
        f = np.asarray(features, dtype=np.float64).ravel()
        momentum = float(f[F_MOMENTUM])
        volatility = float(f[F_VOLATILITY])

        # Damp the signal by volatility: the same momentum means less in a
        # noisy tape than a calm one.
        scale = 1.0 / (1.0 + self.damping * volatility * 100.0)
        expected_return = momentum * scale

        direction = direction_from_return(expected_return, self.threshold)
        proba = self._proba(expected_return, volatility)
        return Prediction(
            direction=direction,
            expected_return=float(expected_return),
            # The probability of *this* call, not of the likeliest class.
            confidence=confidence_for(direction, proba),
            model_version=self.model_version,
            model_hash=self.model_hash,
            features_used=f.size,
        )

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        f = np.asarray(features, dtype=np.float64).ravel()
        momentum = float(f[F_MOMENTUM])
        volatility = float(f[F_VOLATILITY])
        scale = 1.0 / (1.0 + self.damping * volatility * 100.0)
        return self._proba(momentum * scale, volatility)

    def _proba(self, expected_return: float, volatility: float) -> np.ndarray:
        """
        Realised volatility is this model's error spread.

        It has no residuals to measure — it never fits anything — so the
        honest stand-in for "how wrong could I be" is how much the tape is
        moving.

        Fed the *damped* return, the same quantity `predict` thresholds to
        pick a direction. Feeding it raw momentum instead — which is what this
        did — let the distribution and the direction disagree, which is the
        bug `confidence_for` exists to prevent.
        """
        spread = max(volatility, 1e-9) * 4.0
        return direction_probabilities(expected_return, spread, self.threshold)
