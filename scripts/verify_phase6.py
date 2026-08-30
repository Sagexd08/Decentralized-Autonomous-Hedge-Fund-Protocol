#!/usr/bin/env python
"""
Phase 6 gate — IRIS_BUILD_PROMPT v2.0 section 27.

DoD: "IRIS Score computed from at least six dimensions with configurable
weights, unit-tested."

Counting six dimensions is trivial and proves almost nothing, so the gate
checks the properties that make a reputation number worth anything:

  * every dimension is load-bearing — zeroing its weight moves the score, so
    none of the six is decorative padding to reach the count;
  * every dimension is *independent* — no two move together on every record,
    which would mean the same signal counted twice;
  * a stored score is re-derivable from its stored dimensions and weights;
  * an untested agent has no score, not a default one;
  * unsettled predictions never enter a reputation number;
  * simulated and live records are never aggregated together.

The last three are the ones that would let the score lie. A default score for
an untested agent is the worst of them, because Phase 7 allocates capital by
this ranking.

    python scripts/verify_phase6.py
"""

from __future__ import annotations

import math
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import psycopg
except ModuleNotFoundError:  # pragma: no cover - host path
    import subprocess

    print("psycopg not available here; running the gate inside the api container.",
          flush=True)
    raise SystemExit(
        subprocess.run(
            ["docker", "compose", "exec", "-T", "api",
             "python", "/repo/scripts/verify_phase6.py"],
        ).returncode
    )

from agents.reputation.dimensions import DIMENSIONS, Outcome  # noqa: E402
from agents.reputation.score import (  # noqa: E402
    DEFAULT_WEIGHTS,
    compute_score,
    format_leaderboard,
    load_outcomes,
    persist_score,
    score_agent,
    validate_weights,
)

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
results: list[tuple[bool, str, str]] = []

AGENT = "AGT-AXIOM"


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label, detail))
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  {mark}  {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))


def outcome(
    *, correct: bool = True, confidence: float = 0.7, error: float = 0.002,
    score: float = 80.0, actual: float = 0.02, direction: str = "BUY",
    source: str = "SIMULATION",
) -> Outcome:
    return Outcome(
        direction=direction, expected_return=actual, confidence=confidence,
        actual_return=actual, error=error, direction_correct=correct,
        evaluation_score=score, data_source=source,
    )


def good_record(n: int = 60) -> list[Outcome]:
    return [
        outcome(correct=i % 5 != 0, score=85.0 - (i % 3) * 2,
                actual=0.02 + (i % 4) * 0.001, error=0.001 + (i % 3) * 0.0004,
                confidence=0.78)
        for i in range(n)
    ]


def poor_record(n: int = 60) -> list[Outcome]:
    return [
        outcome(correct=i % 5 == 0, score=25.0 + (i % 7) * 8,
                actual=-0.03 + (i % 5) * 0.004, error=0.03 + (i % 4) * 0.01,
                confidence=0.93)
        for i in range(n)
    ]


# ── the dimensions ──────────────────────────────────────────────────────────

def dimensions_section() -> None:
    check(len(DIMENSIONS) >= 6,
          "at least six dimensions", f"{len(DIMENSIONS)}: {', '.join(DIMENSIONS)}")

    good = compute_score(AGENT, good_record())
    poor = compute_score(AGENT, poor_record())

    check(all(0.0 <= v <= 1.0 and math.isfinite(v) for v in good.dimensions.values()),
          "every dimension is finite and on [0, 1]")

    check(good.value > poor.value,
          "a better record scores higher", f"{good.value:.1f} vs {poor.value:.1f}")

    check(0.0 <= good.value <= 100.0 and 0.0 <= poor.value <= 100.0,
          "the score is on [0, 100]", f"{good.value:.1f} / {poor.value:.1f}")

    # Every dimension must be load-bearing. A dimension whose weight can be
    # zeroed without moving the score is padding to reach a count of six.
    dead = []
    for name in DIMENSIONS:
        weights = {k: (0.0 if k == name else v) for k, v in DEFAULT_WEIGHTS.items()}
        total = math.fsum(weights.values())
        weights = {k: v / total for k, v in weights.items()}
        without = compute_score(AGENT, good_record(), weights=weights)
        if abs(without.value - good.value) < 1e-6:
            dead.append(name)
    check(not dead,
          "every dimension changes the score",
          "none is decorative" if not dead else f"inert: {dead}")

    # And they must measure different things. Two dimensions that agree on
    # every record are one dimension counted twice.
    identical = []
    names = list(DIMENSIONS)
    records = [good_record(), poor_record(), good_record(7), poor_record(3)]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if all(
                abs(compute_score(AGENT, r).dimensions[a]
                    - compute_score(AGENT, r).dimensions[b]) < 1e-9
                for r in records
            ):
                identical.append((a, b))
    check(not identical,
          "no two dimensions are the same measurement",
          "all six are distinct" if not identical else f"duplicated: {identical}")


# ── configurable weights ────────────────────────────────────────────────────

def weights_section() -> None:
    record = good_record()
    base = compute_score(AGENT, record)

    accuracy_heavy = {k: 0.0 for k in DEFAULT_WEIGHTS}
    accuracy_heavy["accuracy"] = 1.0
    tilted = compute_score(AGENT, record, weights=accuracy_heavy)
    check(abs(tilted.value - base.value) > 1e-6,
          "changing the weights changes the score",
          f"{base.value:.1f} → {tilted.value:.1f}")

    rejected = []
    for label, weights in [
        ("missing a dimension", {k: v for k, v in DEFAULT_WEIGHTS.items()
                                 if k != "calibration"}),
        ("an unknown dimension", {**DEFAULT_WEIGHTS, "vibes": 0.0}),
        ("weights that do not sum to 1", {k: v * 2 for k, v in DEFAULT_WEIGHTS.items()}),
        ("a negative weight", {**DEFAULT_WEIGHTS, "accuracy": -0.30}),
    ]:
        try:
            validate_weights(weights)
        except ValueError:
            rejected.append(label)
    check(len(rejected) == 4,
          "an invalid weighting is rejected, not silently applied",
          f"{len(rejected)}/4 rejected")

    check(base.weights == DEFAULT_WEIGHTS,
          "the weighting used is returned with the score")

    # Re-derivability is the reason `reputation_scores` stores both. The
    # tolerance is 1e-3 because the stored value is rounded to three decimals.
    recomputed = 100.0 * math.fsum(
        base.dimensions[name] * w for name, w in base.weights.items()
    )
    check(abs(recomputed - base.quality) < 1e-3,
          "quality is re-derivable from its dimensions and weights",
          f"{recomputed:.3f} == {base.quality:.3f}")
    check(abs(base.quality * base.evidence - base.value) < 1e-3,
          "the score is quality discounted by evidence",
          f"{base.quality:.1f} x {base.evidence:.3f} = {base.value:.1f}")


# ── honesty ─────────────────────────────────────────────────────────────────

def honesty_section(conn) -> None:
    check(compute_score(AGENT, []) is None,
          "an agent with no settled predictions has NO score",
          "not 0, not 50 — None")

    # The check that forced evidence out of DIMENSIONS and into a multiplier.
    one = compute_score(AGENT, [outcome(correct=True, score=100.0, error=0.0)])
    many = compute_score(AGENT, [outcome(correct=True, score=100.0, error=0.0)] * 200)
    check(one.value < 20.0,
          "one lucky prediction does not produce a high score",
          f"flawless on 1 call: quality {one.quality:.1f}, scored {one.value:.1f}")
    check(many.value > 4 * one.value and many.quality >= one.quality - 5,
          "the same quality over a long record scores far higher",
          f"n=1 {one.value:.1f} vs n=200 {many.value:.1f}, quality "
          f"{one.quality:.1f} vs {many.quality:.1f}")

    # Unsettled predictions must not enter the record.
    asset = f"P6-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    model_version_id = conn.execute(
        "select id from model_versions where agent_id = %s limit 1", (AGENT,)
    ).fetchone()[0]

    before = len(load_outcomes(conn, AGENT, data_source="SIMULATION"))
    conn.execute(
        """
        insert into predictions
            (agent_id, model_version_id, asset, direction, expected_return,
             confidence, horizon_seconds, prediction_hash, status,
             predicted_at, committed_at, horizon_end)
        values (%s, %s, %s, 'BUY', 0.01, 0.9, 600, %s, 'WAITING_FOR_OUTCOME',
                %s, %s, %s)
        """,
        (AGENT, model_version_id, asset,
         uuid.uuid4().hex + uuid.uuid4().hex[:32],
         now - timedelta(hours=2), now - timedelta(hours=2),
         now - timedelta(hours=1)),
    )
    after = len(load_outcomes(conn, AGENT, data_source="SIMULATION"))
    check(after == before,
          "a WAITING_FOR_OUTCOME prediction never enters the record",
          f"{before} outcomes before and after")

    # Provenance is never mixed.
    live_only = load_outcomes(conn, "AGT-QUANTA", data_source="LIVE")
    sim_only = load_outcomes(conn, "AGT-QUANTA", data_source="SIMULATION")
    check(all(o.data_source == "LIVE" for o in live_only)
          and all(o.data_source == "SIMULATION" for o in sim_only),
          "a record is loaded per provenance, never merged",
          f"{len(sim_only)} SIMULATION, {len(live_only)} LIVE")

    mixed = compute_score("AGT-MIXED", [
        outcome(source="SIMULATION"), outcome(source="LIVE")
    ], data_source="SIMULATION")
    check(mixed.data_source == "SIMULATION",
          "a score always names the provenance it was computed over",
          mixed.data_source)


# ── persistence ─────────────────────────────────────────────────────────────

def persistence_section(conn) -> None:
    score = compute_score(AGENT, good_record())
    persist_score(conn, score)

    stored_value, dimensions, weights = conn.execute(
        """select iris_score, dimensions, weights from reputation_scores
            where agent_id = %s order by computed_at desc limit 1""",
        (AGENT,),
    ).fetchone()

    check(abs(float(stored_value) - score.value) < 1e-3,
          "the score is persisted", f"{float(stored_value):.3f}")

    recomputed = float(dimensions["_evidence"]) * 100.0 * math.fsum(
        float(dimensions[name]) * float(w) for name, w in weights.items()
    )
    check(abs(recomputed - float(stored_value)) < 1e-2,
          "a stored score is re-derivable from the stored row alone",
          f"{recomputed:.3f} == {float(stored_value):.3f}")

    check(dimensions.get("_data_source") == score.data_source
          and dimensions.get("_sample_size") == score.sample_size,
          "provenance and sample size are stored with the score",
          f"{dimensions.get('_data_source')}, n={dimensions.get('_sample_size')}")

    # A score is a history, never overwritten.
    persist_score(conn, compute_score(AGENT, poor_record()))
    rows = conn.execute(
        "select count(*) from reputation_scores where agent_id = %s", (AGENT,)
    ).fetchone()[0]
    check(rows >= 2, "scoring appends rather than overwriting", f"{rows} rows")

    live = score_agent(conn, AGENT, data_source="LIVE")
    check(live is None,
          "an agent with no LIVE record has no LIVE score",
          "None, not a simulated score relabelled")


def main() -> int:
    print("\nIRIS Phase 6 gate — the IRIS Score\n")

    dimensions_section()
    weights_section()

    conn = psycopg.connect(DSN)
    try:
        honesty_section(conn)
        persistence_section(conn)
        print(format_leaderboard({
            "AGT-QUANTA": score_agent(conn, "AGT-QUANTA"),
            "AGT-AXIOM": score_agent(conn, "AGT-AXIOM"),
        }))
    finally:
        conn.rollback()   # the gate leaves nothing behind
        conn.close()

    passed = sum(1 for ok, _, _ in results if ok)
    total = len(results)
    if passed == total:
        print(f"{GREEN}Phase 6 gate PASSED{RESET} — {passed}/{total} checks.\n")
        return 0
    print(f"{RED}Phase 6 gate FAILED{RESET} — {passed}/{total}.")
    for ok, label, _ in results:
        if not ok:
            print(f"  - {label}")
    print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
