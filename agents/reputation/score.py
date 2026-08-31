"""
The IRIS Score — IRIS_BUILD_PROMPT v2.0 section 12.

The weighted quality of an agent's record, discounted by how much of that
record has actually been tested:

    IRIS Score = 100 x (weighted quality) x (evidence)

The multiplication is the part worth arguing for, and the Phase 6 gate is what
forced it. With `evidence` as a seventh weighted dimension at 0.10, one perfect
prediction scored **79.2** — every other dimension maxes out on a sample of
one, and a 10% weight cannot pull that down. Since Phase 7 allocates capital by
this ranking, that agent would have been handed the vault on the strength of a
single lucky call. A weight small enough to be fair to a long record is far too
small to discount a short one; a multiplier is fair to both.

The weights are configurable and are **stored with every score**, because
`reputation_scores` keeps `dimensions` and `weights` side by side for exactly
one reason: a score computed under last month's weighting has to remain
re-derivable after the weighting changes. A reputation number you cannot
reproduce is a reputation number nobody can dispute.

Three rules here are about honesty rather than arithmetic, and each one is a
way the score could otherwise lie:

**An agent with no settled predictions has no score.** Not 0, not 50 — none.
A default would let an agent that has never been tested outrank one with a
proven bad record, and in Phase 7 that ranking allocates capital. `score_agent`
returns None, and the caller has to decide what to do about an untested agent
rather than being handed a number that looks like evidence.

**Scores never mix provenance.** An agent with forty SIMULATION outcomes and
two LIVE ones does not have a reputation; it has two different records. Scoring
is per `data_source`, so a simulated track record can never be aggregated into
something presented as live performance (section 0c).

**Only settled predictions count.** `WAITING_FOR_OUTCOME` exists precisely so
that predictions with no evidence stay out of every reputation number. Counting
them as neutral would let an agent dilute a bad record by predicting on assets
that have no price feed.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Optional, Sequence

import psycopg
from psycopg.types.json import Json

from agents.reputation.dimensions import (
    DIMENSIONS,
    Outcome,
    compute_dimensions,
    evidence,
)

# The default weighting. Accuracy and calibration lead, because being right and
# knowing how right you are is what the protocol pays for. `conviction` is the
# smallest: it is the one dimension an agent can max out by being reckless, so
# it earns a little credit for showing up and no more than that.
DEFAULT_WEIGHTS: dict[str, float] = {
    "accuracy": 0.28,
    "calibration": 0.22,
    "magnitude": 0.15,
    "consistency": 0.10,
    "risk_adjusted": 0.18,
    "conviction": 0.07,
}

# How the sweep labels a record it will not aggregate across.
PROVENANCE = ("SIMULATION", "TESTNET", "LIVE")


@dataclass(frozen=True)
class IrisScore:
    """A score, and everything needed to recompute it."""

    agent_id: str
    value: float                     # 0-100, after the evidence discount
    quality: float                   # 0-100, before it
    evidence: float                  # 0-1, how much of the record is tested
    dimensions: dict[str, float]
    weights: dict[str, float]
    sample_size: int
    data_source: str

    def explain(self) -> str:
        parts = ", ".join(
            f"{name} {self.dimensions[name]:.2f}x{self.weights[name]:.2f}"
            for name in self.weights
        )
        return (
            f"{self.agent_id} {self.value:.1f}/100 "
            f"(quality {self.quality:.1f} x evidence {self.evidence:.2f}) "
            f"[{self.data_source}, n={self.sample_size}] — {parts}"
        )


def validate_weights(weights: dict[str, float]) -> dict[str, float]:
    """
    Reject a weighting that would silently change what the score means.

    Three failures are all easy to introduce by editing a config and all
    invisible afterwards: a missing dimension (silently weighted 0), an unknown
    one (silently ignored), and weights that do not sum to 1 (every score
    shifted by a constant factor, so the leaderboard still looks plausible).
    """
    missing = set(DIMENSIONS) - set(weights)
    if missing:
        raise ValueError(f"weights are missing dimension(s): {sorted(missing)}")

    unknown = set(weights) - set(DIMENSIONS)
    if unknown:
        raise ValueError(f"weights name unknown dimension(s): {sorted(unknown)}")

    if any(w < 0 for w in weights.values()):
        raise ValueError("weights must be non-negative")

    total = math.fsum(weights.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"weights must sum to 1.0, got {total}")

    return dict(weights)


def compute_score(
    agent_id: str,
    outcomes: Sequence[Outcome],
    *,
    weights: Optional[dict[str, float]] = None,
    data_source: str = "SIMULATION",
) -> Optional[IrisScore]:
    """
    The IRIS Score for one agent, over one provenance.

    Returns None for an empty record. That is the whole point: see the module
    docstring.
    """
    if not outcomes:
        return None

    resolved = validate_weights(weights or DEFAULT_WEIGHTS)
    dimensions = compute_dimensions(outcomes)

    quality = 100.0 * math.fsum(dimensions[name] * w for name, w in resolved.items())
    tested = evidence(outcomes)

    return IrisScore(
        agent_id=agent_id,
        # Clamped against float drift only — the dimensions are already
        # validated onto [0, 1] and the weights onto a unit sum, so anything
        # outside this range would be a bug, not a large input.
        value=round(max(0.0, min(100.0, quality * tested)), 3),
        quality=round(max(0.0, min(100.0, quality)), 3),
        evidence=round(tested, 6),
        dimensions=dimensions,
        weights=resolved,
        sample_size=len(outcomes),
        data_source=data_source,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reading the record
# ─────────────────────────────────────────────────────────────────────────────

def load_outcomes(
    conn: psycopg.Connection, agent_id: str, *, data_source: str
) -> list[Outcome]:
    """
    Every scored outcome for one agent, at one provenance.

    `evaluation_score is not null` is the filter that keeps unsettled and
    measured-but-unscored predictions out of the record. A prediction sitting
    in WAITING_FOR_OUTCOME has produced no evidence, and evidence is the only
    thing reputation is allowed to be made of.
    """
    rows = conn.execute(
        """
        select p.direction, p.expected_return, p.confidence,
               o.actual_return, o.error, o.direction_correct,
               o.evaluation_score, o.data_source
          from prediction_outcomes o
          join predictions p on p.id = o.prediction_id
         where p.agent_id = %s
           and o.data_source = %s
           and o.evaluation_score is not null
      order by o.settled_at
        """,
        (agent_id, data_source),
    ).fetchall()

    return [
        Outcome(
            direction=r[0],
            expected_return=float(r[1]),
            confidence=float(r[2]),
            actual_return=float(r[3]),
            error=float(r[4]),
            direction_correct=bool(r[5]),
            evaluation_score=float(r[6]),
            data_source=r[7],
        )
        for r in rows
    ]


def score_agent(
    conn: psycopg.Connection,
    agent_id: str,
    *,
    weights: Optional[dict[str, float]] = None,
    data_source: str = "SIMULATION",
) -> Optional[IrisScore]:
    """Score one agent from the database. None if it has no settled record."""
    return compute_score(
        agent_id,
        load_outcomes(conn, agent_id, data_source=data_source),
        weights=weights,
        data_source=data_source,
    )


def persist_score(conn: psycopg.Connection, score: IrisScore) -> str:
    """
    Append a score. Never an UPDATE.

    `reputation_scores` is a history, not a current value: the Observatory
    plots how an agent's standing moved, and Phase 7's allocator needs to be
    auditable against the score it actually saw. Overwriting would make both
    impossible.
    """
    row_id = str(uuid.uuid4())
    conn.execute(
        """
        insert into reputation_scores (id, agent_id, iris_score, dimensions, weights)
        values (%s, %s, %s, %s, %s)
        """,
        (
            row_id,
            score.agent_id,
            score.value,
            # `data_source` and `sample_size` ride inside `dimensions` rather
            # than in new columns: a score whose provenance and sample size are
            # not recorded alongside it cannot be interpreted later, and the
            # JSONB is already the re-derivation record.
            # `_evidence` rides with the dimensions because without it the
            # stored score cannot be re-derived: it is a factor in the value,
            # not one of the weighted terms.
            Json({**score.dimensions,
                  "_data_source": score.data_source,
                  "_sample_size": score.sample_size,
                  "_evidence": score.evidence}),
            Json(score.weights),
        ),
    )
    return row_id


def score_all(
    conn: psycopg.Connection,
    *,
    weights: Optional[dict[str, float]] = None,
    data_source: str = "SIMULATION",
    persist: bool = True,
) -> dict[str, Optional[IrisScore]]:
    """
    Score every agent. Agents with no settled record map to None.

    They are returned rather than dropped so a caller can tell "untested" apart
    from "not an agent" — the Arena has to render an agent that has not been
    scored yet as exactly that, not as a zero.
    """
    agent_ids = [
        r[0] for r in conn.execute("select id from agents order by id").fetchall()
    ]

    scores: dict[str, Optional[IrisScore]] = {}
    for agent_id in agent_ids:
        score = score_agent(
            conn, agent_id, weights=weights, data_source=data_source
        )
        scores[agent_id] = score
        if score is not None and persist:
            persist_score(conn, score)
    return scores


def leaderboard(scores: dict[str, Optional[IrisScore]]) -> list[IrisScore]:
    """Scored agents, best first. Unscored agents are absent, not last."""
    return sorted(
        (s for s in scores.values() if s is not None),
        key=lambda s: s.value,
        reverse=True,
    )


def format_leaderboard(scores: dict[str, Optional[IrisScore]]) -> str:
    ranked = leaderboard(scores)
    unscored = [a for a, s in scores.items() if s is None]

    lines = [
        "",
        "IRIS Score — six weighted dimensions, discounted by evidence (section 12).",
        "  score = quality x evidence.  A short record cannot rank highly however",
        "  good it looks; that is the discount, not a bug.",
        "Simulated and live records are scored separately and never combined.",
        "",
        f"{'agent':<16}{'score':>8}{'quality':>9}{'evid':>7}{'n':>6}  "
        + "".join(f"{d[:7]:>9}" for d in DEFAULT_WEIGHTS)
        + "   source",
        "-" * 118,
    ]
    for s in ranked:
        lines.append(
            f"{s.agent_id:<16}{s.value:>8.1f}{s.quality:>9.1f}"
            f"{s.evidence:>7.2f}{s.sample_size:>6}  "
            + "".join(f"{s.dimensions[d]:>9.3f}" for d in DEFAULT_WEIGHTS)
            + f"   {s.data_source}"
        )

    if unscored:
        lines += [
            "",
            f"No settled predictions, so no score: {', '.join(sorted(unscored))}",
            "These are NOT ranked last — they are unranked. An untested agent "
            "must not outrank a proven bad one, and must not be presented as "
            "one either.",
        ]
    return "\n".join(lines) + "\n"


def _resolved_source(conn, requested):
    """
    Which provenance bucket to work in.

    `None` means "whichever the protocol actually has evidence in, strongest
    first". Pinning the default to SIMULATION was right while that was the only
    bucket and became wrong the moment predictions started settling against a
    real market — the scorers kept reading an empty bucket and reported every
    agent with a live record as untested.
    """
    from agents.evaluation.prices import strongest_outcome_source

    return requested or strongest_outcome_source(conn)


def main(argv: list[str] | None = None) -> int:
    """
        python -m agents.reputation.score
    """
    import argparse

    from agents.runtime.persistence import connection

    parser = argparse.ArgumentParser(description="Compute the IRIS Score for every agent.")
    parser.add_argument("--source", default=None, choices=PROVENANCE,
                        help="default: the strongest provenance with settled outcomes")
    parser.add_argument("--dry-run", action="store_true",
                        help="compute and print without writing reputation_scores")
    args = parser.parse_args(argv)

    with connection() as conn:
        source = _resolved_source(conn, args.source)
        scores = score_all(conn, data_source=source, persist=not args.dry_run)
        if args.dry_run:
            conn.rollback()

    print(format_leaderboard(scores))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
