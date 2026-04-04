"""Tests for ML monte_carlo module."""
import sys
import os
import pytest
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from ml.monte_carlo import gbm_paths, var_cvar
from ml.regime_classifier import RegimeClassifier, rolling_volatility
from core.allocation import risk_adjusted_return, mwu_update


def test_gbm_paths_shape():
    paths = gbm_paths(100000, 0.15, 0.20, 30, 100)
    assert paths.shape == (100, 31)


def test_gbm_paths_all_positive():
    paths = gbm_paths(100000, 0.15, 0.20, 30, 100)
    assert (paths > 0).all()


def test_gbm_paths_sigma_zero_raises():
    with pytest.raises(AssertionError, match="sigma must be positive"):
        gbm_paths(100, 0.05, 0.0, 10, 50)


def test_gbm_paths_sigma_negative_raises():
    with pytest.raises(AssertionError, match="sigma must be positive"):
        gbm_paths(100, 0.05, -0.1, 10, 50)


def test_var_cvar_cvar_lte_var():
    """CVaR must be <= VaR: tail mean is always at least as bad as the threshold."""
    paths = gbm_paths(100, 0.05, 0.20, 30, 500)
    result = var_cvar(paths)
    assert result["cvar"] <= result["var"], (
        f"Expected cvar ({result['cvar']:.6f}) <= var ({result['var']:.6f})"
    )


def test_risk_adjusted_return_zero_volatility_and_drawdown():
    """risk_adjusted_return must return 0.0 when volatility=0 and drawdown=0, no ZeroDivisionError."""
    assert risk_adjusted_return(0.1, 0, 0) == 0.0


def test_mwu_update_weights_sum_to_one():
    """mwu_update output weights must sum to 1.0 for random inputs."""
    rng = np.random.default_rng(42)
    for _ in range(50):
        n = rng.integers(2, 20)
        w = rng.random(n)
        w = w / w.sum()
        r = rng.uniform(-1.0, 1.0, n)
        result = mwu_update(w, r, 0.01)
        assert abs(result.sum() - 1.0) < 1e-9, f"weights sum to {result.sum()}, expected 1.0"


def test_rolling_volatility_same_length():
    """rolling_volatility must return an array of the same length as the input."""
    rng = np.random.default_rng(0)
    returns = rng.normal(0, 0.01, 100)
    vol = rolling_volatility(returns, 30)
    assert len(vol) == len(returns)


def test_rolling_volatility_all_non_negative():
    """rolling_volatility must return all non-negative values (std dev >= 0)."""
    rng = np.random.default_rng(1)
    returns = rng.normal(0, 0.01, 100)
    vol = rolling_volatility(returns, 30)
    assert (vol >= 0).all()


def test_rolling_volatility_short_series():
    """rolling_volatility works when series is shorter than the window."""
    returns = np.array([0.01, -0.02, 0.005])
    vol = rolling_volatility(returns, 30)
    assert len(vol) == len(returns)
    assert (vol >= 0).all()


def test_regime_classifier_confidences_in_range():
    """All confidences returned by RegimeClassifier.predict must be in [0.0, 1.0]."""
    rng = np.random.default_rng(42)
    clf = RegimeClassifier()
    clf.fit(rng.normal(0, 0.01, 200))
    returns = rng.normal(0, 0.02, 100)
    _, confidences = clf.predict(returns)
    assert all(0.0 <= c <= 1.0 for c in confidences), (
        f"Some confidences out of [0, 1]: {[c for c in confidences if not (0.0 <= c <= 1.0)]}"
    )


def test_regime_classifier_extreme_returns_uniform_fallback():
    """Extreme returns cause all likelihoods to underflow to 0; predict must fall back to uniform [1/3, 1/3, 1/3]."""
    clf = RegimeClassifier()
    clf.fit(np.array([]))  # fit sets means/stds; extreme r=1000 will underflow
    regimes, confidences = clf.predict(np.array([1000.0]))
    expected = 1.0 / clf.n_states
    assert abs(confidences[0] - expected) < 1e-9, (
        f"Expected uniform confidence {expected}, got {confidences[0]}"
    )


def test_regime_classifier_output_lengths_match_input():
    """len(regimes) and len(confidences) must equal len(returns)."""
    rng = np.random.default_rng(7)
    clf = RegimeClassifier()
    clf.fit(rng.normal(0, 0.01, 200))
    returns = rng.normal(0, 0.02, 50)
    regimes, confidences = clf.predict(returns)
    assert len(regimes) == len(returns)
    assert len(confidences) == len(returns)
