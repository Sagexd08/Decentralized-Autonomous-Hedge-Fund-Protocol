"""
Transformer — IRIS_BUILD_PROMPT v2.0 section 11.

A small encoder over the return window: linear projection, learned positional
embedding, two `TransformerEncoderLayer`s, mean-pooled to two heads.

Where the CNN-LSTM reads the window as a sequence and carries state forward,
this attends across the whole window at once — so a pattern at bar 3 can bear
directly on bar 32 without being squeezed through a recurrent bottleneck. That
difference is the point of having both: they fail on different tapes, and
section 10 requires the agents built on them to behave differently rather than
being palette-swaps.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from ml.models.base import (
    BUY,
    HOLD,
    SELL,
    Prediction,
    direction_from_return,
    hash_weights,
    softmax,
)

WINDOW = 32
D_MODEL = 16


class _Net(nn.Module):
    def __init__(self, d_model: int = D_MODEL, heads: int = 2, layers: int = 2) -> None:
        super().__init__()
        self.project = nn.Linear(2, d_model)
        # Learned rather than sinusoidal: the window is short and fixed, so
        # there is nothing to extrapolate to and the model may as well learn
        # what each position in the window is worth.
        self.positions = nn.Parameter(torch.zeros(1, WINDOW, d_model))
        nn.init.normal_(self.positions, std=0.02)

        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=heads,
            dim_feedforward=d_model * 4,
            dropout=0.0,          # deterministic inference; section 18
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=layers)
        self.head = nn.Linear(d_model, 1)
        self.spread = nn.Linear(d_model, 1)

    def forward(self, window: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        x = self.project(window) + self.positions
        x = self.encoder(x)
        pooled = x.mean(dim=1)
        return self.head(pooled).squeeze(-1), torch.nn.functional.softplus(
            self.spread(pooled).squeeze(-1)
        )


class TransformerModel:
    name = "transformer"

    def __init__(self, threshold: float = 0.0005, seed: int = 0) -> None:
        self.threshold = threshold
        self.seed = seed
        torch.manual_seed(seed)
        self.net = _Net()
        self.net.eval()
        self.fitted = False
        # Targets are ~1e-3; a network initialised for unit-scale outputs has
        # to travel a long way to reach them, and with a plain Adam step it can
        # overshoot into divergence. Fit on standardised targets and undo the
        # scaling at predict time so the learning problem is well-conditioned.
        self._target_scale = 1.0
        self.model_version = "transformer-1.0.0"
        self.model_hash = self._hash()

    def _hash(self) -> str:
        return hash_weights(
            self.name, [p.detach().cpu().numpy() for p in self.net.parameters()]
        )

    def fit(self, X_windows: np.ndarray, y: np.ndarray, epochs: int = 300) -> "TransformerModel":
        self.net.train()
        # A pre-norm encoder this small needs a longer, gentler schedule than
        # the CNN-LSTM: with only 60 epochs it never left the flat-HOLD basin
        # and the evaluation correctly called it DEGENERATE. Gradient clipping
        # below is what makes the longer run safe.
        opt = torch.optim.Adam(self.net.parameters(), lr=2e-3)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
        loss_fn = nn.SmoothL1Loss()

        self._target_scale = float(max(np.std(y), 1e-9))
        # Normalise here, exactly as predict() does, so training and inference
        # cannot drift apart on the representation.
        normalised = np.asarray(
            [self.window_from_prices(row) for row in np.asarray(X_windows)],
            dtype=np.float64,
        )
        xb = torch.tensor(normalised, dtype=torch.float32)
        yb = torch.tensor(y / self._target_scale, dtype=torch.float32)
        for _ in range(epochs):
            opt.zero_grad()
            pred, _ = self.net(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            # Without clipping a single outlier bar can blow the weights out to
            # a scale the model never recovers from — the failure that produced
            # an MSE of 1.96e+11 before this was added.
            torch.nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
            opt.step()
            sched.step()

        self.net.eval()
        self.fitted = True
        self.model_hash = self._hash()
        return self

    @staticmethod
    def window_from_prices(prices: np.ndarray) -> np.ndarray:
        """
        Turn a raw price window into the two channels the network reads.

        Channel 0 is returns — scale-free, so BTC at 60,000 and a token at 0.60
        are the same problem. Channel 1 is the z-scored price *level* within the
        window, which returns alone throw away. On a mean-reverting series the
        deviation from the local mean is the signal, so a model given only
        returns is blind to the thing worth predicting — which is exactly why
        both sequence models regressed to a flat HOLD before this channel
        existed, while the tabular models (which get `z_score` as a feature)
        did not.

        Returns shape (WINDOW, 2).
        """
        p = np.asarray(prices, dtype=np.float64).ravel()
        if p.size < WINDOW + 1:
            p = np.pad(p, (WINDOW + 1 - p.size, 0), mode="edge")
        w = p[-(WINDOW + 1):]

        returns = np.diff(w) / np.maximum(np.abs(w[:-1]), 1e-9)
        level = w[1:]
        z = (level - level.mean()) / max(level.std(), 1e-9)
        return np.stack([returns, z], axis=-1)

    def _forward(self, features: np.ndarray) -> tuple[float, float]:
        window = self.window_from_prices(features)
        with torch.no_grad():
            pred, spread = self.net(torch.tensor(window[None, ...], dtype=torch.float32))
        return (
            float(pred.item()) * self._target_scale,
            float(spread.item()) * self._target_scale,
        )

    def predict(self, features: np.ndarray) -> Prediction:
        expected_return, _ = self._forward(features)
        proba = self.predict_proba(features)
        return Prediction(
            direction=direction_from_return(expected_return, self.threshold),
            expected_return=expected_return,
            confidence=float(proba.max()),
            model_version=self.model_version,
            model_hash=self.model_hash,
            features_used=WINDOW,
        )

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        expected_return, spread = self._forward(features)
        snr = expected_return / max(spread, 1e-6)
        logits = np.zeros(3)
        logits[BUY] = snr
        logits[SELL] = -snr
        logits[HOLD] = 0.35
        return softmax(logits)
