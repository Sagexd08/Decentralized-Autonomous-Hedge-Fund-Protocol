"""
Feature extraction — IRIS_BUILD_PROMPT v2.0 section 11.

One vector, one order, shared by every model. Two models fed differently-ordered
features would produce an incomparable evaluation, so the order is fixed here
and asserted in the tests.

The tabular models (baseline, gradient boosting) read this vector. The sequence
models (CNN-LSTM, transformer) read the raw price window instead and normalise
it themselves — the vector would throw away exactly the ordering they exist to
exploit.
"""

from __future__ import annotations

import numpy as np

# Fixed order. ml.models.baseline indexes into positions 0-2 by name.
FEATURE_NAMES = (
    "momentum",        # 0  — close-to-close over the window
    "volatility",      # 1  — realised stdev of returns
    "z_score",         # 2  — last price vs the short mean, in stdevs
    "mean_return",     # 3
    "range_pct",       # 4  — high-low spread over the short window
    "drawdown",        # 5  — worst peak-to-trough in the window
    "skew",            # 6  — return asymmetry
    "accel",           # 7  — change in momentum; second derivative of price
)
N_FEATURES = len(FEATURE_NAMES)

SHORT = 8

# How many steps ahead a training target looks.
#
# Ten, because the protocol commits to a ten-minute horizon and the feed ticks
# once a minute. It defaulted to one, so every model was fitted to answer
# "where is the price in one minute" while its answer was recorded as a claim
# about ten — see ml/inference/artifacts.TRAINING_HORIZON_STEPS. The constant
# lives here because this is the module that builds the target, and both the
# artifact cache and the Phase 4 evaluation have to agree with it or they are
# measuring different problems.
DEFAULT_HORIZON = 10


def extract(prices: np.ndarray) -> np.ndarray:
    """Turn a price window into the shared feature vector."""
    p = np.asarray(prices, dtype=np.float64).ravel()
    if p.size < SHORT + 1:
        p = np.pad(p, (SHORT + 1 - p.size, 0), mode="edge")

    returns = np.diff(p) / np.maximum(p[:-1], 1e-9)
    window = p[-SHORT:]

    momentum = (p[-1] - p[-SHORT]) / max(abs(p[-SHORT]), 1e-9)
    volatility = float(np.std(returns))
    mean_return = float(np.mean(returns))

    spread = float(np.std(window))
    z_score = (p[-1] - float(np.mean(window))) / max(spread, 1e-9)

    peak = np.maximum.accumulate(p)
    drawdown = float(np.min((p - peak) / np.maximum(peak, 1e-9)))

    centred = returns - mean_return
    denom = max(volatility ** 3, 1e-12)
    skew = float(np.mean(centred ** 3) / denom)

    half = max(SHORT // 2, 1)
    recent = (p[-1] - p[-half]) / max(abs(p[-half]), 1e-9)
    accel = recent - momentum / 2.0

    return np.array(
        [
            momentum,
            volatility,
            z_score,
            mean_return,
            (float(window.max()) - float(window.min())) / max(abs(float(window.min())), 1e-9),
            drawdown,
            skew,
            accel,
        ],
        dtype=np.float64,
    )


def build_dataset(
    prices: np.ndarray, window: int = 40, horizon: int = DEFAULT_HORIZON
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build (feature vectors, raw price windows, next-horizon returns).

    Both representations come from one pass so the tabular and sequence models
    are trained and scored on exactly the same samples — otherwise the baseline
    comparison would be measuring different problems.

    The windows are **raw prices**, not returns. The sequence models normalise
    internally via `window_from_prices`, so handing them pre-normalised data
    would difference it a second time. That bug silently produced predicted
    returns of ~3600 (360,000%) while every type check passed, because
    differencing values already near zero explodes.
    """
    p = np.asarray(prices, dtype=np.float64).ravel()
    feats, windows, targets = [], [], []

    for i in range(window, p.size - horizon):
        hist = p[: i + 1]
        feats.append(extract(hist))
        w = hist[-33:]
        if w.size < 33:
            w = np.pad(w, (33 - w.size, 0), mode="edge")
        windows.append(w)
        targets.append((p[i + horizon] - p[i]) / max(p[i], 1e-9))

    return (
        np.asarray(feats, dtype=np.float64),
        np.asarray(windows, dtype=np.float64),
        np.asarray(targets, dtype=np.float64),
    )
