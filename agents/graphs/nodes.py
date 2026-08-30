"""
Trading graph nodes — IRIS_BUILD_PROMPT v2.0 section 10.

    MARKET_OBSERVATION -> FEATURE_EXTRACTION -> REGIME_ANALYSIS
    -> HISTORICAL_RETRIEVAL -> MODEL_INFERENCE -> RISK_ANALYSIS
    -> DECISION -> VALIDATION -> PREDICTION_COMMIT -> EXECUTION/ABSTAIN
    -> OUTCOME_TRACKING

Each node is a plain typed function on AgentState returning a partial update.
They are ordinary functions, not methods, so they can be unit-tested in
isolation without constructing a graph.

Two rules from the spec are load-bearing here and are not stylistic:

  * **RISK_ANALYSIS and VALIDATION contain no model call of any kind.** They
    are the deterministic gate between a proposal and capital. If either ever
    grows a dependency on an LLM or a learned model, the hard boundary in
    section 10 is gone and a prompt can move money.

  * **PREDICTION_COMMIT hashes the prediction before the outcome exists.**
    `committed_at` must precede `horizon_end`, and the database enforces that
    independently (see db/migrations/0001_init.sql).

What is deliberately *not* here, because it belongs to a later phase:
  * settlement and scoring — Phase 5. OUTCOME_TRACKING records what to watch
    and stops.
  * pgvector retrieval — Phase 12. HISTORICAL_RETRIEVAL returns an empty,
    explicitly-labelled result rather than fabricated analogues.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from agents.state import (
    AgentState,
    Decision,
    Node,
    RiskAssessment,
    ValidationResult,
)

# ── risk limits ─────────────────────────────────────────────────────────────
# Phase 8 moves these into the on-chain risk engine and governance. Until then
# they live here as named constants rather than magic numbers inline.
MAX_VOLATILITY_BPS = 3500
MAX_DRAWDOWN_BPS = 2000
MIN_CONFIDENCE = 0.55
MAX_EXPECTED_RETURN = 0.25  # a model claiming >25% over one horizon is broken
DEFAULT_HORIZON_SECONDS = 600


def _now() -> float:
    return time.time()


def _timed(node: Node, started: float) -> dict[str, dict[str, int]]:
    return {"node_latency_ms": {node.value: int((_now() - started) * 1000)}}


# ── 1. MARKET_OBSERVATION ───────────────────────────────────────────────────

def market_observation(state: AgentState) -> dict[str, Any]:
    """
    Pull the price window the rest of the graph reasons over.

    Synthetic and labelled as such. The series is seeded from the run so a
    replay of the same run produces the same tape — section 18 requires
    simulation to be reproducible, and that has to hold at the source.
    """
    started = _now()
    rng = random.Random(state.seed)

    price = 100.0
    prices: list[float] = []
    for _ in range(64):
        # Ornstein-Uhlenbeck-ish: mean-reverting with noise
        price += 0.02 * (100.0 - price) + rng.gauss(0, 0.6)
        prices.append(round(price, 6))

    return {
        "prices": prices,
        "observed_at": _now(),
        "data_source": "SIMULATION",
        **_timed(Node.MARKET_OBSERVATION, started),
    }


# ── 2. FEATURE_EXTRACTION ───────────────────────────────────────────────────

def feature_extraction(state: AgentState) -> dict[str, Any]:
    """Derive the features the model and the risk layer both read."""
    started = _now()
    p = state.prices
    if len(p) < 8:
        return {
            "errors": [*state.errors, "FEATURE_EXTRACTION: price window too short"],
            **_timed(Node.FEATURE_EXTRACTION, started),
        }

    returns = [(p[i] - p[i - 1]) / p[i - 1] for i in range(1, len(p))]
    mean_return = statistics.fmean(returns)
    vol = statistics.pstdev(returns)

    peak, drawdown = p[0], 0.0
    for price in p:
        peak = max(peak, price)
        drawdown = min(drawdown, (price - peak) / peak)

    window = p[-8:]
    features = {
        "last": p[-1],
        "mean_return": mean_return,
        "volatility": vol,
        "momentum": (p[-1] - p[-8]) / p[-8],
        "z_score": (p[-1] - statistics.fmean(window)) / (statistics.pstdev(window) or 1e-9),
        "max_drawdown": drawdown,
        "range_pct": (max(window) - min(window)) / (min(window) or 1e-9),
    }
    return {"features": features, **_timed(Node.FEATURE_EXTRACTION, started)}


# ── 3. REGIME_ANALYSIS ──────────────────────────────────────────────────────

def regime_analysis(state: AgentState) -> dict[str, Any]:
    """
    Classify the volatility regime.

    Phase 4 replaces this with the HMM classifier. The thresholds here are a
    placeholder, and the node says so via `regime_confidence` rather than
    pretending to a certainty it has not earned.
    """
    started = _now()
    vol = state.features.get("volatility", 0.0)

    if vol < 0.004:
        regime, confidence = "CALM", 0.6
    elif vol < 0.010:
        regime, confidence = "NORMAL", 0.6
    else:
        regime, confidence = "STRESSED", 0.6

    return {
        "regime": regime,
        "regime_confidence": confidence,
        **_timed(Node.REGIME_ANALYSIS, started),
    }


# ── 4. HISTORICAL_RETRIEVAL ─────────────────────────────────────────────────

def historical_retrieval(state: AgentState) -> dict[str, Any]:
    """
    Look up comparable historical regimes.

    Phase 12 wires this to pgvector over `market_events`. Returning an empty
    list is the honest answer today; returning invented analogues would be
    exactly the section 0c failure the spec forbids, and the downstream nodes
    would have no way to tell.
    """
    started = _now()
    return {"analogues": [], **_timed(Node.HISTORICAL_RETRIEVAL, started)}


# ── 5. MODEL_INFERENCE ──────────────────────────────────────────────────────

# Each strategy is backed by a different model class, so two agents on the same
# tape genuinely disagree rather than being palette-swaps of one formula
# (v2 section 10).
STRATEGY_MODELS = {
    "momentum": "cnn_lstm",
    "mean_reversion": "gradient_boosting",
    "breakout": "baseline",
    "adaptive": "transformer",
}


def model_inference(state: AgentState) -> dict[str, Any]:
    """
    Run the agent's model over the observed window.

    The model classes live in `ml/` behind one interface (v2 section 11); this
    node only picks which one the strategy uses and records its identity, so
    a prediction can always be traced back to the exact model version and
    weight hash that produced it.

    An untrained model is still a real forward pass, not a random number — but
    it is labelled `UNTRAINED` so nothing downstream mistakes it for a fitted
    one. Phase 13 loads trained weights.
    """
    started = _now()
    f = state.features
    if not f:
        return {
            "errors": [*state.errors, "MODEL_INFERENCE: no features"],
            **_timed(Node.MODEL_INFERENCE, started),
        }

    try:
        import numpy as np

        from ml.inference.registry import TABULAR, all_models
        from ml.features.extract import extract

        name = STRATEGY_MODELS.get(state.strategy, "cnn_lstm")
        model = all_models(seed=state.seed)[name]
        payload = (
            extract(np.asarray(state.prices))
            if name in TABULAR
            else np.asarray(state.prices)
        )
        prediction = model.predict(payload)

        return {
            "predicted_return": round(float(prediction.expected_return), 8),
            "model_confidence": round(float(prediction.confidence), 4),
            "inference_source": (
                f"{prediction.model_version}"
                f"{'' if getattr(model, 'fitted', False) else ' (UNTRAINED)'}"
            ),
            **_timed(Node.MODEL_INFERENCE, started),
        }
    except Exception as exc:
        # A model that will not load must not take the run down: the agent
        # abstains on low confidence instead of trading on a guess.
        return {
            "predicted_return": 0.0,
            "model_confidence": 0.0,
            "inference_source": f"UNAVAILABLE ({exc})",
            "errors": [*state.errors, f"MODEL_INFERENCE: {exc}"],
            **_timed(Node.MODEL_INFERENCE, started),
        }


# ── 6. RISK_ANALYSIS — deterministic, never a model call ────────────────────

def risk_analysis(state: AgentState) -> dict[str, Any]:
    """
    Measure risk and record any limit breaches.

    Deterministic by mandate (v2 section 10). This node decides nothing; it
    reports. VALIDATION acts on what it finds.
    """
    started = _now()
    f = state.features
    returns_vol = f.get("volatility", 0.0)
    drawdown = f.get("max_drawdown", 0.0)

    # Historical (non-parametric) VaR/CVaR over the observed window.
    p = state.prices
    returns = sorted((p[i] - p[i - 1]) / p[i - 1] for i in range(1, len(p))) if len(p) > 1 else [0.0]
    idx = max(0, int(math.floor(0.05 * len(returns))) - 1)
    var_95 = returns[idx]
    tail = returns[: idx + 1] or [var_95]
    cvar_95 = statistics.fmean(tail)

    volatility_bps = int(round(returns_vol * 10_000))
    drawdown_bps = int(round(abs(drawdown) * 10_000))

    breaches: list[str] = []
    if volatility_bps > MAX_VOLATILITY_BPS:
        breaches.append(f"volatility {volatility_bps}bps > {MAX_VOLATILITY_BPS}bps")
    if drawdown_bps > MAX_DRAWDOWN_BPS:
        breaches.append(f"drawdown {drawdown_bps}bps > {MAX_DRAWDOWN_BPS}bps")

    risk = RiskAssessment(
        volatility_bps=volatility_bps,
        var_95=round(var_95, 8),
        cvar_95=round(cvar_95, 8),
        drawdown_bps=drawdown_bps,
        exposure_ok=True,
        breaches=breaches,
    )
    return {"risk": risk, **_timed(Node.RISK_ANALYSIS, started)}


# ── 7. DECISION ─────────────────────────────────────────────────────────────

def decision(state: AgentState) -> dict[str, Any]:
    """
    Turn the prediction into a proposal.

    A *proposal*. Nothing here reaches capital; VALIDATION is next and it can
    reject anything this node produces.
    """
    started = _now()
    predicted = state.predicted_return
    if predicted is None:
        return {
            "errors": [*state.errors, "DECISION: no prediction"],
            **_timed(Node.DECISION, started),
        }

    threshold = 0.0005
    if predicted > threshold:
        direction = "BUY"
    elif predicted < -threshold:
        direction = "SELL"
    else:
        direction = "HOLD"

    proposal = Decision(
        direction=direction,
        expected_return=predicted,
        confidence=state.model_confidence,
        horizon_seconds=DEFAULT_HORIZON_SECONDS,
        rationale=(
            f"{state.strategy} on a {state.regime} regime; "
            f"predicted {predicted:+.4%} over {DEFAULT_HORIZON_SECONDS}s"
        ),
    )
    return {"decision": proposal, **_timed(Node.DECISION, started)}


# ── 8. VALIDATION — deterministic, never a model call ───────────────────────

def validation(state: AgentState) -> dict[str, Any]:
    """
    The gate. Free-form model output never reaches capital without passing
    here, and this function contains no model call of any kind (v2 section 10).

    A HOLD is not an error — it is simply nothing to commit, so it is rejected
    as "no position proposed" and the graph abstains.
    """
    started = _now()
    reasons: list[str] = []
    d = state.decision
    risk = state.risk

    if d is None:
        reasons.append("no decision proposed")
    if risk is None:
        reasons.append("no risk assessment")

    if d is not None:
        if d.direction == "HOLD":
            reasons.append("no position proposed")
        if d.confidence < MIN_CONFIDENCE:
            reasons.append(
                f"confidence {d.confidence:.2f} below floor {MIN_CONFIDENCE}"
            )
        if abs(d.expected_return) > MAX_EXPECTED_RETURN:
            reasons.append(
                f"expected return {d.expected_return:+.2%} exceeds the sanity "
                f"bound of {MAX_EXPECTED_RETURN:.0%} — treat as a broken model"
            )
        if d.horizon_seconds <= 0:
            reasons.append("non-positive horizon")

    if risk is not None:
        reasons.extend(risk.breaches)
        if not risk.exposure_ok:
            reasons.append("exposure limit breached")

    return {
        "validation": ValidationResult(approved=not reasons, reasons=reasons),
        **_timed(Node.VALIDATION, started),
    }


# ── 9. PREDICTION_COMMIT ────────────────────────────────────────────────────

def canonical_payload(
    *,
    agent_id: str,
    asset: str,
    direction: str,
    expected_return: float,
    confidence: float,
    horizon_seconds: int,
    model_version_id: str | None,
    committed_at: str,
) -> str:
    """
    The exact bytes that get hashed.

    Canonical because the hash is a commitment: sorted keys, no whitespace
    variation, fixed float formatting. Two runs that predict the same thing at
    the same instant must produce the same hash, and any change to the claim
    must produce a different one.
    """
    payload = {
        "agent_id": agent_id,
        "asset": asset,
        "direction": direction,
        "expected_return": f"{expected_return:.8f}",
        "confidence": f"{confidence:.5f}",
        "horizon_seconds": horizon_seconds,
        "model_version_id": model_version_id,
        "committed_at": committed_at,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def prediction_commit(state: AgentState) -> dict[str, Any]:
    """
    Hash and stamp the prediction *before* its outcome can be known.

    This is the core Web3 x ML primitive (v2 section 5). Phase 5 adds
    settlement and scoring; Phase 3 only has to produce a commitment that is
    stable, unique, and provably earlier than the horizon it is judged against.
    """
    started = _now()
    d = state.decision
    v = state.validation
    if d is None or v is None or not v.approved:
        return {
            "errors": [*state.errors, "PREDICTION_COMMIT reached without approval"],
            **_timed(Node.PREDICTION_COMMIT, started),
        }

    now = datetime.now(timezone.utc)
    committed_at = now.isoformat()
    horizon_end = (now + timedelta(seconds=d.horizon_seconds)).isoformat()

    payload = canonical_payload(
        agent_id=state.agent_id,
        asset=state.asset,
        direction=d.direction,
        expected_return=d.expected_return,
        confidence=d.confidence,
        horizon_seconds=d.horizon_seconds,
        model_version_id=state.model_version_id,
        committed_at=committed_at,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return {
        "prediction_hash": digest,
        "committed_at": committed_at,
        "horizon_end": horizon_end,
        **_timed(Node.PREDICTION_COMMIT, started),
    }


# ── 10a. EXECUTION ──────────────────────────────────────────────────────────

def execution(state: AgentState) -> dict[str, Any]:
    """
    Act on an approved, committed prediction.

    Phase 8 connects this to the vault. Today it marks the run as executed and
    nothing more — it does not pretend to have placed a trade.
    """
    started = _now()
    return {"executed": True, **_timed(Node.EXECUTION, started)}


# ── 10b. ABSTAIN ────────────────────────────────────────────────────────────

def abstain(state: AgentState) -> dict[str, Any]:
    """
    Decline to act, with the reason recorded.

    Abstention is a first-class outcome, not a failure. An agent that abstains
    when its own risk layer objects is behaving correctly, and the reason is
    kept so the Observatory can show *why*.
    """
    started = _now()
    reasons = state.validation.reasons if state.validation else ["no validation result"]
    return {
        "abstained": True,
        "abstain_reason": "; ".join(reasons) or "unspecified",
        **_timed(Node.ABSTAIN, started),
    }


# ── 11. OUTCOME_TRACKING ────────────────────────────────────────────────────

def outcome_tracking(state: AgentState) -> dict[str, Any]:
    """
    Record when this prediction becomes judgeable.

    Phase 5 owns the settlement sweep that reads `horizon_end` and scores the
    prediction. This node's whole job is to leave that marker behind.
    """
    started = _now()
    return {
        "tracking_until": state.horizon_end,
        **_timed(Node.OUTCOME_TRACKING, started),
    }


# ── routing ─────────────────────────────────────────────────────────────────

def route_after_validation(state: AgentState) -> str:
    """The only branch in the graph: approved commits, rejected abstains."""
    return "commit" if (state.validation and state.validation.approved) else "abstain"
