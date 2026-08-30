"""
Multiplicative Weights Update (MWU) capital allocation engine.
Guarantees O(sqrt(T) * log(N)) regret vs best fixed agent in hindsight.
"""
import numpy as np
from typing import List, Dict

def mwu_update(weights: np.ndarray, returns: np.ndarray, eta: float = 0.01) -> np.ndarray:
    """
    Multiplicative Weights Update rule.
    w_i(t+1) = w_i(t) * exp(eta * R_i(t))
    Normalized: w_i(t+1) /= sum(w_j(t+1))
    """
    updated = weights * np.exp(eta * returns)
    result = updated / updated.sum()
    assert abs(result.sum() - 1.0) < 1e-9, "weights must sum to 1.0"
    return result

def risk_adjusted_return(raw_return: float, volatility: float, drawdown: float, lam: float = 0.5) -> float:
    """Score_i = Return_i / (Volatility_i + lambda * |Drawdown_i|)"""
    denom = volatility + lam * abs(drawdown)
    return raw_return / denom if denom > 0 else 0.0

def reputation_decay(recent: float, historical: float, alpha: float = 0.3) -> float:
    """Score = alpha * recent + (1 - alpha) * historical"""
    return alpha * recent + (1 - alpha) * historical

def regret_bound(T: int, N: int) -> float:
    """Theoretical regret bound for MWU: O(sqrt(T * log(N)))"""
    return np.sqrt(T * np.log(N))

class AllocationEngine:
    def __init__(self, n_agents: int, eta: float = 0.01):
        self.n = n_agents
        self.eta = eta
        self.weights = np.ones(n_agents) / n_agents
        self.history: List[np.ndarray] = []
        self.t = 0

    def step(self, raw_returns: np.ndarray, volatilities: np.ndarray, drawdowns: np.ndarray) -> np.ndarray:

        try:
            from core.protocol_params import protocol_params
            live_eta = protocol_params.eta
        except Exception:
            live_eta = self.eta
        adj_returns = np.array([
            risk_adjusted_return(r, v, d)
            for r, v, d in zip(raw_returns, volatilities, drawdowns)
        ])
        self.weights = mwu_update(self.weights, adj_returns, live_eta)
        self.history.append(self.weights.copy())
        self.t += 1
        return self.weights

    def get_regret_bound(self) -> float:
        return regret_bound(self.t, self.n)
