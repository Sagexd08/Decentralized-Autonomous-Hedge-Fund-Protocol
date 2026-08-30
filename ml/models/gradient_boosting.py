"""
Gradient boosting — IRIS_BUILD_PROMPT v2.0 section 11.

scikit-learn `HistGradientBoostingRegressor`, predicting the next-bar return
directly rather than a class label. Regression then thresholding keeps the
model's output on the same scale as every other model here, so the comparison
against the baseline is like-for-like.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from ml.models.base import (
    Prediction,
    confidence_for,
    direction_from_return,
    direction_probabilities,
    hash_params,
    hash_weights,
)


class GradientBoostingModel:
    name = "gradient_boosting"

    def __init__(
        self,
        threshold: float = 0.0005,
        max_iter: int = 120,
        learning_rate: float = 0.06,
        max_depth: int = 4,
        seed: int = 0,
    ) -> None:
        self.threshold = threshold
        self.seed = seed
        self.model = HistGradientBoostingRegressor(
            max_iter=max_iter,
            learning_rate=learning_rate,
            max_depth=max_depth,
            random_state=seed,
        )
        self.fitted = False
        self._residual_scale = 1e-3
        self.model_version = "gbdt-1.0.0"
        # Until it is fitted the model is fully described by its config.
        self.model_hash = hash_params(
            self.name,
            {
                "max_iter": max_iter,
                "learning_rate": learning_rate,
                "max_depth": max_depth,
                "seed": seed,
                "fitted": False,
            },
        )

    def fit(self, X: np.ndarray, y: np.ndarray) -> "GradientBoostingModel":
        self.model.fit(X, y)
        self.fitted = True

        # Residual spread sets the confidence scale: a model whose errors are
        # large should not report high confidence on a small predicted move.
        residuals = y - self.model.predict(X)
        self._residual_scale = float(max(np.std(residuals), 1e-9))

        # Identity now depends on what it learned, not just how it was configured.
        preds = self.model.predict(X)
        self.model_hash = hash_weights(
            self.name, [np.asarray(preds, dtype=np.float64), np.array([self._residual_scale])]
        )
        return self

    def predict(self, features: np.ndarray) -> Prediction:
        f = np.asarray(features, dtype=np.float64).reshape(1, -1)
        expected_return = (
            float(self.model.predict(f)[0]) if self.fitted else 0.0
        )
        direction = direction_from_return(expected_return, self.threshold)
        proba = self.predict_proba(features)
        return Prediction(
            direction=direction,
            expected_return=expected_return,
            # The probability of *this* call, not of the likeliest class.
            confidence=confidence_for(direction, proba),
            model_version=self.model_version,
            model_hash=self.model_hash,
            features_used=f.size,
        )

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        f = np.asarray(features, dtype=np.float64).reshape(1, -1)
        expected_return = float(self.model.predict(f)[0]) if self.fitted else 0.0
        # The residual spread measured at fit time is this model's uncertainty.
        return direction_probabilities(
            expected_return, self._residual_scale * 2.0, self.threshold
        )
