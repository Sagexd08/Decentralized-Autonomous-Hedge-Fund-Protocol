"""
Shared agent state — IRIS_BUILD_PROMPT v2.0 section 10.

Every node in the trading graph is a typed function over this object. The spec
is explicit that nodes must not mutate an implicit dict, so the state is a
Pydantic model and each node returns only the fields it actually sets.

The state is deliberately flat. A nested structure reads better on paper but
makes the Observatory (section 15) harder to render, and makes it harder to see
at a glance which node produced which field — so each field carries the node
that writes it in its description.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Node(str, Enum):
    """The graph's nodes, in execution order (v2 section 10)."""

    MARKET_OBSERVATION = "MARKET_OBSERVATION"
    FEATURE_EXTRACTION = "FEATURE_EXTRACTION"
    REGIME_ANALYSIS = "REGIME_ANALYSIS"
    HISTORICAL_RETRIEVAL = "HISTORICAL_RETRIEVAL"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    RISK_ANALYSIS = "RISK_ANALYSIS"
    DECISION = "DECISION"
    VALIDATION = "VALIDATION"
    PREDICTION_COMMIT = "PREDICTION_COMMIT"
    EXECUTION = "EXECUTION"
    ABSTAIN = "ABSTAIN"
    OUTCOME_TRACKING = "OUTCOME_TRACKING"


Direction = Literal["BUY", "SELL", "HOLD"]
Regime = Literal["CALM", "NORMAL", "STRESSED"]


class Decision(BaseModel):
    """
    What the agent proposes to do.

    This is the object the hard boundary in v2 section 10 is drawn around: a
    model — or, for the Adaptive Research agent, an LLM — may *propose* one of
    these, but a deterministic validator decides whether it ever reaches
    capital. Nothing downstream of VALIDATION trusts a field on this object
    without having checked it.
    """

    model_config = ConfigDict(frozen=True)

    direction: Direction
    expected_return: float = Field(description="fractional, not percent")
    confidence: float = Field(ge=0.0, le=1.0)
    horizon_seconds: int = Field(gt=0)
    rationale: str = ""


class RiskAssessment(BaseModel):
    """Output of RISK_ANALYSIS. Deterministic — never an LLM call."""

    model_config = ConfigDict(frozen=True)

    volatility_bps: int
    var_95: float
    cvar_95: float
    drawdown_bps: int
    exposure_ok: bool
    breaches: list[str] = Field(default_factory=list)

    @property
    def is_clear(self) -> bool:
        return not self.breaches


class ValidationResult(BaseModel):
    """
    Output of VALIDATION — the gate between a proposal and capital.

    `approved` is the only field the graph routes on. A rejection always
    carries reasons, so an abstention is explainable after the fact rather than
    a silent no-op.
    """

    model_config = ConfigDict(frozen=True)

    approved: bool
    reasons: list[str] = Field(default_factory=list)


def _merge(left: dict | None, right: dict | None) -> dict:
    """Reducer for accumulated node timings."""
    return {**(left or {}), **(right or {})}


class AgentState(BaseModel):
    """
    The object threaded through the graph.

    Nodes return partial updates; LangGraph merges them. Fields are grouped by
    the node that writes them.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ── run identity (set before the graph starts) ──────────────────────────
    agent_id: str
    agent_run_id: str
    asset: str
    strategy: str
    model_version_id: Optional[str] = None
    seed: int = 0

    # ── MARKET_OBSERVATION ──────────────────────────────────────────────────
    prices: list[float] = Field(default_factory=list)
    observed_at: Optional[float] = None
    data_source: str = "SIMULATION"
    # Where the window actually came from, in words — the venue and span for a
    # real feed, or the reason the node fell back to a synthetic tape. Written
    # into `graph_checkpoints`, so the Observatory can answer "what was this
    # agent looking at" for a run that happened last week.
    observation_note: str = ""
    price_provider: Optional[str] = None

    # ── FEATURE_EXTRACTION ──────────────────────────────────────────────────
    features: dict[str, float] = Field(default_factory=dict)

    # ── REGIME_ANALYSIS ─────────────────────────────────────────────────────
    regime: Optional[Regime] = None
    regime_confidence: float = 0.0

    # ── HISTORICAL_RETRIEVAL ────────────────────────────────────────────────
    analogues: list[dict[str, Any]] = Field(default_factory=list)

    # ── MODEL_INFERENCE ─────────────────────────────────────────────────────
    predicted_return: Optional[float] = None
    model_confidence: float = 0.0
    inference_source: str = "SIMULATION"

    # ── RISK_ANALYSIS ───────────────────────────────────────────────────────
    risk: Optional[RiskAssessment] = None

    # ── DECISION ────────────────────────────────────────────────────────────
    decision: Optional[Decision] = None

    # ── VALIDATION ──────────────────────────────────────────────────────────
    validation: Optional[ValidationResult] = None

    # ── PREDICTION_COMMIT ───────────────────────────────────────────────────
    prediction_id: Optional[str] = None
    prediction_hash: Optional[str] = None
    committed_at: Optional[str] = None
    horizon_end: Optional[str] = None

    # ── EXECUTION / ABSTAIN ─────────────────────────────────────────────────
    executed: bool = False
    abstained: bool = False
    abstain_reason: Optional[str] = None

    # ── OUTCOME_TRACKING ────────────────────────────────────────────────────
    tracking_until: Optional[str] = None

    # ── bookkeeping ─────────────────────────────────────────────────────────
    node_latency_ms: Annotated[dict[str, int], _merge] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
