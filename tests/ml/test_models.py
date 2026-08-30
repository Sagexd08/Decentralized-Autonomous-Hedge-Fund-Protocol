"""
Model layer tests — IRIS_BUILD_PROMPT v2.0 section 11 / Phase 4 DoD.

DoD: all four model classes return predictions via the common interface, and
the baseline comparison is logged.

The tests that matter most here are not "does it run" but:

  * every model satisfies the same interface, so the comparison is like-for-like;
  * `model_hash` is a real function of the model's parameters — invariant 3
    depends on it, and the on-chain registry rejects an unchanged hash;
  * the evaluation refuses to call a degenerate model a winner.

That last one exists because it caught a real failure: a transformer predicting
BUY for 100% of samples, with an MSE of 1.96e+11, was initially reported as
BEATS BASELINE on accuracy alone.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.features.extract import FEATURE_NAMES, N_FEATURES, build_dataset, extract  # noqa: E402
from ml.inference.registry import (  # noqa: E402
    DEGENERATE_SHARE,
    TABULAR,
    ModelScore,
    all_models,
    compare_to_baseline,
    evaluate_all,
    format_report,
)
from ml.models.base import CLASSES, BaseModel, Prediction  # noqa: E402


def series(n: int = 400, seed: int = 11) -> np.ndarray:
    """A mean-reverting tape — the same generator the agent graph observes."""
    rng = random.Random(seed)
    p, out = 100.0, []
    for _ in range(n):
        p += 0.02 * (100.0 - p) + rng.gauss(0, 0.6)
        out.append(p)
    return np.array(out)


@pytest.fixture(scope="module")
def data():
    return build_dataset(series())


# ── the common interface ────────────────────────────────────────────────────

def test_there_are_four_model_classes():
    """Section 11 names exactly four."""
    assert set(all_models()) == {
        "baseline", "gradient_boosting", "cnn_lstm", "transformer"
    }


@pytest.mark.parametrize("name", ["baseline", "gradient_boosting", "cnn_lstm", "transformer"])
def test_every_model_satisfies_the_interface(name, data):
    X_features, X_windows, _ = data
    model = all_models()[name]
    assert isinstance(model, BaseModel)

    payload = X_features[0] if name in TABULAR else X_windows[0]
    prediction = model.predict(payload)

    assert isinstance(prediction, Prediction)
    assert prediction.direction in CLASSES
    assert 0.0 <= prediction.confidence <= 1.0
    assert np.isfinite(prediction.expected_return)
    assert prediction.model_version and prediction.model_hash


@pytest.mark.parametrize("name", ["baseline", "gradient_boosting", "cnn_lstm", "transformer"])
def test_predict_proba_is_a_distribution(name, data):
    X_features, X_windows, _ = data
    model = all_models()[name]
    payload = X_features[0] if name in TABULAR else X_windows[0]
    proba = model.predict_proba(payload)

    assert proba.shape == (3,)
    assert np.all(proba >= 0)
    assert proba.sum() == pytest.approx(1.0, abs=1e-9)


# ── model identity (invariant 3) ────────────────────────────────────────────

@pytest.mark.parametrize("name", ["baseline", "gradient_boosting", "cnn_lstm", "transformer"])
def test_model_hash_is_reproducible(name):
    """The same configuration must produce the same identity, every time."""
    assert all_models(seed=0)[name].model_hash == all_models(seed=0)[name].model_hash


def test_model_hash_is_a_sha256_digest():
    for model in all_models().values():
        assert len(model.model_hash) == 64
        int(model.model_hash, 16)  # raises if not hex


def test_different_models_have_different_identities():
    hashes = {m.model_hash for m in all_models().values()}
    assert len(hashes) == 4


def test_training_changes_the_model_identity(data):
    """
    Invariant 3: a new model version must be distinguishable from the last.
    The on-chain registry rejects an `update_model` whose hash is unchanged, so
    a fitted model that hashed the same as its unfitted self would make the
    version history a lie.
    """
    X_features, _, y = data
    model = all_models(seed=0)["gradient_boosting"]
    before = model.model_hash
    model.fit(X_features[:200], y[:200])
    assert model.model_hash != before


def test_the_baseline_needs_no_training_to_have_an_identity():
    """It has no learned parameters, so its hash comes from its configuration."""
    model = all_models()["baseline"]
    assert model.model_hash and not getattr(model, "fitted", False)


# ── features ────────────────────────────────────────────────────────────────

def test_feature_vector_shape_and_order():
    f = extract(series(100))
    assert f.shape == (N_FEATURES,)
    assert FEATURE_NAMES[:3] == ("momentum", "volatility", "z_score")
    assert np.all(np.isfinite(f))


def test_features_are_deterministic():
    prices = series(100)
    assert np.array_equal(extract(prices), extract(prices))


def test_build_dataset_returns_raw_price_windows():
    """
    The sequence models normalise internally. Handing them pre-normalised data
    differenced it twice and produced predicted returns of ~360,000%, so the
    contract is pinned here.
    """
    _, windows, _ = build_dataset(series(200))
    assert windows.min() > 1.0, "windows must be prices, not returns"


# ── the baseline comparison (section 11's explicit requirement) ─────────────

def test_evaluation_reports_every_model_with_a_verdict():
    scores = evaluate_all(series(400), seed=0, train=True)
    assert set(scores) == {"baseline", "gradient_boosting", "cnn_lstm", "transformer"}
    assert scores["baseline"].verdict.startswith("BASELINE")
    for name, score in scores.items():
        assert score.verdict != "UNSCORED", f"{name} was never compared"


def test_report_names_the_comparison_explicitly():
    """"Don't bury it" — the verdict must appear in the printed output."""
    report = format_report(evaluate_all(series(400), seed=0, train=True))
    assert "verdict" in report
    assert "Beating the baseline:" in report
    for name in ("baseline", "gradient_boosting", "cnn_lstm", "transformer"):
        assert name in report


def _score(name: str, accuracy: float, mse: float, dominant: float) -> ModelScore:
    return ModelScore(
        name=name, model_version="v", model_hash="h",
        accuracy=accuracy, directional_accuracy=accuracy, mse=mse, mae=0.0,
        trades=10, confusion=np.zeros((3, 3), dtype=int),
        dominant_class_share=dominant,
    )


def test_a_degenerate_model_cannot_beat_the_baseline():
    """
    The regression this test locks down: a model answering the same class every
    time posted a higher accuracy than the baseline and was called a winner.
    """
    scores = compare_to_baseline({
        "baseline": _score("baseline", 0.42, 1e-4, 0.4),
        "degenerate": _score("degenerate", 0.99, 1e-4, 1.0),
    })
    assert not scores["degenerate"].beats_baseline
    assert "DEGENERATE" in scores["degenerate"].verdict


def test_a_model_with_wild_regression_error_cannot_beat_the_baseline():
    """Right about direction, absurd about magnitude — magnitude sizes the position."""
    scores = compare_to_baseline({
        "baseline": _score("baseline", 0.42, 1e-4, 0.4),
        "wild": _score("wild", 0.99, 1e4, 0.4),
    })
    assert not scores["wild"].beats_baseline
    assert "REJECTED" in scores["wild"].verdict


def test_a_genuinely_better_model_is_recognised():
    """The disqualifiers must not be so strict that nothing can ever win."""
    scores = compare_to_baseline({
        "baseline": _score("baseline", 0.42, 1e-4, 0.4),
        "good": _score("good", 0.64, 2e-5, 0.45),
    })
    assert scores["good"].beats_baseline


def test_degenerate_threshold_is_a_share_not_a_count():
    assert 0.5 < DEGENERATE_SHARE <= 1.0


# ── models must actually differ ─────────────────────────────────────────────

def test_models_disagree_on_the_same_input(data):
    """
    Four classes that all produced the same number would make the comparison
    theatre. They read different representations and must land differently.
    """
    X_features, X_windows, _ = data
    predictions = {
        name: model.predict(X_features[5] if name in TABULAR else X_windows[5]).expected_return
        for name, model in all_models(seed=0).items()
    }
    assert len(set(round(v, 10) for v in predictions.values())) > 1


# ── confidence means what it says ───────────────────────────────────────────
# These lock down two bugs that Phase 4's evaluation could not see, because it
# scored direction and magnitude and never looked at confidence at all. Both
# were found by the Phase 3 gate after the models were wired into the agent
# graph, where confidence is what the validation floor gates on.

@pytest.mark.parametrize("name", ["baseline", "gradient_boosting", "cnn_lstm", "transformer"])
def test_confidence_is_the_probability_of_the_predicted_direction(name, data):
    """
    Bug 1: `confidence` was `max(proba)` — the probability of the *likeliest*
    class, which is not necessarily the class being predicted. A model
    proposing BUY could report the probability it had assigned to HOLD, and the
    agent graph's 0.55 validation floor then gated on that number as though it
    meant "how sure are you about this trade".
    """
    X_features, X_windows, _ = data
    model = all_models(seed=0)[name]
    if hasattr(model, "fit"):
        payload_train = X_features if name in TABULAR else X_windows
        model.fit(payload_train[:200], _train_targets(data)[:200])

    for i in range(0, 120, 9):
        payload = X_features[i] if name in TABULAR else X_windows[i]
        prediction = model.predict(payload)
        proba = model.predict_proba(payload)
        expected = float(proba[CLASSES.index(prediction.direction)])
        assert prediction.confidence == pytest.approx(expected, abs=1e-9), (
            f"{name} reported confidence {prediction.confidence:.4f} for "
            f"{prediction.direction} but assigned it {expected:.4f}"
        )


@pytest.mark.parametrize("name", ["baseline", "gradient_boosting", "cnn_lstm", "transformer"])
def test_confidence_can_span_a_usable_range(name, data):
    """
    Bug 2: the HOLD logit was a hardcoded 0.35, which put a floor near 0.29 and
    a ceiling near 0.415 on `max(proba)` whenever the predicted move was small.
    Confidence was therefore not comparable between models, and no CNN-LSTM
    agent could ever clear the graph's validation floor — that whole strategy
    silently never traded.

    This asserts the *mechanism* is unpinned, not that any given model is
    confident: a genuinely uncertain model should still report low confidence.
    """
    from ml.models.base import direction_probabilities

    tight = direction_probabilities(0.05, spread=0.001, threshold=0.0005)
    assert tight.max() > 0.9, "a strong signal must be able to reach high confidence"

    wide = direction_probabilities(0.0005, spread=0.05, threshold=0.0005)
    assert wide.max() < 0.5, "a signal buried in noise must not look confident"


def test_a_precise_model_predicting_no_move_is_confident_about_it(data):
    """
    HOLD is a claim, not an absence of one. A model whose errors are far
    smaller than the tradeable band is genuinely sure nothing is happening, and
    the distribution should say so.
    """
    from ml.models.base import HOLD, direction_probabilities

    proba = direction_probabilities(0.0, spread=0.00001, threshold=0.0005)
    assert proba.argmax() == HOLD and proba[HOLD] > 0.9


def _train_targets(data):
    return data[2]


# ── the uncertainty head is actually trained ────────────────────────────────

@pytest.mark.parametrize("name", ["cnn_lstm", "transformer"])
def test_the_spread_head_learns(name, data):
    """
    `spread` was never in the training loss — `pred, _ = self.net(xb)` — so it
    received no gradient and reported whatever its random initialisation gave.
    Confidence is `expected_return / spread`, so every confidence these models
    ever produced was an arbitrary constant. Its magnitude looked plausible
    only because `_target_scale` multiplies it.

    Two things must hold for it to mean anything: fitting has to move it, and
    it has to vary per input. A constant spread is a constant confidence, which
    is the same failure wearing a trained-looking number.
    """
    _, X_windows, y = data
    model = all_models(seed=0)[name]

    before = np.array([model._forward(X_windows[i])[1] for i in range(0, 60, 6)])
    model.fit(X_windows[:200], y[:200])
    after = np.array([model._forward(X_windows[i])[1] for i in range(0, 60, 6)])

    assert not np.allclose(before, after), "fitting must move the spread head"
    assert after.std() > 1e-5, (
        f"{name} reports a near-constant spread ({after.std():.2e}); "
        f"confidence derived from it carries no information"
    )


@pytest.mark.parametrize("name", ["cnn_lstm", "transformer"])
def test_the_spread_is_the_right_order_of_magnitude(name, data):
    """
    Trained against |residual|, so it should land near the scale of the targets
    rather than at an arbitrary constant. A spread ten times too large makes
    every prediction look unconfident; ten times too small makes every one look
    certain.
    """
    _, X_windows, y = data
    model = all_models(seed=0)[name]
    model.fit(X_windows[:200], y[:200])

    spread = np.mean([model._forward(X_windows[i])[1] for i in range(0, 60, 6)])
    target_scale = float(np.mean(np.abs(y)))
    assert 0.1 * target_scale < spread < 10 * target_scale, (
        f"{name} spread {spread:.6f} against a target scale of {target_scale:.6f}"
    )


@pytest.mark.parametrize(
    "name", ["baseline", "gradient_boosting", "cnn_lstm", "transformer"]
)
def test_a_model_can_reach_a_tradeable_confidence(name, data):
    """
    The agent graph will not commit below 0.55. A model that cannot exceed that
    on any input is not cautious, it is inert — the strategy built on it can
    never trade.

    This is the property the leftover 2x / 4x error-scale multipliers broke for
    the tabular models, and the untrained spread head broke for CNN-LSTM.
    """
    X_features, X_windows, y = data
    model = all_models(seed=0)[name]
    if hasattr(model, "fit"):
        model.fit((X_features if name in TABULAR else X_windows)[:250], y[:250])

    inputs = X_features if name in TABULAR else X_windows
    best = max(
        model.predict(inputs[i]).confidence
        for i in range(0, min(len(inputs), 400), 3)
    )
    assert best > 0.55, (
        f"{name} never exceeds confidence {best:.3f}; the 0.55 validation "
        f"floor makes it structurally unable to trade"
    )
