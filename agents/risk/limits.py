"""
Risk limits and breach detection — IRIS_BUILD_PROMPT v2.0 section 8.

The limits are named constants rather than numbers inline, because each one is
a policy decision about when the protocol stops trusting an agent, and a policy
buried in an expression is a policy nobody can review.

Two kinds of breach exist and they are not interchangeable:

  * **Per-run** breaches come from `RISK_ANALYSIS` inside the graph. They stop
    *this* trade. Until Phase 8 they stopped nothing else, because nothing
    recorded them — the agent abstained and the observation evaporated.
  * **Per-record** breaches come from an agent's settled outcomes. They are the
    ones that can freeze or slash, because they are the only ones that describe
    a pattern rather than a moment.

A single bad prediction is not misconduct. The protocol has to be able to tell
"this trade looks dangerous" from "this agent is dangerous", and conflating the
two produces a system that either freezes constantly or never.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence

from agents.reputation.dimensions import Outcome

# ── limits ──────────────────────────────────────────────────────────────────

# Peak-to-trough on the agent's own cumulative realised return. The single most
# important number here: it is what a depositor actually experiences.
MAX_DRAWDOWN_BPS = 2000          # 20%

# Realised volatility of the agent's per-prediction returns.
MAX_VOLATILITY_BPS = 3500        # 35%

# 95% conditional value-at-risk — the mean of the worst 5% of outcomes. A
# separate limit from volatility because an agent can look calm on average and
# still have a tail that empties the vault.
MAX_CVAR_BPS = 1200              # 12%

# Directional accuracy below which an agent is not predicting. Sits above the
# 1/3 a coin-flip over three classes would give, so noise alone does not breach.
MIN_ACCURACY = 0.25

# How many settled predictions before a record can breach at all. Below this,
# a drawdown is a small sample, not a pattern — and freezing on it would punish
# an agent for the variance every new agent has.
MIN_SAMPLE_FOR_BREACH = 10

# ── escalation ──────────────────────────────────────────────────────────────

# A CRITICAL breach freezes immediately. A WARN has to repeat: one bad window
# is noise, three is a trend.
WARN_BREACHES_BEFORE_FREEZE = 3

# How far past its limit a drawdown has to go before the breach is CRITICAL
# rather than WARN.
CRITICAL_MULTIPLE = 1.5

# Slash size, in basis points of stake, scaled by how far past the limit the
# drawdown went. Bounded at both ends: below the floor a slash is not worth
# recording, and the ceiling exists because a slash that takes everything
# removes any reason for the agent to keep operating honestly afterwards.
MIN_SLASH_BPS = 100              # 1%
MAX_SLASH_BPS = 5000             # 50%

# How much of the excess drawdown converts to slash. At 1.0, an agent 10 points
# past its limit loses 10% of stake.
SLASH_PER_EXCESS_BPS = 1.0


@dataclass(frozen=True)
class Breach:
    """One limit exceeded, with the evidence that says so."""

    kind: str                    # matches risk_events.kind
    severity: str                # INFO | WARN | CRITICAL
    measured_bps: int
    limit_bps: int
    detail: str

    @property
    def is_critical(self) -> bool:
        return self.severity == "CRITICAL"

    def __str__(self) -> str:
        return f"{self.kind} {self.measured_bps}bps > {self.limit_bps}bps ({self.severity})"


@dataclass(frozen=True)
class RiskProfile:
    """What an agent's settled record says about how it is behaving."""

    sample_size: int
    drawdown_bps: int
    volatility_bps: int
    cvar_bps: int
    accuracy: float
    cumulative_return: float
    breaches: list[Breach]

    @property
    def is_clear(self) -> bool:
        return not self.breaches

    @property
    def worst(self) -> str:
        if not self.breaches:
            return "INFO"
        for level in ("CRITICAL", "WARN", "INFO"):
            if any(b.severity == level for b in self.breaches):
                return level
        return "INFO"


def position_returns(outcomes: Sequence[Outcome]) -> list[float]:
    """
    What taking each position as called actually earned.

    A correct SELL earns the fall, so a short flips the sign. A HOLD earns
    nothing — which is the honest treatment: declining to trade is neither a
    gain nor a loss, and counting it as either would let an agent manage its
    drawdown by abstaining.
    """
    return [
        -o.actual_return if o.direction == "SELL"
        else o.actual_return if o.direction == "BUY"
        else 0.0
        for o in outcomes
    ]


def max_drawdown(returns: Sequence[float]) -> float:
    """
    Worst peak-to-trough on the cumulative return. Non-negative.

    Additive rather than compounded, matching how the returns are measured
    per-prediction. The distinction matters at these magnitudes less than the
    consistency does: the number here has to mean the same thing as the one the
    limit was set against.
    """
    equity = peak = worst = 0.0
    for r in returns:
        equity += r
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return abs(worst)


def cvar(returns: Sequence[float], quantile: float = 0.05) -> float:
    """
    Mean of the worst `quantile` of outcomes. Non-negative, as a loss.

    Historical rather than parametric: a normal-distribution CVaR on financial
    returns understates exactly the tail this limit exists to catch.
    """
    if not returns:
        return 0.0
    ordered = sorted(returns)
    cut = max(1, int(math.floor(quantile * len(ordered))))
    tail = ordered[:cut]
    return abs(min(0.0, statistics.fmean(tail)))


def evaluate(outcomes: Sequence[Outcome]) -> RiskProfile:
    """
    Measure an agent's settled record against the limits.

    Reports; decides nothing. `agents.risk.engine` acts on what this finds, the
    same split the graph draws between RISK_ANALYSIS and VALIDATION.
    """
    returns = position_returns(outcomes)
    n = len(outcomes)

    drawdown_bps = int(round(max_drawdown(returns) * 10_000))
    volatility_bps = int(round(
        (statistics.pstdev(returns) if len(returns) > 1 else 0.0) * 10_000
    ))
    cvar_bps = int(round(cvar(returns) * 10_000))
    accuracy = (
        sum(1 for o in outcomes if o.direction_correct) / n if n else 0.0
    )
    cumulative = math.fsum(returns)

    breaches: list[Breach] = []

    # Below the sample floor nothing breaches. A three-prediction drawdown is
    # variance, and freezing on it would punish every agent for being new —
    # which is the same mistake `evidence` corrects in the IRIS Score.
    if n >= MIN_SAMPLE_FOR_BREACH:
        if drawdown_bps > MAX_DRAWDOWN_BPS:
            severity = (
                "CRITICAL"
                if drawdown_bps > MAX_DRAWDOWN_BPS * CRITICAL_MULTIPLE
                else "WARN"
            )
            breaches.append(Breach(
                kind="DRAWDOWN_BREACH", severity=severity,
                measured_bps=drawdown_bps, limit_bps=MAX_DRAWDOWN_BPS,
                detail=f"peak-to-trough {drawdown_bps / 100:.2f}% over {n} settled predictions",
            ))

        if volatility_bps > MAX_VOLATILITY_BPS:
            breaches.append(Breach(
                kind="VOLATILITY_BREACH", severity="WARN",
                measured_bps=volatility_bps, limit_bps=MAX_VOLATILITY_BPS,
                detail=f"realised volatility {volatility_bps / 100:.2f}%",
            ))

        if cvar_bps > MAX_CVAR_BPS:
            breaches.append(Breach(
                kind="CVAR_BREACH", severity="WARN",
                measured_bps=cvar_bps, limit_bps=MAX_CVAR_BPS,
                detail=f"mean of the worst 5% of outcomes: -{cvar_bps / 100:.2f}%",
            ))

        if accuracy < MIN_ACCURACY:
            breaches.append(Breach(
                kind="CONFIDENCE_FLOOR", severity="WARN",
                measured_bps=int(round(accuracy * 10_000)),
                limit_bps=int(round(MIN_ACCURACY * 10_000)),
                detail=f"directional accuracy {accuracy:.1%} over {n} predictions",
            ))

    return RiskProfile(
        sample_size=n,
        drawdown_bps=drawdown_bps,
        volatility_bps=volatility_bps,
        cvar_bps=cvar_bps,
        accuracy=accuracy,
        cumulative_return=cumulative,
        breaches=breaches,
    )


def slash_bps_for(drawdown_bps: int) -> int:
    """
    How much stake a drawdown costs, in basis points.

    Proportional to the *excess* over the limit, not to the drawdown itself: an
    agent exactly at its limit has not misbehaved, and a penalty that starts at
    the limit rather than beyond it makes the limit a cliff.
    """
    excess = max(0, drawdown_bps - MAX_DRAWDOWN_BPS)
    scaled = int(round(excess * SLASH_PER_EXCESS_BPS))
    return max(MIN_SLASH_BPS, min(MAX_SLASH_BPS, scaled))
