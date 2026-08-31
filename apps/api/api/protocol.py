"""
The three v2 screens — IRIS_BUILD_PROMPT v2.0 section 15, Phases 10-12.

    /api/protocol/arena        Agent Arena       — who is winning, and what they hold
    /api/protocol/observatory  AI Observatory    — how a decision was actually made
    /api/protocol/ledger       Prediction Ledger — what was claimed, and what happened

Every endpoint reads the tables phases 5-8 write. Nothing here has a fixture
fallback, and that is deliberate: the older `/api/agents` route falls back to a
hardcoded list of nine invented agents when its query fails, which means a
database outage renders as a working dashboard full of numbers nobody produced.
These routes return an empty result and say so instead.

**Every response carries a `provenance` block.** Section 0c requires simulated
data to be labelled wherever it surfaces, and the label has to survive the
whole way to the screen — it is not enough for `prediction_outcomes.data_source`
to be right in the database if the JSON drops it. `provenance.sources` lists
what the rows behind this response actually rest on, so a UI cannot render a
number without being told what kind of number it is.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from db.connection import fetch_all_dicts, fetch_one_dict

logger = logging.getLogger(__name__)
router = APIRouter()


def provenance(sources: list[str], *, note: str = "") -> dict[str, Any]:
    """
    What the numbers in this response rest on.

    `live` is false unless every contributing row is LIVE. Deliberately
    pessimistic: a mixed response is not live, and defaulting the other way
    would let one live row launder a screen full of simulated ones.
    """
    clean = sorted({s for s in sources if s})
    live = bool(clean) and clean == ["LIVE"]

    if note:
        message = note
    elif live:
        # True only once every contributing row came from a real venue. The
        # claim is deliberately narrow: real prices, measured honestly. It says
        # nothing about capital, because none is deployed — Phase 2's custody
        # gate keeps allocation authority and wallet control apart, and the
        # allocator moves weights, not funds.
        message = (
            "Real market data. Prices come from a public exchange and every "
            "outcome below was measured against it. No live capital is "
            "deployed; allocations are weights, not transfers."
        )
    elif clean == ["SIMULATION"] or not clean:
        message = (
            "Simulated market data and synthetically trained models. "
            "Not evidence of live performance."
        )
    else:
        # The mixed case is the one worth naming out loud. It happens when the
        # feed was down for part of a settlement window, and it means some
        # rows here rest on a synthetic tape.
        message = (
            f"Mixed provenance ({', '.join(clean)}). Treated as the weakest: "
            f"some rows below were measured against simulated prices."
        )

    return {"sources": clean or ["SIMULATION"], "live": live, "note": message}


def _sources(rows: list[dict], key: str = "data_source") -> list[str]:
    return [r.get(key) for r in rows if r.get(key)]


# ─────────────────────────────────────────────────────────────────────────────
# Phase 10 — Agent Arena
# ─────────────────────────────────────────────────────────────────────────────

ARENA_SQL = """
    with latest_score as (
        select distinct on (agent_id)
               agent_id, iris_score, dimensions, weights, computed_at
          from reputation_scores
      order by agent_id, computed_at desc
    ),
    latest_alloc as (
        select distinct on (agent_id)
               agent_id, weight, step, eta, created_at
          from allocation_history
      order by agent_id, step desc
    ),
    settled as (
        select p.agent_id,
               count(*)                                          as settled_count,
               avg(case when o.direction_correct then 1.0 else 0.0 end) as accuracy,
               avg(o.evaluation_score)                           as mean_score,
               max(o.settled_at)                                 as last_settled
          from prediction_outcomes o
          join predictions p on p.id = o.prediction_id
         where o.evaluation_score is not null
      group by p.agent_id
    ),
    staked as (
        select agent_id,
               sum(case when is_unstake then -amount else amount end) as stake
          from agent_stakes group by agent_id
    )
    select a.id, a.name, a.strategy, a.status, a.vault_id,
           s.iris_score, s.dimensions, s.weights, s.computed_at,
           al.weight as allocation_weight, al.step as allocation_step,
           t.settled_count, t.accuracy, t.mean_score, t.last_settled,
           coalesce(st.stake, 0) as stake,
           mv.model_family, mv.version as model_version, mv.model_hash
      from agents a
 left join latest_score s  on s.agent_id  = a.id
 left join latest_alloc al on al.agent_id = a.id
 left join settled t       on t.agent_id  = a.id
 left join staked st       on st.agent_id = a.id
 left join model_versions mv on mv.agent_id = a.id and mv.is_active
  order by coalesce(s.iris_score, -1) desc, a.id
"""


@router.get("/arena")
def arena() -> dict[str, Any]:
    """
    The leaderboard — Phase 10.

    An agent with no settled record has `iris_score: null`, not 0. Phase 6
    returns None for exactly this reason: a default would let an agent that has
    never been tested outrank one with a proven bad record, and the Arena is
    where a reader would draw that conclusion. They are returned in a separate
    `unranked` list rather than sorted to the bottom, because "not yet
    measured" and "measured and bad" are different claims.
    """
    rows = fetch_all_dicts(ARENA_SQL, {})

    ranked, unranked = [], []
    for row in rows:
        entry = {
            "agent_id": row["id"],
            "name": row["name"],
            "strategy": row["strategy"],
            "status": row["status"],
            "vault_id": row["vault_id"],
            "iris_score": float(row["iris_score"]) if row["iris_score"] is not None else None,
            "dimensions": row["dimensions"],
            "weights": row["weights"],
            "allocation_weight": (
                float(row["allocation_weight"])
                if row["allocation_weight"] is not None else 0.0
            ),
            "allocation_step": row["allocation_step"],
            "settled_count": int(row["settled_count"] or 0),
            "accuracy": float(row["accuracy"]) if row["accuracy"] is not None else None,
            "mean_score": float(row["mean_score"]) if row["mean_score"] is not None else None,
            "stake": float(row["stake"] or 0),
            "model": {
                "family": row["model_family"],
                "version": row["model_version"],
                "hash": row["model_hash"],
            },
            "last_settled": row["last_settled"],
        }
        (ranked if entry["iris_score"] is not None else unranked).append(entry)

    dimension_sources = [
        (r["dimensions"] or {}).get("_data_source")
        for r in rows if r["dimensions"]
    ]

    return {
        "ranked": ranked,
        # Not "last place". An untested agent must not be presented as a bad one.
        "unranked": unranked,
        "totals": {
            "agents": len(rows),
            "scored": len(ranked),
            "allocated": sum(1 for e in ranked + unranked if e["allocation_weight"] > 0),
        },
        "provenance": provenance(dimension_sources),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase 11 — AI Observatory
# ─────────────────────────────────────────────────────────────────────────────

RUNS_SQL = """
    select r.id, r.agent_id, a.name as agent_name, a.strategy,
           r.status, r.started_at, r.finished_at, r.latency_ms, r.error,
           r.prediction_id,
           (select count(*) from graph_checkpoints c where c.agent_run_id = r.id) as nodes
      from agent_runs r
      left join agents a on a.id = r.agent_id
     where (cast(:agent as text) is null or r.agent_id = cast(:agent as text))
  order by r.started_at desc
     limit :limit
"""


@router.get("/observatory/runs")
def observatory_runs(
    agent: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=200),
) -> dict[str, Any]:
    """Recent agent runs — Phase 11."""
    rows = fetch_all_dicts(RUNS_SQL, {"agent": agent, "limit": limit})
    return {
        "runs": rows,
        "count": len(rows),
        "provenance": provenance(["SIMULATION"]),
    }


@router.get("/observatory/runs/{run_id}")
def observatory_run(run_id: str) -> dict[str, Any]:
    """
    One run, node by node — Phase 11.

    The checkpoints are a *chain*: each node's `input_hash` equals the previous
    node's `output_hash`, so the trail can be verified rather than believed.
    `chain_intact` is computed here rather than assumed, because a broken chain
    is the one thing that would make this screen a reconstruction instead of a
    recording.
    """
    run = fetch_one_dict(
        """select r.id, r.agent_id, a.name as agent_name, a.strategy, r.status,
                  r.started_at, r.finished_at, r.latency_ms, r.error, r.prediction_id
             from agent_runs r left join agents a on a.id = r.agent_id
            where r.id = :run_id""",
        {"run_id": run_id},
    )
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    checkpoints = fetch_all_dicts(
        """select seq, node, latency_ms, input_hash, output_hash, state, created_at
             from graph_checkpoints where agent_run_id = :run_id order by seq""",
        {"run_id": run_id},
    )

    intact = all(
        checkpoints[i]["input_hash"] == checkpoints[i - 1]["output_hash"]
        for i in range(1, len(checkpoints))
    )

    prediction = None
    if run.get("prediction_id"):
        prediction = fetch_one_dict(
            """select p.id, p.asset, p.direction, p.expected_return, p.confidence,
                      p.prediction_hash, p.status, p.committed_at, p.horizon_end,
                      o.actual_return, o.error, o.direction_correct,
                      o.evaluation_score, o.data_source
                 from predictions p
            left join prediction_outcomes o on o.prediction_id = p.id
                where p.id = :pid""",
            {"pid": str(run["prediction_id"])},
        )

    return {
        "run": run,
        "checkpoints": checkpoints,
        "chain_intact": intact,
        "prediction": prediction,
        "provenance": provenance(
            [(prediction or {}).get("data_source") or "SIMULATION"]
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase 12 — Prediction Ledger
# ─────────────────────────────────────────────────────────────────────────────

LEDGER_SQL = """
    select p.id, p.agent_id, a.name as agent_name, p.asset, p.direction,
           p.expected_return, p.confidence, p.horizon_seconds,
           p.prediction_hash, p.status, p.predicted_at, p.committed_at,
           p.horizon_end, p.solana_sig,
           o.actual_return, o.error, o.direction_correct, o.evaluation_score,
           o.settled_at, o.data_source
      from predictions p
      left join agents a on a.id = p.agent_id
      left join prediction_outcomes o on o.prediction_id = p.id
     where (cast(:agent as text) is null or p.agent_id = cast(:agent as text))
       and (cast(:status as text) is null or p.status = cast(:status as text))
  order by p.committed_at desc nulls last, p.predicted_at desc
     limit :limit
"""


@router.get("/ledger")
def ledger(
    agent: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    """
    Committed predictions and their outcomes — Phase 12.

    `waiting` is broken out as its own count on purpose. A prediction in
    WAITING_FOR_OUTCOME is not "pending" — it is the protocol *declining to
    score something it has no evidence for*, which is the most honest thing the
    system does. Flattening it into a spinner alongside "not due yet" would
    hide exactly that.
    """
    rows = fetch_all_dicts(
        LEDGER_SQL, {"agent": agent, "status": status, "limit": limit}
    )

    for row in rows:
        # The claim was hashed before its horizon closed. Surfaced as a boolean
        # so the UI can show the primitive rather than leaving the reader to
        # compare two timestamps.
        committed, horizon = row.get("committed_at"), row.get("horizon_end")
        row["committed_before_horizon"] = bool(
            committed and horizon and committed <= horizon
        )

    counts = fetch_one_dict(
        """
        select count(*) filter (where status = 'COMMITTED')            as committed,
               count(*) filter (where status = 'WAITING_FOR_OUTCOME')  as waiting,
               count(*) filter (where status = 'SETTLED')              as settled,
               count(*) filter (where status = 'EVALUATED')            as evaluated,
               count(*)                                               as total
          from predictions
         where (cast(:agent as text) is null or agent_id = :agent)
        """,
        {"agent": agent},
    ) or {}

    scored = [r for r in rows if r.get("evaluation_score") is not None]
    return {
        "predictions": rows,
        "counts": counts,
        "summary": {
            "scored": len(scored),
            "correct": sum(1 for r in scored if r["direction_correct"]),
            "accuracy": (
                sum(1 for r in scored if r["direction_correct"]) / len(scored)
                if scored else None
            ),
            "mean_score": (
                sum(float(r["evaluation_score"]) for r in scored) / len(scored)
                if scored else None
            ),
        },
        "provenance": provenance(
            _sources(rows),
            note=(
                "Outcomes are measured against a simulated price tape. "
                "A prediction in WAITING_FOR_OUTCOME has no price evidence and "
                "is deliberately unscored — it counts toward nothing."
            ),
        ),
    }


@router.get("/ledger/{prediction_id}")
def ledger_entry(prediction_id: str) -> dict[str, Any]:
    """One prediction, with the commitment and its settlement side by side."""
    row = fetch_one_dict(
        """select p.*, o.actual_return, o.error, o.direction_correct,
                  o.evaluation_score, o.settled_at, o.data_source
             from predictions p
        left join prediction_outcomes o on o.prediction_id = p.id
            where p.id = :pid""",
        {"pid": prediction_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail="prediction not found")

    return {
        "prediction": row,
        "committed_before_horizon": bool(
            row.get("committed_at") and row.get("horizon_end")
            and row["committed_at"] <= row["horizon_end"]
        ),
        "provenance": provenance([row.get("data_source") or "SIMULATION"]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Shared
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/risk")
def risk_feed(limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    """Breaches, freezes and slashes — the Phase 8 chain, for the Arena."""
    events = fetch_all_dicts(
        """select id, agent_id, kind, severity, measured_bps, limit_bps,
                  detail, data_source, created_at
             from risk_events order by created_at desc limit :limit""",
        {"limit": limit},
    )
    slashes = fetch_all_dicts(
        """select id, agent_id, risk_event_id, drawdown_bps, slash_bps,
                  amount_slashed, data_source, created_at
             from slash_events order by created_at desc limit :limit""",
        {"limit": limit},
    )
    return {
        "risk_events": events,
        "slash_events": slashes,
        "provenance": provenance(_sources(events) + _sources(slashes)),
    }


@router.get("/summary")
def summary() -> dict[str, Any]:
    """
    One call for the landing page.

    Counts read straight off the tables, so a zero here means the protocol has
    genuinely not done that thing yet rather than that a widget failed to load.
    """
    row = fetch_one_dict(
        """
        select (select count(*) from agents where status in ('ACTIVE','PROBATION')) as active_agents,
               (select count(*) from agents where status = 'FROZEN')                as frozen_agents,
               (select count(*) from agents where status = 'SLASHED')               as slashed_agents,
               (select count(*) from predictions)                                   as predictions,
               (select count(*) from prediction_outcomes)                           as settled,
               (select count(*) from predictions where status = 'WAITING_FOR_OUTCOME') as waiting,
               (select count(*) from agent_runs)                                    as runs,
               (select coalesce(max(step), -1) from allocation_history)             as allocation_step,
               (select count(*) from protocol_events)                               as events
        """,
        {},
    ) or {}
    return {"totals": row, "provenance": provenance(["SIMULATION"])}
