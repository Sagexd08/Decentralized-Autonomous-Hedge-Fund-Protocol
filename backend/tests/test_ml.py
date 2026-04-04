"""Property-based tests for ML modules using Hypothesis.

Validates: Requirements 9.6
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from ml.monte_carlo import gbm_paths, var_cvar
from ml.regime_classifier import rolling_volatility
from core.allocation import mwu_update, risk_adjusted_return

def normalized_weights(n):
    """Strategy: array of n positive floats that sum to 1.0."""
    return arrays(
        dtype=np.float64,
        shape=n,
        elements=st.floats(min_value=1e-6, max_value=1.0, allow_nan=False, allow_infinity=False),
    ).map(lambda w: w / w.sum())

@given(
    n=st.integers(min_value=2, max_value=20),
    eta=st.floats(min_value=1e-4, max_value=1.0, allow_nan=False, allow_infinity=False),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
@settings(max_examples=100)
def test_mwu_update_weights_sum_to_one(n, eta, seed):
    """**Validates: Requirements 9.6** — mwu_update output weights always sum to 1.0."""
    rng = np.random.default_rng(seed)
    raw = rng.random(n)
    weights = raw / raw.sum()
    returns = rng.uniform(-1.0, 1.0, n)
    result = mwu_update(weights, returns, eta)
    assert abs(result.sum() - 1.0) < 1e-9, f"weights sum to {result.sum()}, expected 1.0"

@given(
    S0=st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    mu=st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
    sigma=st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False),
    T=st.integers(min_value=1, max_value=50),
    n_paths=st.integers(min_value=2, max_value=100),
)
@settings(max_examples=50)
def test_gbm_paths_all_positive(S0, mu, sigma, T, n_paths):
    """**Validates: Requirements 9.6** — all simulated GBM prices are strictly positive."""
    paths = gbm_paths(S0, mu, sigma, T, n_paths)
    assert paths.shape == (n_paths, T + 1)
    assert (paths > 0).all(), "GBM paths must always be strictly positive"

@given(
    S0=st.floats(min_value=1.0, max_value=1e5, allow_nan=False, allow_infinity=False),
    mu=st.floats(min_value=-0.3, max_value=0.3, allow_nan=False, allow_infinity=False),
    sigma=st.floats(min_value=0.01, max_value=0.8, allow_nan=False, allow_infinity=False),
    T=st.integers(min_value=5, max_value=30),
    n_paths=st.integers(min_value=50, max_value=200),
)
@settings(max_examples=50)
def test_var_cvar_cvar_lte_var(S0, mu, sigma, T, n_paths):
    """**Validates: Requirements 9.6** — CVaR (Expected Shortfall) is always <= VaR."""
    paths = gbm_paths(S0, mu, sigma, T, n_paths)
    result = var_cvar(paths)
    assert result["cvar"] <= result["var"], (
        f"CVaR ({result['cvar']:.6f}) must be <= VaR ({result['var']:.6f})"
    )

@given(
    returns=arrays(
        dtype=np.float64,
        shape=st.integers(min_value=2, max_value=200),
        elements=st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
    ),
    window=st.integers(min_value=1, max_value=50),
)
@settings(max_examples=100)
def test_rolling_volatility_all_non_negative(returns, window):
    """**Validates: Requirements 9.6** — rolling volatility values are always >= 0."""
    vol = rolling_volatility(returns, window)
    assert len(vol) == len(returns), "output length must match input length"
    assert (vol >= 0).all(), "volatility must be non-negative"

@given(
    raw_return=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_risk_adjusted_return_zero_denom_returns_zero(raw_return):
    """**Validates: Requirements 9.6** — zero volatility and zero drawdown yields 0.0, not an error."""
    result = risk_adjusted_return(raw_return, volatility=0.0, drawdown=0.0)
    assert result == 0.0, f"Expected 0.0 for zero denom, got {result}"
