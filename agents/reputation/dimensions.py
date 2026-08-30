"""
The dimensions an IRIS Score is built from — IRIS_BUILD_PROMPT v2.0 section 12.

Section 12 asks for at least six dimensions with configurable weights. Six
numbers averaged together is easy; six numbers that each say something the
others do not is the actual work. Each dimension here answers a question the
rest cannot:

    accuracy       was it right?
    calibration    did it know how sure it should have been?
    magnitude      was it right about *how much*?
    consistency    is it reliably that good, or averaging two extremes?
    risk_adjusted  did it earn that return, or just take more risk?
    conviction     did it take a position, or hedge into HOLD?

Every one is a pure function of a list of settled outcomes, on 0-1, and total:
no input produces NaN, and none can be improved by predicting nothing.

`evidence` is deliberately **not** in that list. It measures how much of a
record has been tested, which is not a quality — and the Phase 6 gate proved
why that distinction matters. When it was a seventh weighted dimension at 0.10,
a single perfect prediction scored **79.2**: the other six dimensions were all
maxed on a sample of one, and a 10% weight could not pull that down. An agent
like that would have been handed the vault by the Phase 7 allocator.

So evidence multiplies rather than adds. The score is *quality x how much that
quality has been demonstrated*, which is also the form that makes it directly
usable for allocation: an agent that has proven nothing carries almost no
weight, however good its handful of calls looked.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence

# The half-life of doubt: at this many settled predictions, a record carries
# half its face value. Not a cliff — the curve saturates, so there is no count
# an agent can sit just above to unlock full credit, and each early prediction
# is worth far more than each later one.
EVIDENCE_SATURATION = 20

# The volatility floor in the risk-adjusted ratio. Without it, an agent whose
# returns happen to be near-identical divides by ~0 and posts an unbounded
# score — the classic way a Sharpe ratio lies about a small sample.
MIN_VOLATILITY = 0.002

# Section 7's risk-adjusted score weights drawdown alongside volatility:
#   R_i = Return / (Vol + lambda * |Drawdown|)
DRAWDOWN_LAMBDA = 0.5


@dataclass(frozen=True)
class Outcome:
    """
    One settled prediction, as reputation sees it.

    Deliberately narrow. Reputation reads what the agent claimed and what
    happened — not the model, the strategy, or the run. Anything else here
    would be a lever for scoring an agent on something other than its record.
    """

    direction: str
    expected_return: float
    confidence: float
    actual_return: float
    error: float
    direction_correct: bool
    evaluation_score: float      # 0-100, from agents.evaluation.scoring
    data_source: str


def accuracy(outcomes: Sequence[Outcome]) -> float:
    """Share of calls that got the direction right."""
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if o.direction_correct) / len(outcomes)


def calibration(outcomes: Sequence[Outcome], bins: int = 5) -> float:
    """
    Does stated confidence match the realised hit rate?

    Reliability, not accuracy. An agent that says 60% and is right 60% of the
    time is perfectly calibrated even though it is wrong 40% of the time. An
    agent that says 95% and is right 60% of the time is not.

    Measured as 1 minus the sample-weighted mean gap between stated confidence
    and realised accuracy *within each confidence bin*. Binning is load-bearing:
    on a single average, systematic overconfidence on strong calls would cancel
    against underconfidence on weak ones, and an agent wrong in both directions
    would look perfectly calibrated.

    This dimension only became measurable once `confidence` was fixed to be the
    probability of the direction actually predicted. Before that it was the
    probability of whichever class happened to be likeliest, so comparing it to
    the hit rate compared two different quantities.
    """
    if not outcomes:
        return 0.0

    buckets: list[list[Outcome]] = [[] for _ in range(bins)]
    for o in outcomes:
        index = min(int(o.confidence * bins), bins - 1)
        buckets[index].append(o)

    total_gap = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        stated = statistics.fmean(o.confidence for o in bucket)
        realised = sum(1 for o in bucket if o.direction_correct) / len(bucket)
        total_gap += abs(stated - realised) * len(bucket)

    return max(0.0, 1.0 - total_gap / len(outcomes))


def magnitude(outcomes: Sequence[Outcome]) -> float:
    """
    Was it right about *how much*, not just which way?

    Separate from accuracy because magnitude is what sizes a position. An agent
    that calls every direction correctly and every size ten times too large
    loses money while scoring perfectly on accuracy.
    """
    if not outcomes:
        return 0.0
    # Mirrors agents.evaluation.scoring: smooth decay, so a wildly wrong size
    # stays distinguishable from a merely imprecise one.
    return statistics.fmean(1.0 / (1.0 + o.error / 0.01) for o in outcomes)


def consistency(outcomes: Sequence[Outcome]) -> float:
    """
    Is the record steady, or two extremes averaged into a mediocre mean?

    An agent scoring 100 and 0 alternately has the same mean as one scoring 50
    every time, and they are not the same agent — the first is untrustworthy
    with capital even though its average says otherwise.
    """
    if len(outcomes) < 2:
        # One prediction has no spread to measure. Returning 1.0 would hand a
        # brand-new agent a perfect score on this dimension; 0.0 would punish it
        # for something it has not had the chance to demonstrate. Neutral is the
        # honest answer, and `evidence` is what discounts the record as a whole.
        return 0.5
    scores = [o.evaluation_score / 100.0 for o in outcomes]
    spread = statistics.pstdev(scores)
    # A stdev of 0.5 on a 0-1 scale is about as inconsistent as a record gets.
    return max(0.0, 1.0 - spread / 0.5)


def risk_adjusted(outcomes: Sequence[Outcome]) -> float:
    """
    Return per unit of risk taken — section 7's R_i, squashed onto 0-1.

    An agent that doubled its return by doubling its position size has not
    improved. Dividing by the agent's own volatility plus a drawdown penalty
    means leverage cannot buy a better score.
    """
    if not outcomes:
        return 0.0

    # What taking each position as called actually earned: a correct SELL earns
    # the fall, so a short flips the sign of the realised return.
    returns = [
        -o.actual_return if o.direction == "SELL"
        else o.actual_return if o.direction == "BUY"
        else 0.0
        for o in outcomes
    ]
    mean_return = statistics.fmean(returns)
    volatility = statistics.pstdev(returns) if len(returns) > 1 else MIN_VOLATILITY

    equity, peak, drawdown = 0.0, 0.0, 0.0
    for r in returns:
        equity += r
        peak = max(peak, equity)
        drawdown = min(drawdown, equity - peak)

    denominator = max(volatility, MIN_VOLATILITY) + DRAWDOWN_LAMBDA * abs(drawdown)
    ratio = mean_return / denominator

    # A logistic squash rather than a clamp, so a very good agent and an
    # extraordinary one stay distinguishable instead of both pinning at 1.0.
    return 1.0 / (1.0 + math.exp(-4.0 * max(-50.0, min(50.0, ratio))))


def conviction(outcomes: Sequence[Outcome]) -> float:
    """
    Did it take a position, or hedge into HOLD?

    An agent that predicts HOLD every time is never badly wrong and never worth
    anything: it consumes an allocation slot and returns nothing. Distinct from
    accuracy, because HOLD can be the correct call — this measures willingness
    to commit, not whether committing worked.

    Deliberately naive on its own: an agent that takes a side every time and is
    wrong every time scores 1.0 here. It is only meaningful in combination,
    where `accuracy` and `risk_adjusted` are simultaneously near zero.
    """
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if o.direction != "HOLD") / len(outcomes)


def evidence(outcomes: Sequence[Outcome]) -> float:
    """
    How much of this record has actually been tested. **Not a dimension.**

    Kept out of `DIMENSIONS` on purpose — see the module docstring. It is a
    multiplier on the weighted quality score, not something averaged in beside
    it, because a weight small enough to be fair to a long record is far too
    small to discount a sample of one.

    Saturating rather than linear or stepped: each early prediction moves the
    number a lot, each later one moves it less, and it never quite reaches 1.
    A short record is cheap to improve, a long one is impossible to fake, and
    there is no threshold to sit just above.
    """
    n = len(outcomes)
    if n == 0:
        return 0.0
    return n / (n + EVIDENCE_SATURATION)


# The registry. Ordered, because the JSONB written to `reputation_scores` is
# read back by the UI and a stable key order keeps diffs legible.
DIMENSIONS = {
    "accuracy": accuracy,
    "calibration": calibration,
    "magnitude": magnitude,
    "consistency": consistency,
    "risk_adjusted": risk_adjusted,
    "conviction": conviction,
}


def compute_dimensions(outcomes: Sequence[Outcome]) -> dict[str, float]:
    """
    Every dimension, on 0-1.

    Checked rather than trusted: a NaN escaping here would reach
    `reputation_scores.iris_score`, pass the CHECK constraint (NaN comparisons
    are never true, so `BETWEEN 0 AND 100` does not reject it), and poison an
    agent's reputation silently.
    """
    values = {name: fn(outcomes) for name, fn in DIMENSIONS.items()}
    for name, value in values.items():
        if not math.isfinite(value):
            raise ValueError(f"dimension {name} produced {value}")
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"dimension {name} produced {value}, outside [0, 1]")
    return {name: round(value, 6) for name, value in values.items()}
