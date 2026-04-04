<<<<<<< HEAD
from fastapi import APIRouter
import numpy as np
from ml.monte_carlo import gbm_paths, var_cvar
from ml.regime_classifier import RegimeClassifier, rolling_volatility

router = APIRouter()


@router.get("/monte-carlo")
def monte_carlo(S0: float = 100000, mu: float = 0.15, sigma: float = 0.20, T: int = 30, n_paths: int = 200):
    paths = gbm_paths(S0, mu, sigma, T, n_paths)
    stats = var_cvar(paths)
    # Return sample paths for visualization (50 paths)
    sample = paths[:50].tolist()
    return {"stats": stats, "paths": sample}


@router.get("/rolling-volatility")
def get_rolling_vol(window: int = 30):
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.015, 252)
    vol = rolling_volatility(returns, window)
    return {"volatility": vol.tolist()}


@router.get("/regime")
def get_regime():
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.015, 90)
    clf = RegimeClassifier()
    clf.fit(returns)
    regimes, confidences = clf.predict(returns)
    return {"regimes": regimes, "confidences": confidences}


@router.get("/allocation-weights")
def get_weights(eta: float = None, steps: int = 50):
    from core.allocation import AllocationEngine
    from core.protocol_params import protocol_params
    # Use governance-controlled eta if not explicitly overridden
    effective_eta = eta if eta is not None else protocol_params.eta
    engine = AllocationEngine(n_agents=6, eta=effective_eta)
    history = []
    for _ in range(steps):
        raw_r = np.random.normal(0.001, 0.01, 6)
        vols = np.random.uniform(0.05, 0.30, 6)
        dds = np.random.uniform(0.01, 0.15, 6)
        w = engine.step(raw_r, vols, dds)
        history.append(w.tolist())
    return {
        "weights_history": history,
        "final_weights": engine.weights.tolist(),
        "regret_bound": engine.get_regret_bound(),
        "eta_used": effective_eta,
        "eta_source": "governance" if eta is None else "manual",
    }
=======
from fastapi import APIRouter
import numpy as np
from ml.monte_carlo import gbm_paths, var_cvar
from ml.regime_classifier import RegimeClassifier, rolling_volatility

router = APIRouter()


@router.get("/monte-carlo")
def monte_carlo(S0: float = 100000, mu: float = 0.15, sigma: float = 0.20, T: int = 30, n_paths: int = 200):
    paths = gbm_paths(S0, mu, sigma, T, n_paths)
    stats = var_cvar(paths)
    # Return sample paths for visualization (50 paths)
    sample = paths[:50].tolist()
    return {"stats": stats, "paths": sample}


@router.get("/rolling-volatility")
def get_rolling_vol(window: int = 30):
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.015, 252)
    vol = rolling_volatility(returns, window)
    return {"volatility": vol.tolist()}


@router.get("/regime")
def get_regime():
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.015, 90)
    clf = RegimeClassifier()
    clf.fit(returns)
    regimes, confidences = clf.predict(returns)
    return {"regimes": regimes, "confidences": confidences}


@router.get("/allocation-weights")
def get_weights(eta: float = None, steps: int = 50):
    from core.allocation import AllocationEngine
    from core.protocol_params import protocol_params
    # Use governance-controlled eta if not explicitly overridden
    effective_eta = eta if eta is not None else protocol_params.eta
    engine = AllocationEngine(n_agents=6, eta=effective_eta)
    history = []
    for _ in range(steps):
        raw_r = np.random.normal(0.001, 0.01, 6)
        vols = np.random.uniform(0.05, 0.30, 6)
        dds = np.random.uniform(0.01, 0.15, 6)
        w = engine.step(raw_r, vols, dds)
        history.append(w.tolist())
    return {
        "weights_history": history,
        "final_weights": engine.weights.tolist(),
        "regret_bound": engine.get_regret_bound(),
        "eta_used": effective_eta,
        "eta_source": "governance" if eta is None else "manual",
    }
>>>>>>> D!
