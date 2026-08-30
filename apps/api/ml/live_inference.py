"""
Live inference bridge: converts PriceEngine history into CNN-LSTM feature windows
and returns a trading decision with confidence.

The CNN-LSTM was trained on 20-feature OHLCV windows of shape (50, 20).
At inference time we only have close-price history, so we synthesise the missing
OHLCV columns from the price series (realistic for tick-level data where the bar
open ≈ previous close and intrabar high/low ≈ ±0.1% of close).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sklearn.preprocessing import StandardScaler
    from ml.hybrid_model import CNNLSTMModel

logger = logging.getLogger(__name__)

# Must match FEATURE_COLS in train_hybrid.py exactly
FEATURE_COLS = [
    "Open", "High", "Low", "Close", "Volume",
    "return_1", "return_5", "log_return", "price_diff",
    "roll_mean_10", "roll_std_10", "roll_vol_10",
    "roll_mean_20", "roll_std_20", "roll_vol_20",
    "momentum_10", "momentum_20",
    "hl_spread", "body_ratio", "vol_norm",
]

WINDOW_SIZE = 50          # must match training config
# We need WINDOW_SIZE rows after engineering; rolling(20) drops 19 rows at the
# front, so we need WINDOW_SIZE + 20 raw price ticks minimum.
MIN_HISTORY = WINDOW_SIZE + 20


@dataclass
class LivePrediction:
    symbol: str
    predicted_log_return: float
    decision: str           # "BUY" | "SELL" | "HOLD"
    confidence: float       # 0-1
    source: str             # "cnn_lstm" | "momentum_fallback"


def _build_ohlcv_matrix(prices: list[float]) -> np.ndarray:
    """
    Synthesise an (N, 20) OHLCV feature matrix from a list of close prices.

    Synthetic assumptions (conservative):
      - Open  = previous Close
      - High  = max(Open, Close) * 1.001   (0.1% intrabar wiggle)
      - Low   = min(Open, Close) * 0.999
      - Volume= 1e8 baseline, scaled by |return| (higher move → higher volume)
    """
    prices = np.array(prices, dtype=np.float64)
    n = len(prices)

    close  = prices
    open_  = np.concatenate([[prices[0]], prices[:-1]])
    high   = np.maximum(open_, close) * 1.001
    low    = np.minimum(open_, close) * 0.999

    log_ret = np.log(close / np.maximum(open_, 1e-12))
    volume  = 1e8 * (1.0 + 10.0 * np.abs(log_ret))  # volume proxy

    def safe_pct(a, shift):
        prev = np.roll(a, shift)
        prev[:shift] = a[0]
        return (a - prev) / np.maximum(np.abs(prev), 1e-12)

    def rolling_mean(a, w):
        out = np.full_like(a, np.nan)
        for i in range(w - 1, n):
            out[i] = a[i - w + 1 : i + 1].mean()
        return out

    def rolling_std(a, w):
        out = np.full_like(a, np.nan)
        for i in range(w - 1, n):
            out[i] = a[i - w + 1 : i + 1].std(ddof=0)
        return out

    ret1 = safe_pct(close, 1)
    ret5 = safe_pct(close, 5)
    price_diff = close - np.roll(close, 1); price_diff[0] = 0.0

    rm10  = rolling_mean(close, 10)
    rs10  = rolling_std(close, 10)
    rv10  = rolling_std(log_ret, 10)
    rm20  = rolling_mean(close, 20)
    rs20  = rolling_std(close, 20)
    rv20  = rolling_std(log_ret, 20)

    mom10 = close - np.roll(close, 10); mom10[:10] = 0.0
    mom20 = close - np.roll(close, 20); mom20[:20] = 0.0

    hl_spread  = (high - low) / np.maximum(close, 1e-12)
    body_ratio = np.abs(close - open_) / np.maximum(high - low, 1e-12)

    vol_mean20 = rolling_mean(volume, 20)
    vol_norm   = volume / np.maximum(vol_mean20, 1e-12)

    mat = np.column_stack([
        open_, high, low, close, volume,
        ret1, ret5, log_ret, price_diff,
        rm10, rs10, rv10,
        rm20, rs20, rv20,
        mom10, mom20,
        hl_spread, body_ratio, vol_norm,
    ])
    return mat


def build_feature_window(prices: list[float]) -> np.ndarray | None:
    """
    Build the (WINDOW_SIZE, 20) input tensor from a list of close prices.

    Returns None if there is not enough history.
    """
    if len(prices) < MIN_HISTORY:
        return None

    mat = _build_ohlcv_matrix(prices)

    # Drop rows with any NaN (from rolling ops at the start of the series)
    valid = mat[~np.isnan(mat).any(axis=1)]
    if len(valid) < WINDOW_SIZE:
        return None

    # Take the most recent WINDOW_SIZE rows
    return valid[-WINDOW_SIZE:].astype(np.float32)


def ml_decision(
    symbol: str,
    prices: list[float],
    model: "CNNLSTMModel",
    scaler: "StandardScaler",
) -> LivePrediction:
    """
    Run CNN-LSTM inference on live price history.

    Falls back to momentum signal if the model or history is unavailable.
    """
    import torch
    from ml.train_hybrid import decision as _decision_label

    window = build_feature_window(prices)
    if window is None or model is None or scaler is None:
        return _momentum_fallback(symbol, prices)

    try:
        model.eval()
        x_scaled = scaler.transform(window)                        # (50, 20)
        x_tensor = torch.tensor(x_scaled[None], dtype=torch.float32)  # (1, 50, 20)
        with torch.no_grad():
            pred_log_return = model(x_tensor).item()

        label = _decision_label(pred_log_return)

        # Confidence: normalised distance from 0 relative to training threshold 0.001
        raw_conf = abs(pred_log_return) / 0.001
        confidence = min(0.95, math.tanh(raw_conf) * 0.85 + 0.10)

        logger.debug(
            "CNN-LSTM [%s] pred=%.6f decision=%s conf=%.3f",
            symbol, pred_log_return, label, confidence,
        )
        return LivePrediction(
            symbol=symbol,
            predicted_log_return=pred_log_return,
            decision=label,
            confidence=confidence,
            source="cnn_lstm",
        )

    except Exception as exc:
        logger.warning("CNN-LSTM inference failed for %s: %s — falling back", symbol, exc)
        return _momentum_fallback(symbol, prices)


def _momentum_fallback(symbol: str, prices: list[float]) -> LivePrediction:
    """Simple 3-bar momentum as fallback when model is unavailable."""
    if len(prices) < 4:
        return LivePrediction(
            symbol=symbol, predicted_log_return=0.0,
            decision="HOLD", confidence=0.5, source="momentum_fallback",
        )
    momentum = (prices[-1] - prices[-4]) / (prices[-4] + 1e-12)
    if momentum > 0.005:
        decision, log_ret = "BUY", 0.002
    elif momentum < -0.005:
        decision, log_ret = "SELL", -0.002
    else:
        decision, log_ret = "HOLD", 0.0

    return LivePrediction(
        symbol=symbol, predicted_log_return=log_ret,
        decision=decision, confidence=0.5, source="momentum_fallback",
    )
