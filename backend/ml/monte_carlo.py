import numpy as np
from typing import Dict

def gbm_paths(S0: float, mu: float, sigma: float, T: int, n_paths: int = 1000) -> np.ndarray:
    """
    Simulate GBM paths: dS = mu*S*dt + sigma*S*dW
    Returns shape (n_paths, T+1)
    """
    assert sigma > 0, "sigma must be positive"
    dt = 1 / 252
    paths = np.zeros((n_paths, T + 1))
    paths[:, 0] = S0
    Z = np.random.standard_normal((n_paths, T))
    for t in range(1, T + 1):
        paths[:, t] = paths[:, t - 1] * np.exp((mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z[:, t - 1])
    return paths

def var_cvar(paths: np.ndarray, confidence: float = 0.95) -> Dict[str, float]:
    """Compute Value at Risk and Conditional VaR from simulated paths.

    Sign convention: all return values are expressed as fractional returns
    where negative values represent losses (e.g. -0.05 means a 5% loss).

    VaR is the loss threshold at the given confidence level — the worst
    return that is not exceeded with probability `confidence`. CVaR (Expected
    Shortfall) is the mean return of all scenarios that breach VaR, so it
    represents the average loss in the tail. By construction:

        cvar <= var  (CVaR is always at least as bad as VaR)

    Args:
        paths: Simulated price paths of shape (n_paths, T+1).
        confidence: Confidence level for VaR/CVaR, e.g. 0.95 for 95%.

    Returns:
        Dict with keys:
            "var"             – Value at Risk (negative = loss)
            "cvar"            – Conditional VaR / Expected Shortfall (cvar <= var)
            "expected_return" – Mean return across all paths
            "prob_profit"     – Fraction of paths with positive return
            "p95"             – 95th percentile return
            "p50"             – Median return
            "p5"              – 5th percentile return
    """
    final_returns = (paths[:, -1] - paths[:, 0]) / paths[:, 0]
    var = np.percentile(final_returns, (1 - confidence) * 100)
    cvar = final_returns[final_returns <= var].mean()
    return {
        "var": float(var),
        "cvar": float(cvar),
        "expected_return": float(final_returns.mean()),
        "prob_profit": float((final_returns > 0).mean()),
        "p95": float(np.percentile(final_returns, 95)),
        "p50": float(np.percentile(final_returns, 50)),
        "p5": float(np.percentile(final_returns, 5)),
    }
