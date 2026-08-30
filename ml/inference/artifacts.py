"""
Trained-model artifacts — IRIS_BUILD_PROMPT v2.0 sections 11 and 12,
invariant 3 ("model identity is persistent and versioned").

This module exists because of two bugs the Phase 3 gate caught after Phase 4
wired real models into the graph.

**Every agent abstained, always.** `model_inference` constructed a fresh,
*untrained* model on each run. An untrained network's confidence output is
arbitrary, it sat below the 0.55 validation floor, and so no agent ever
committed a prediction. The graph was working; there was simply nothing behind
it. Nothing type-checked wrong and nothing crashed — the system just quietly
never traded.

**Model identity moved with the run.** The model was seeded from `state.seed`,
which is the *market tape's* seed and changes every run. So the same agent
produced a different `model_hash` on every invocation, which is precisely what
invariant 3 forbids: a version history where every entry is a new version is
not a version history. A model's seed is a property of its version, not of the
run observing it, so it comes from the agent's registered version here.

Artifacts are cached on disk because the transformer takes ~25s to fit, and a
cold container that retrains three models before answering is a cold container
that fails the section 27 Phase 16 boot budget. The cache is keyed by the
training contract — family, seed, series, hyper-shape — so changing any of
them produces a different key rather than silently reusing stale weights.
"""

from __future__ import annotations

import hashlib
import os
import pickle
import random
import threading
from pathlib import Path
from typing import Optional

import numpy as np

from ml.features.extract import build_dataset
from ml.models.base import BaseModel
from ml.inference.registry import TABULAR, all_models

# Where fitted artifacts live. Overridable so a test never writes into the
# directory the API is serving from.
ARTIFACT_DIR = Path(os.getenv("IRIS_MODEL_DIR", "/app/var/models"))

# The training contract. Every value here is part of the cache key: change one
# and you get a new artifact, not a stale one wearing a new name.
TRAINING_SEED = 1_337
TRAINING_SAMPLES = 600
TRAINING_START_PRICE = 100.0
TRAINING_MEAN_REVERSION = 0.02
TRAINING_NOISE = 0.6
CONTRACT_VERSION = 2   # bumped when confidence was rederived in ml/models/base

_lock = threading.Lock()
_memo: dict[tuple[str, int], BaseModel] = {}


def training_series(
    n: int = TRAINING_SAMPLES, seed: int = TRAINING_SEED
) -> np.ndarray:
    """
    The tape every model is fitted on.

    Deliberately the same Ornstein-Uhlenbeck process the agents observe, so a
    model is trained on a series with the character of the one it will predict.
    Seeded and fixed, because section 18 requires simulation to be reproducible
    — and a model whose training data cannot be regenerated is a model whose
    reported accuracy cannot be checked.

    This is synthetic. Every prediction made from it is labelled SIMULATION all
    the way through to `prediction_outcomes.data_source`, and nothing here
    should ever be presented as evidence of live performance.
    """
    rng = random.Random(seed)
    price = TRAINING_START_PRICE
    out: list[float] = []
    for _ in range(n):
        price += TRAINING_MEAN_REVERSION * (TRAINING_START_PRICE - price)
        price += rng.gauss(0, TRAINING_NOISE)
        out.append(price)
    return np.asarray(out, dtype=np.float64)


def contract_key(family: str, seed: int) -> str:
    """A short digest of everything that determines the fitted weights."""
    payload = "|".join(
        str(x)
        for x in (
            CONTRACT_VERSION, family, seed, TRAINING_SEED, TRAINING_SAMPLES,
            TRAINING_START_PRICE, TRAINING_MEAN_REVERSION, TRAINING_NOISE,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def artifact_path(family: str, seed: int) -> Path:
    return ARTIFACT_DIR / f"{family}-{contract_key(family, seed)}.pkl"


def model_seed_for(agent_id: str) -> int:
    """
    A stable per-agent model seed.

    Derived from the agent id, so the same agent initialises the same weights
    on every run and its `model_hash` is a fact about the agent rather than an
    accident of when it ran. Different agents get different initialisations, so
    two agents on the same family are still genuinely different models —
    section 10 is explicit that agents must not be palette-swaps.
    """
    return int(hashlib.sha256(agent_id.encode("utf-8")).hexdigest()[:8], 16)


def _fit(family: str, seed: int) -> BaseModel:
    model = all_models(seed=seed)[family]
    if not hasattr(model, "fit"):
        return model  # the baseline has nothing to learn

    prices = training_series()
    X_features, X_windows, y = build_dataset(prices)
    model.fit(X_features if family in TABULAR else X_windows, y)
    return model


def fitted_model(family: str, seed: int = 0) -> BaseModel:
    """
    A trained model, from memory, then disk, then by fitting one.

    The lock matters: FastAPI serves concurrently, and two requests racing to
    fit the same transformer would burn 50 seconds of CPU to produce one
    artifact. Held across the fit deliberately — the alternative is a
    double-fit, and the fit is the expensive part.
    """
    key = (family, seed)
    cached = _memo.get(key)
    if cached is not None:
        return cached

    with _lock:
        cached = _memo.get(key)
        if cached is not None:
            return cached

        model = _load(family, seed) or _fit(family, seed)
        _save(model, family, seed)
        _memo[key] = model
        return model


def _load(family: str, seed: int) -> Optional[BaseModel]:
    """
    Read a cached artifact, or None.

    Any failure here — a truncated file, a pickle written by another version of
    the code, an unreadable directory — falls through to retraining. A stale
    artifact silently loaded would put weights nobody can account for behind
    real predictions, which is worse than 25 seconds of CPU.
    """
    path = artifact_path(family, seed)
    if not path.exists():
        return None
    try:
        with path.open("rb") as fh:
            model = pickle.load(fh)
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        return None

    if getattr(model, "name", None) != family:
        return None
    return model


def _save(model: BaseModel, family: str, seed: int) -> None:
    """Best-effort. A read-only volume must not stop the model from being used."""
    path = artifact_path(family, seed)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("wb") as fh:
            pickle.dump(model, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)   # atomic: a concurrent reader never sees a partial file
    except Exception:
        pass


def warm(families: tuple[str, ...] = ("baseline", "gradient_boosting",
                                      "cnn_lstm", "transformer"),
         seed: int = 0) -> dict[str, str]:
    """Fit and cache everything up front. Returns family -> model_hash."""
    return {f: fitted_model(f, seed).model_hash for f in families}


def clear_memo() -> None:
    """Drop the in-process cache. For tests; does not touch disk."""
    with _lock:
        _memo.clear()
