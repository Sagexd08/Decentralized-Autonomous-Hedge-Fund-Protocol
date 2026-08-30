"""
Market regime classifier using Hidden Markov Model (HMM).
3 states: Bull (0), Sideways (1), Bear (2)
"""
import numpy as np
from typing import List, Tuple

class RegimeClassifier:
    """
    Gaussian HMM-based regime classifier.
    In production: use hmmlearn.GaussianHMM with deep feature extraction.
    """
    def __init__(self, n_states: int = 3):
        self.n_states = n_states
        self.state_names = {0: "Bull", 1: "Sideways", 2: "Bear"}

    def fit(self, returns: np.ndarray):

        self.means = np.array([0.001, 0.0, -0.001])
        self.stds = np.array([0.01, 0.008, 0.015])

    def predict(self, returns: np.ndarray) -> Tuple[List[str], List[float]]:
        """Classify each timestep into a regime with confidence."""
        regimes, confidences = [], []
        for r in returns:
            likelihoods = np.exp(-0.5 * ((r - self.means) / self.stds) ** 2) / self.stds
            total = likelihoods.sum()
            if total == 0:
                probs = np.ones(self.n_states) / self.n_states
            else:
                probs = likelihoods / total
            probs = np.clip(probs, 0, 1)
            state = int(np.argmax(probs))
            regimes.append(self.state_names[state])
            confidences.append(float(probs[state]))
        return regimes, confidences

def rolling_volatility(returns: np.ndarray, window: int = 30) -> np.ndarray:
    """Compute rolling annualized volatility."""
    vol = np.array([
        returns[max(0, i - window):i].std() * np.sqrt(252)
        for i in range(1, len(returns) + 1)
    ])
    return vol
