"""
Model registry and the baseline comparison — IRIS_BUILD_PROMPT v2.0 section 11.

Section 11: "Baseline exists so ML has something to beat — track this
comparison explicitly in the evaluation output, don't bury it."

So `compare_to_baseline` is not an optional diagnostic tucked behind a flag.
It returns a verdict per model — BEATS BASELINE / MATCHES BASELINE / LOSES TO
BASELINE — and `format_report` prints it, because a comparison you have to go
looking for is one nobody looks at.

Evaluation is on direction (SELL / HOLD / BUY), not regression loss alone. A
model can win on MSE by predicting a flat near-zero everywhere and be useless
to trade, so the confusion matrix is what the report leads with.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from ml.features.extract import build_dataset
from ml.models.base import CLASSES, BaseModel, Prediction, direction_from_return
from ml.models.baseline import BaselineModel
from ml.models.cnn_lstm import CnnLstmModel
from ml.models.gradient_boosting import GradientBoostingModel
from ml.models.transformer import TransformerModel

# Models that read the shared feature vector vs. the raw price window.
TABULAR = {"baseline", "gradient_boosting"}

# Which model class backs which strategy.
#
# Lives here rather than in the graph because it is a fact about the model
# registry, not about the node that looks it up — and `ml` must not import
# `agents` to find out which models it is expected to have fitted.
STRATEGY_MODELS = {
    "momentum": "cnn_lstm",
    "mean_reversion": "gradient_boosting",
    "breakout": "baseline",
    "adaptive": "transformer",
}

DEFAULT_FAMILY = "cnn_lstm"


def family_for_strategy(strategy: str) -> str:
    """The model family a strategy runs on."""
    return STRATEGY_MODELS.get(strategy, DEFAULT_FAMILY)

# A model emitting one class for this share of samples is not predicting.
DEGENERATE_SHARE = 0.90

# How much worse a model's regression error may be than the baseline's before
# its direction accuracy stops counting as a win. A model can be right about
# direction while being wildly wrong about magnitude, and magnitude is what
# sizes the position.
MSE_TOLERANCE = 10.0


def all_models(seed: int = 0) -> dict[str, BaseModel]:
    """One instance of each of the four classes required by section 11."""
    return {
        "baseline": BaselineModel(),
        "gradient_boosting": GradientBoostingModel(seed=seed),
        "cnn_lstm": CnnLstmModel(seed=seed),
        "transformer": TransformerModel(seed=seed),
    }


@dataclass
class ModelScore:
    name: str
    model_version: str
    model_hash: str
    accuracy: float
    directional_accuracy: float   # accuracy on the bars where it took a side
    mse: float
    mae: float
    trades: int                   # non-HOLD predictions
    confusion: np.ndarray = field(repr=False)
    dominant_class_share: float = 0.0
    verdict: str = "UNSCORED"

    @property
    def is_degenerate(self) -> bool:
        """
        A model that answers the same thing almost every time.

        This is worth naming because such a model can post a respectable
        accuracy purely from class imbalance while carrying no information at
        all — and would otherwise be reported as beating the baseline.
        """
        return self.dominant_class_share >= DEGENERATE_SHARE

    @property
    def beats_baseline(self) -> bool:
        return self.verdict == "BEATS BASELINE"


def _true_direction(returns: np.ndarray, threshold: float) -> list[str]:
    return [direction_from_return(float(r), threshold) for r in returns]


def score_model(
    model: BaseModel,
    name: str,
    X_features: np.ndarray,
    X_windows: np.ndarray,
    y: np.ndarray,
    threshold: float = 0.0005,
) -> ModelScore:
    inputs = X_features if name in TABULAR else X_windows
    preds: list[Prediction] = [model.predict(row) for row in inputs]

    predicted_dirs = [p.direction for p in preds]
    predicted_rets = np.array([p.expected_return for p in preds], dtype=np.float64)
    truth = _true_direction(y, threshold)

    correct = sum(int(a == b) for a, b in zip(predicted_dirs, truth))
    accuracy = correct / max(len(truth), 1)

    took_a_side = [i for i, d in enumerate(predicted_dirs) if d != "HOLD"]
    directional = (
        sum(int(predicted_dirs[i] == truth[i]) for i in took_a_side) / len(took_a_side)
        if took_a_side
        else 0.0
    )

    confusion = np.zeros((3, 3), dtype=int)
    index = {c: i for i, c in enumerate(CLASSES)}
    for actual, predicted in zip(truth, predicted_dirs):
        confusion[index[actual], index[predicted]] += 1

    counts = np.bincount([index[d] for d in predicted_dirs], minlength=3)
    dominant = float(counts.max() / max(counts.sum(), 1))

    return ModelScore(
        name=name,
        model_version=model.model_version,
        model_hash=model.model_hash,
        accuracy=accuracy,
        directional_accuracy=directional,
        mse=float(np.mean((predicted_rets - y) ** 2)),
        mae=float(np.mean(np.abs(predicted_rets - y))),
        trades=len(took_a_side),
        confusion=confusion,
        dominant_class_share=dominant,
    )


def compare_to_baseline(scores: dict[str, ModelScore], margin: float = 0.01) -> dict[str, ModelScore]:
    """
    Stamp every model with its verdict against the baseline.

    `margin` keeps a rounding difference from being reported as a win. A model
    within a point of a free, untrainable rule has not earned its complexity,
    and saying so is the entire purpose of keeping the baseline around.
    """
    baseline = scores.get("baseline")
    if baseline is None:
        return scores

    for name, score in scores.items():
        if name == "baseline":
            score.verdict = (
                "BASELINE (DEGENERATE)" if score.is_degenerate else "BASELINE"
            )
            continue

        # Two disqualifications before accuracy is even consulted. Both were
        # added after a transformer that predicted BUY for every single sample,
        # with an MSE of 1.96e+11, was reported as beating the baseline on
        # accuracy alone.
        if score.is_degenerate:
            score.verdict = (
                f"DEGENERATE — one class {score.dominant_class_share:.0%} of the time"
            )
            continue
        if score.mse > baseline.mse * MSE_TOLERANCE:
            score.verdict = (
                f"REJECTED — MSE {score.mse / baseline.mse:.0f}x the baseline's"
            )
            continue

        delta = score.accuracy - baseline.accuracy
        if delta > margin:
            score.verdict = "BEATS BASELINE"
        elif delta < -margin:
            score.verdict = "LOSES TO BASELINE"
        else:
            score.verdict = "MATCHES BASELINE"
    return scores


def evaluate_all(prices: np.ndarray, seed: int = 0, train: bool = True) -> dict[str, ModelScore]:
    """
    Fit (optionally) and score all four models on one series.

    Scored **out of sample**. When this fits, it fits on the first 70% and
    scores on the remaining 30%; scoring on the whole series would let a fitted
    model be graded partly on data it had already seen, while the baseline —
    which fits nothing — was graded on all of it throughout. The comparison
    that Phase 4 exists to make is only meaningful if both sides face the same
    exam, and an in-sample advantage flatters exactly the models whose value is
    most in question.
    """
    X_features, X_windows, y = build_dataset(prices)
    models = all_models(seed=seed)

    start = 0
    if train:
        split = int(len(y) * 0.7)
        models["gradient_boosting"].fit(X_features[:split], y[:split])
        models["cnn_lstm"].fit(X_windows[:split], y[:split])
        models["transformer"].fit(X_windows[:split], y[:split])
        start = split

    scores = {
        name: score_model(
            model, name, X_features[start:], X_windows[start:], y[start:]
        )
        for name, model in models.items()
    }
    return compare_to_baseline(scores)


def format_report(scores: dict[str, ModelScore]) -> str:
    """The comparison, printed where it cannot be missed."""
    lines = [
        "",
        "Model evaluation — direction accuracy, not regression loss alone.",
        "A model can win on MSE by predicting flat and still be untradeable.",
        "",
        f"{'model':<20}{'version':<22}{'acc':>7}{'dir-acc':>9}{'trades':>8}"
        f"{'mse':>12}   verdict",
        "-" * 100,
    ]
    order = ["baseline"] + [n for n in scores if n != "baseline"]
    for name in order:
        s = scores[name]
        lines.append(
            f"{s.name:<20}{s.model_version:<22}{s.accuracy:>7.3f}"
            f"{s.directional_accuracy:>9.3f}{s.trades:>8}{s.mse:>12.3e}   {s.verdict}"
        )

    lines += ["", "Confusion matrices (rows = actual, cols = predicted; SELL/HOLD/BUY)"]
    for name in order:
        lines.append(f"  {name}")
        for row_name, row in zip(CLASSES, scores[name].confusion):
            lines.append(f"    {row_name:<5}" + "".join(f"{v:>7}" for v in row))

    beaten = [s.name for s in scores.values() if s.beats_baseline]
    lines += [
        "",
        f"Beating the baseline: {', '.join(beaten) if beaten else 'none'}",
        "",
    ]
    return "\n".join(lines)
