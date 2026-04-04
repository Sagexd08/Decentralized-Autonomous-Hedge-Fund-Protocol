import math
import time
from typing import Any

import numpy as np
from fastapi import APIRouter

from api.agents import AGENTS
from core.allocation import risk_adjusted_return

router = APIRouter()

_AGENT_MODELS = {
    "AlphaWave": "LSTM Momentum Stack",
    "QuantSigma": "Z-Score Mean Reversion",
    "NeuralArb": "Transformer Arbitrage",
    "VoltexAI": "HMM Volatility Breakout",
    "FluxArb": "Cointegration Pairs Engine",
    "DeltaHedge": "Greeks Hedger",
    "OmegaFlow": "Liquidation Cascade Detector",
    "StableYield": "Yield Optimizer",
    "NovaSurge": "RL Scalping Policy",
}

_STAGE_ORDER = [
    "market_data",
    "feature_engineering",
    "regime_detection",
    "agent_decisions",
    "risk_engine",
    "execution",
    "performance",
    "allocation",
    "slashing",
]


def _agent_snapshot(agent: dict[str, Any], regime: str, phase: float) -> dict[str, Any]:
    confidence = round(
        max(0.35, min(0.97, 0.55 + agent["sharpe"] * 0.08 - abs(agent["drawdown"]) * 0.006 + math.sin(phase) * 0.04)),
        2,
    )
    var_95 = round(max(1.2, agent["volatility"] * 0.42 + abs(agent["drawdown"]) * 0.18), 2)
    anomaly = max(0.01, min(0.94, (abs(agent["drawdown"]) / 20) + (agent["volatility"] / 60) - (agent["sharpe"] / 10)))
    trust = max(1, min(100, int(round(agent["score"] * 0.55 + agent["sharpe"] * 12 - abs(agent["drawdown"]) * 0.8))))
    risk_score = round(risk_adjusted_return(agent["pnl"] / 100, max(agent["volatility"] / 100, 0.01), abs(agent["drawdown"]) / 100), 4)
    rogue = anomaly > 0.55 or trust < 55 or agent["status"] == "probation"
    decision = "BUY" if confidence >= 0.74 else "SELL" if anomaly > 0.48 else "HOLD"
    return {
        "id": agent["id"],
        "name": agent["name"],
        "strategy": agent["strategy"],
        "model": _AGENT_MODELS.get(agent["name"], "Hybrid Strategy"),
        "risk": agent["risk"],
        "regime_context": regime,
        "capital_allocated_pct": agent["allocation"],
        "historical_return_pct": agent["pnl"],
        "sharpe_ratio": agent["sharpe"],
        "drawdown_pct": agent["drawdown"],
        "confidence_score": confidence,
        "trust_score": trust,
        "var_95_pct": var_95,
        "anomaly_score": round(anomaly, 2),
        "stake_locked": agent["stake"],
        "decision": decision,
        "decision_signed": True,
        "risk_adjusted_score": risk_score,
        "rogue_flag": rogue,
        "status": "slashing_watch" if rogue else "healthy",
        "dna": {
            "style": agent["strategy"],
            "model_family": _AGENT_MODELS.get(agent["name"], "Hybrid Strategy"),
            "primary_edge": "speed" if "Arb" in agent["name"] else "adaptation" if agent["name"] in {"AlphaWave", "NovaSurge", "VoltexAI"} else "risk discipline",
            "time_horizon": "intraday" if agent["risk"] == "Aggressive" else "swing" if agent["risk"] == "Balanced" else "defensive carry",
        },
    }


def _build_loop_state() -> dict[str, Any]:
    now = time.time()
    phase = now / 11
    regimes = ["trending", "mean-reverting", "stress"]
    regime = regimes[int(now / 17) % len(regimes)]
    leader_names = {"trending": ["AlphaWave", "NovaSurge"], "mean-reverting": ["QuantSigma", "FluxArb"], "stress": ["VoltexAI", "StableYield"]}
    snapshots = [_agent_snapshot(agent, regime, phase + index) for index, agent in enumerate(AGENTS)]
    snapshots.sort(key=lambda item: (item["trust_score"], item["confidence_score"]), reverse=True)
    loop_index = int(now // 3)
    stage_index = loop_index % len(_STAGE_ORDER)
    stage_status = []
    for idx, stage in enumerate(_STAGE_ORDER):
        if idx < stage_index:
            status = "complete"
        elif idx == stage_index:
            status = "active"
        else:
            status = "pending"
        stage_status.append({"key": stage, "label": stage.replace("_", " ").title(), "status": status})
    slashed = [agent for agent in snapshots if agent["rogue_flag"]]
    leader_board = []
    for position, agent in enumerate(snapshots[:5], start=1):
        leader_board.append({
            "rank": position,
            "agent_id": agent["id"],
            "name": agent["name"],
            "trust_score": agent["trust_score"],
            "confidence_score": agent["confidence_score"],
            "capital_allocated_pct": agent["capital_allocated_pct"],
            "model": agent["model"],
        })
    return {
        "timestamp": now,
        "loop_id": f"loop-{loop_index}",
        "regime": regime,
        "meta_agent": {
            "status": "observing",
            "recommendation": f"Boost {leader_names[regime][0]} and reduce exposure to any agent crossing anomaly score 0.55.",
            "capital_posture": "offensive" if regime == "trending" else "neutral" if regime == "mean-reverting" else "defensive",
        },
        "system_metrics": {
            "portfolio_var_95_pct": round(float(np.mean([agent["var_95_pct"] for agent in snapshots])), 2),
            "avg_confidence": round(float(np.mean([agent["confidence_score"] for agent in snapshots])), 2),
            "autonomy_score": 94,
            "execution_latency_ms": 1480,
            "ui_latency_ms": 320,
            "active_agents": len(snapshots),
        },
        "stage_status": stage_status,
        "leaderboard": leader_board,
        "agents": snapshots,
        "allocation_summary": {
            "winners": leader_names[regime],
            "watchlist": [agent["name"] for agent in slashed[:2]],
            "capital_rotation": "MWU reweights every epoch using risk-adjusted scores and reputation decay.",
        },
        "slashing_summary": {
            "candidates": [
                {
                    "agent_id": agent["id"],
                    "name": agent["name"],
                    "reason": "Anomaly score breached risk threshold" if agent["anomaly_score"] > 0.55 else "Probationary performance below trust floor",
                    "slash_pct": 10 if agent["anomaly_score"] > 0.55 else 4,
                }
                for agent in slashed[:3]
            ],
            "slash_count": len(slashed),
        },
    }


@router.get("/loop")
def get_loop_state():
    return _build_loop_state()


@router.get("/demo")
def get_demo_state():
    state = _build_loop_state()
    slashing_target = state["slashing_summary"]["candidates"][0]["name"] if state["slashing_summary"]["candidates"] else "DeltaHedge"
    steps = [
        {"step": 1, "title": "Market pulse updates", "description": "Live prices, macro headlines, and social signals stream into the protocol.", "status": "complete"},
        {"step": 2, "title": "Agents think in parallel", "description": "Stateful agents score the regime and emit signed BUY / SELL / HOLD actions.", "status": "complete"},
        {"step": 3, "title": "Risk engine filters execution", "description": "VaR, anomaly, and drawdown constraints reject unsafe moves before capital moves.", "status": "active"},
        {"step": 4, "title": "MWU reallocates capital", "description": f"Capital rotates toward {', '.join(state['allocation_summary']['winners'])} as regret-minimizing weights update.", "status": "pending"},
        {"step": 5, "title": "Weak agent gets slashed", "description": f"{slashing_target} is flagged for economic punishment after breaching protocol trust thresholds.", "status": "pending"},
        {"step": 6, "title": "Governance adapts the organism", "description": "AI-assisted governance suggests parameter updates for the next market regime.", "status": "pending"},
    ]
    return {
        "headline": "We built a self-evolving financial organism.",
        "judge_script": steps,
        "talking_points": [
            "Capital is programmable, but intelligence is decentralized.",
            "Agents compete for capital under cryptoeconomic enforcement.",
            "Risk controls are visible, algorithmic, and explainable.",
            "Governance can tune the organism without breaking custody assumptions.",
        ],
        "contract_prompt_example": "Create a hedge fund that rebalances every hour based on volatility and slashes agents after a 15% drawdown.",
        "loop_snapshot": state,
    }


@router.get("/governance-suggestions")
def get_governance_suggestions():
    state = _build_loop_state()
    regime = state["regime"]
    if regime == "trending":
        suggestions = [
            {"title": "Raise learning rate η to 0.014", "reason": "Trending markets reward faster capital rotation into persistent winners.", "impact": "allocation"},
            {"title": "Increase max single-agent allocation to 38%", "reason": "Top-performing agents are showing stable confidence above 0.8.", "impact": "risk"},
        ]
    elif regime == "mean-reverting":
        suggestions = [
            {"title": "Lower learning rate η to 0.009", "reason": "Reduce overreaction while mean-reversion edges churn quickly.", "impact": "allocation"},
            {"title": "Boost balanced-pool capital share", "reason": "Balanced strategies are dominating trust-adjusted leaderboards.", "impact": "pools"},
        ]
    else:
        suggestions = [
            {"title": "Tighten slashing threshold to 17% drawdown", "reason": "Stress regime requires stronger rogue-agent deterrence.", "impact": "risk"},
            {"title": "Reduce aggressive pool volatility cap by 300 bps", "reason": "Portfolio VaR is elevated and anomaly detections are rising.", "impact": "risk"},
        ]
    return {
        "regime": regime,
        "suggestions": suggestions,
        "predictive_vote_outcome": {
            "pass_probability": 0.71 if regime != "stress" else 0.82,
            "delegation_bias": "risk delegates" if regime == "stress" else "performance delegates",
        },
    }
