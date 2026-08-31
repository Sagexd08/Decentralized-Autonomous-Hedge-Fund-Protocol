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

from ml.features.extract import DEFAULT_HORIZON, build_dataset
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
CONTRACT_VERSION = 7   # bumped for mini-batched training on an update budget

# How many steps ahead the models are trained to predict.
#
# This has to equal the horizon the protocol actually judges them over, and it
# did not. `build_dataset` defaulted to one step while DECISION commits to
# `DEFAULT_HORIZON_SECONDS` = 600 and the feed ticks once a minute — so every
# model was fitted to answer "where is the price in one minute" and its answer
# was recorded as a claim about ten. Settlement then measured the ten-minute
# move against a one-minute forecast and scored the difference as error.
#
# On the synthetic tape this was invisible: its returns were ~60x larger than a
# real market's, so a one-step prediction happened to land in the same range as
# a ten-step real move. Two wrong scales cancelling is not a working system.
#
# `tests/unit/test_training_contract.py` asserts this stays equal to
# DEFAULT_HORIZON_SECONDS / FEED_STEP_SECONDS. ml must not import agents — the
# layering runs the other way — so the tie is a test rather than an import.
TRAINING_HORIZON_STEPS = DEFAULT_HORIZON
FEED_STEP_SECONDS = 60

_lock = threading.Lock()
_memo: dict[tuple[str, int], BaseModel] = {}


def synthetic_series(
    n: int = TRAINING_SAMPLES, seed: int = TRAINING_SEED
) -> np.ndarray:
    """
    The fallback tape, used when no real snapshot exists.

    An Ornstein-Uhlenbeck process starting at 100.0. Seeded and fixed, because
    section 18 requires simulation to be reproducible — a model whose training
    data cannot be regenerated is a model whose reported accuracy cannot be
    checked.

    This is synthetic, and its statistics are nothing like a real market's: its
    one-step returns have a standard deviation near 60bps against roughly 1bps
    for one-minute BTC. A model fitted here and run on a live tape predicts
    moves about sixty times too large. That is why `ml.training.dataset`
    exists and why this is now the fallback rather than the default.
    """
    rng = random.Random(seed)
    price = TRAINING_START_PRICE
    out: list[float] = []
    for _ in range(n):
        price += TRAINING_MEAN_REVERSION * (TRAINING_START_PRICE - price)
        price += rng.gauss(0, TRAINING_NOISE)
        out.append(price)
    return np.asarray(out, dtype=np.float64)


# Kept under its original name: several tests and `ml.training` import it.
training_series = synthetic_series

_SYNTHETIC_KEY = "|".join(
    str(x) for x in (
        "SIMULATION", TRAINING_SEED, TRAINING_SAMPLES,
        TRAINING_START_PRICE, TRAINING_MEAN_REVERSION, TRAINING_NOISE,
    )
)


def training_set() -> tuple[np.ndarray, str, str]:
    """
    The series to fit on, its cache key, and a human-readable provenance line.

    Resolved from the frozen snapshot in `ml.training.dataset` when one exists,
    and from the synthetic tape when it does not. Not memoised: it is two file
    reads, it is called once per fit, and a stale in-process copy would let a
    container keep fitting on a dataset that was deliberately replaced.
    """
    try:
        from ml.training.dataset import current

        snapshot = current()
    except Exception:  # noqa: BLE001 - a missing snapshot is not a failure
        snapshot = None

    if snapshot is not None and snapshot.series.size >= 200:
        return snapshot.series, snapshot.digest, snapshot.describe()

    return (
        synthetic_series(),
        _SYNTHETIC_KEY,
        f"synthetic Ornstein-Uhlenbeck tape, {TRAINING_SAMPLES} samples "
        f"(seed {TRAINING_SEED}) — not a real market",
    )


def contract_key(family: str, seed: int) -> str:
    """
    A short digest of everything that determines the fitted weights.

    The training data's own digest is part of it, so refreshing the snapshot
    produces a new artifact rather than silently reusing weights fitted on the
    series it replaced. That is invariant 3 doing real work: a model trained on
    different data is a different model and must not wear the old hash.
    """
    _, data_key, _ = training_set()
    payload = "|".join(
        str(x)
        for x in (CONTRACT_VERSION, family, seed, TRAINING_HORIZON_STEPS, data_key)
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

    prices, _, provenance = training_set()
    X_features, X_windows, y = build_dataset(prices, horizon=TRAINING_HORIZON_STEPS)
    model.fit(X_features if family in TABULAR else X_windows, y)
    # Recorded on the model so a prediction can be traced back to the data
    # behind it, not just to the weights.
    try:
        model.training_provenance = provenance  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - a frozen model is still a usable model
        pass
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
    """Fit and cache one seed's models. Returns family -> model_hash."""
    return {f: fitted_model(f, seed).model_hash for f in families}


def warm_agents(dsn: Optional[str] = None) -> dict[str, str]:
    """
    Fit and cache the models the **registered agents** actually use.

    `warm()` on its own warms seed 0, which no agent has. Model identity is per
    agent (invariant 3): `model_seed_for(agent_id)` gives each one its own
    initialisation, so warming seed 0 filled the cache with artifacts nothing
    would ever ask for and left every agent's first run to fit its own from
    cold. That was tolerable at ninety seconds a fit and became the dominant
    cost the moment the training set was real. See `ml/training/schedule.py`
    for the other half of that fix.

    Returns agent_id -> model_hash. Falls back to `warm()` if the registry
    cannot be read, so a cold container without a database still gets a cache.
    """
    from ml.inference.registry import family_for_strategy

    try:
        import psycopg

        from agents.runtime.persistence import dsn as default_dsn

        with psycopg.connect(dsn or default_dsn()) as conn:
            rows = conn.execute(
                "select id, strategy from agents where status <> 'RETIRED' "
                "order by id"
            ).fetchall()
    except Exception:  # noqa: BLE001 - a cold container may have no database
        return warm()

    out: dict[str, str] = {}
    for agent_id, strategy in rows:
        family = family_for_strategy(strategy)
        if family is None:
            continue
        out[agent_id] = fitted_model(family, model_seed_for(agent_id)).model_hash
    return out or warm()


def clear_memo() -> None:
    """Drop the in-process cache. For tests; does not touch disk."""
    with _lock:
        _memo.clear()
