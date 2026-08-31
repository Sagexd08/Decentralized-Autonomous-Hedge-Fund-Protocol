"""
CNN-LSTM — IRIS_BUILD_PROMPT v2.0 section 11.

A 1-D convolutional front end over the price window, feeding an LSTM. The conv
picks up local shape (a spike, a step, a squeeze); the LSTM carries what
happened earlier in the window. Small on purpose — this runs on CPU inside the
API container on every agent cycle, so capacity is spent where it earns its
latency.

The agentic-layer prompt is explicit that this must be "a real forward pass
(not a stub returning random numbers)", so it is: real `nn.Module`, real
convolution, real recurrence, deterministic under a fixed seed.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from ml.training.schedule import plan

from ml.models.base import (
    Prediction,
    confidence_for,
    direction_from_return,
    direction_probabilities,
    hash_weights,
)

WINDOW = 32


class _Net(nn.Module):
    def __init__(self, hidden: int = 24) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(2, 8, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.Conv1d(8, 12, kernel_size=3, padding=1),
            nn.ReLU(),
        )
        self.lstm = nn.LSTM(12, hidden, batch_first=True)
        # Two heads on a shared trunk: the return the agent trades on, and a
        # spread used for confidence. One head predicting both would force the
        # model to trade off accuracy against calibration.
        self.head = nn.Linear(hidden, 1)
        self.spread = nn.Linear(hidden, 1)

    def forward(self, window: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # window: (batch, WINDOW, 2)
        x = window.transpose(1, 2)           # (batch, 2, WINDOW)
        x = self.conv(x)                     # (batch, 12, WINDOW)
        x = x.transpose(1, 2)                # (batch, WINDOW, 12)
        out, _ = self.lstm(x)
        last = out[:, -1, :]
        return self.head(last).squeeze(-1), torch.nn.functional.softplus(
            self.spread(last).squeeze(-1)
        )


class CnnLstmModel:
    name = "cnn_lstm"

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
        self.model_version = "cnn-lstm-1.0.0"
        self.model_hash = self._hash()

    def _hash(self) -> str:
        return hash_weights(
            self.name,
            [p.detach().cpu().numpy() for p in self.net.parameters()],
        )

    def fit(self, X_windows: np.ndarray, y: np.ndarray, epochs: int = 300) -> "CnnLstmModel":
        """
        Train on normalised price windows against next-bar returns.

        300 epochs on a cosine schedule, matching the transformer. At 60 epochs
        at a fixed learning rate this model under-fitted badly — its predictions
        shrank toward the mean (mean |prediction| 0.00086 against a target scale
        of 0.0048), which is what made it lose to the baseline in Phase 4. The
        transformer was given the longer schedule when it hit the same basin;
        the same fix was simply never applied here.
        """
        self.net.train()
        self._target_scale = float(max(np.std(y), 1e-9))
        # Normalise here, exactly as predict() does, so training and inference
        # cannot drift apart on the representation.
        normalised = np.asarray(
            [self.window_from_prices(row) for row in np.asarray(X_windows)],
            dtype=np.float64,
        )
        xb = torch.tensor(normalised, dtype=torch.float32)
        yb = torch.tensor(y / self._target_scale, dtype=torch.float32)

        # Mini-batched against a fixed update budget rather than a fixed number
        # of full-batch passes. See ml/training/schedule.py: with real market
        # data the old shape made a single fit cost tens of minutes and grow
        # with every day of history ingested, and there is one fit per agent.
        batch_size, steps, epochs = plan(int(xb.shape[0]))
        opt = torch.optim.Adam(self.net.parameters(), lr=2e-3)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
        loss_fn = nn.SmoothL1Loss()
        generator = torch.Generator().manual_seed(self.seed)

        for _ in range(epochs):
            # Reshuffled every epoch, from a seeded generator: the batch order
            # is part of the fitted weights, so it has to be reproducible or
            # the same agent gets a new model_hash on every fit.
            order = torch.randperm(xb.shape[0], generator=generator)
            for step in range(steps):
                index = order[step * batch_size:(step + 1) * batch_size]
                if index.numel() == 0:
                    continue
                opt.zero_grad()
                pred, spread = self.net(xb[index])
                loss = loss_fn(pred, yb[index])
                # The spread head is trained here, against the absolute
                # residual of the prediction head. It was previously left out
                # of the loss entirely (`pred, _ = self.net(xb)`), so it
                # received no gradient and reported whatever its random
                # initialisation produced. Its magnitude looked plausible only
                # because `_target_scale` multiplies it — and since
                # `confidence` is derived from `expected_return / spread`,
                # every confidence this model reported was an arbitrary
                # constant.
                #
                # Detached, so learning to be uncertain cannot become a way to
                # reduce the prediction loss. The two heads share a trunk but
                # must not negotiate: a model that could widen its error bars
                # to look better would do exactly that.
                loss = loss + loss_fn(spread, (yb[index] - pred).abs().detach())
                loss.backward()
                # Without clipping a single outlier bar can blow the weights
                # out to a scale the model never recovers from — the failure
                # that produced an MSE of 1.96e+11 before this was added.
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
        expected_return, spread = self._forward(features)
        direction = direction_from_return(expected_return, self.threshold)
        proba = direction_probabilities(expected_return, spread, self.threshold)
        return Prediction(
            direction=direction,
            expected_return=expected_return,
            # The probability of *this* call, not of the likeliest class.
            confidence=confidence_for(direction, proba),
            model_version=self.model_version,
            model_hash=self.model_hash,
            features_used=WINDOW,
        )

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        expected_return, spread = self._forward(features)
        return direction_probabilities(expected_return, spread, self.threshold)
