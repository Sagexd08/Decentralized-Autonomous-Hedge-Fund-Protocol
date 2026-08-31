"""
The training contract — Phase 13.

Small file, one job: hold together two constants that live in different layers
and must agree, plus the snapshot machinery that decides which series the
models are fitted on.

`ml` must not import `agents` — the dependency runs the other way — so the tie
between the horizon a model is trained for and the horizon the protocol judges
it over cannot be an import. It is this test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.graphs.nodes import (  # noqa: E402
    DEFAULT_HORIZON_SECONDS,
    FEED_STEP_SECONDS,
    MIN_DECISION_THRESHOLD,
    THRESHOLD_SIGMA,
    decision_threshold,
)
from agents.evaluation.scoring import HOLD_BAND  # noqa: E402
from agents.state import AgentState  # noqa: E402
from ml.inference import artifacts  # noqa: E402
from ml.training import dataset  # noqa: E402


def state(**features) -> AgentState:
    return AgentState(
        agent_id="AGT-TEST", agent_run_id="run", asset="BTC",
        strategy="momentum", features=features,
    )


# ── the horizon a model is trained for is the one it is judged over ─────────

def test_training_horizon_matches_the_decision_horizon():
    """
    The models were fitted to predict one step and their answers were recorded
    as claims about ten. Settlement then measured a ten-minute move against a
    one-minute forecast and scored the difference as the agent's error.

    On the synthetic tape this was invisible: its returns were roughly sixty
    times a real market's, so a one-step prediction happened to land in the
    same range as a ten-step real move. Two wrong scales cancelling is not a
    working system, and only real data made it visible.
    """
    expected = DEFAULT_HORIZON_SECONDS / FEED_STEP_SECONDS
    assert artifacts.TRAINING_HORIZON_STEPS == expected


def test_both_layers_agree_on_how_often_the_feed_ticks():
    assert artifacts.FEED_STEP_SECONDS == FEED_STEP_SECONDS


# ── the decision threshold scales with the market ───────────────────────────

def test_the_threshold_grows_with_observed_volatility():
    """
    A flat five-basis-point bar was right for the synthetic tape's 60bps
    returns and became a 1.4-sigma bar on BTC's 3bps, which no agent could
    clear. The constant was never wrong about conviction; it was wrong to be a
    constant.
    """
    calm = decision_threshold(state(volatility=0.0001))
    normal = decision_threshold(state(volatility=0.0011))
    wild = decision_threshold(state(volatility=0.0060))
    assert calm < normal < wild


def test_the_threshold_never_falls_below_what_scoring_calls_flat():
    """
    Scoring treats a realised move smaller than HOLD_BAND as flat. An agent
    committing a direction below that is claiming something the scorer will
    not credit either way, so the gate and the grader are tied together.
    """
    assert MIN_DECISION_THRESHOLD == HOLD_BAND
    assert decision_threshold(state(volatility=0.0)) == HOLD_BAND
    assert decision_threshold(state(volatility=1e-9)) >= HOLD_BAND


def test_the_threshold_widens_over_the_horizon_not_one_step():
    """
    `volatility` is per step and the horizon spans ten of them. Comparing a
    ten-minute forecast against one minute of noise understates the bar by
    about a factor of three.
    """
    # Well above the floor, so the scaling is measured rather than the clamp.
    vol = 0.003
    steps = DEFAULT_HORIZON_SECONDS / FEED_STEP_SECONDS
    assert decision_threshold(state(volatility=vol)) == pytest.approx(
        THRESHOLD_SIGMA * vol * steps ** 0.5
    )


def test_a_missing_volatility_feature_falls_back_to_the_floor():
    assert decision_threshold(state()) == MIN_DECISION_THRESHOLD


# ── the training snapshot ───────────────────────────────────────────────────

def test_the_digest_is_stable_across_a_round_trip(tmp_path, monkeypatch):
    """
    The digest is the artifact cache key. If it is not reproducible after a
    save and load, every boot misses the cache and refits every model — which
    is both slow and a new `model_hash` each time, exactly what invariant 3
    forbids.
    """
    monkeypatch.setattr(dataset, "DATA_DIR", tmp_path)
    series = np.linspace(77_000.0, 77_500.0, 400)
    snapshot = dataset.Snapshot(
        series=series, asset="BTC", source="LIVE", provider="binance",
        digest=dataset.digest_of(series, "BTC", "LIVE", "binance"),
        samples=series.size, first_at=None, last_at=None, created_at="",
    )
    dataset.save(snapshot)

    reloaded = dataset.current()
    assert reloaded is not None
    assert reloaded.digest == snapshot.digest
    assert np.allclose(reloaded.series, series)


def test_a_snapshot_whose_data_no_longer_matches_its_digest_is_rejected(
    tmp_path, monkeypatch
):
    """
    A cache keyed by a digest that no longer describes the data is worse than
    no cache: the models would be fitted on one series and filed under
    another's identity.
    """
    monkeypatch.setattr(dataset, "DATA_DIR", tmp_path)
    series = np.linspace(1.0, 2.0, 400)
    snapshot = dataset.Snapshot(
        series=series, asset="BTC", source="LIVE", provider="binance",
        digest=dataset.digest_of(series, "BTC", "LIVE", "binance"),
        samples=series.size, first_at=None, last_at=None, created_at="",
    )
    dataset.save(snapshot)

    # Overwrite the payload without touching the pointer.
    np.savez_compressed(
        tmp_path / f"training-{snapshot.digest}.npz",
        series=np.linspace(9.0, 10.0, 400),
    )
    assert dataset.current() is None


def test_a_missing_snapshot_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset, "DATA_DIR", tmp_path)
    assert dataset.current() is None


def test_different_data_produces_a_different_digest():
    a = np.linspace(1.0, 2.0, 100)
    b = np.linspace(1.0, 2.0001, 100)
    assert dataset.digest_of(a, "BTC", "LIVE", "binance") != dataset.digest_of(
        b, "BTC", "LIVE", "binance"
    )


def test_provenance_is_part_of_the_digest():
    """
    Two identical series from different places are different training sets.
    Sharing a key would let a synthetic fit be served under a live identity.
    """
    series = np.linspace(1.0, 2.0, 100)
    assert dataset.digest_of(series, "BTC", "LIVE", "binance") != dataset.digest_of(
        series, "BTC", "SIMULATION", None
    )


# ── the artifact cache key follows the data ─────────────────────────────────

def test_the_cache_key_changes_when_the_training_set_does(tmp_path, monkeypatch):
    """
    Invariant 3 doing real work. A model trained on different data is a
    different model and must not wear the old hash — so refreshing the
    snapshot has to produce a new artifact rather than silently reusing
    weights fitted on the series it replaced.
    """
    monkeypatch.setattr(dataset, "DATA_DIR", tmp_path)
    before = artifacts.contract_key("baseline", 1)

    series = np.linspace(77_000.0, 77_900.0, 500)
    dataset.save(
        dataset.Snapshot(
            series=series, asset="BTC", source="LIVE", provider="binance",
            digest=dataset.digest_of(series, "BTC", "LIVE", "binance"),
            samples=series.size, first_at=None, last_at=None, created_at="",
        )
    )
    assert artifacts.contract_key("baseline", 1) != before


def test_the_synthetic_fallback_is_used_when_there_is_no_snapshot(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(dataset, "DATA_DIR", tmp_path)
    series, key, note = artifacts.training_set()
    assert "synthetic" in note.lower()
    assert "not a real market" in note
    assert series.size == artifacts.TRAINING_SAMPLES
    assert key == artifacts._SYNTHETIC_KEY


def test_the_snapshot_is_used_when_one_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset, "DATA_DIR", tmp_path)
    series = np.linspace(77_000.0, 77_900.0, 500)
    dataset.save(
        dataset.Snapshot(
            series=series, asset="BTC", source="LIVE", provider="binance",
            digest=dataset.digest_of(series, "BTC", "LIVE", "binance"),
            samples=series.size, first_at=None, last_at=None, created_at="",
        )
    )
    resolved, key, note = artifacts.training_set()
    assert np.allclose(resolved, series)
    assert "binance" in note and "LIVE" in note


def test_the_two_tapes_have_wildly_different_return_scales():
    """
    The measurement behind the whole phase. The synthetic tape's one-step
    returns are roughly an order of magnitude and a half larger than a real
    market's, which is why a model fitted on one and run on the other
    overstates every move it predicts.
    """
    synthetic = artifacts.synthetic_series()
    sd_bps = float(np.std(np.diff(synthetic) / synthetic[:-1])) * 10_000
    assert sd_bps > 40  # real one-minute BTC sits nearer 3
