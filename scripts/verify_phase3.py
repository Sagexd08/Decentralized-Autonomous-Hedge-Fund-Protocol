#!/usr/bin/env python3
"""
Phase 3 gate check — IRIS_BUILD_PROMPT v2.0 section 27.

Definition of Done:
    One agent completes the full graph end-to-end on synthetic data,
    checkpointed in Neon.

Both halves are checked against the running stack, not against a mock: the
graph is executed for real and the resulting rows are read back out of
Postgres. A run that "completed" without leaving a trace fails this gate.

    docker compose up -d
    python scripts/verify_phase3.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"

SEED_COMMITS = 7    # exercises PREDICTION_COMMIT -> EXECUTION -> OUTCOME_TRACKING
SEED_ABSTAINS = 0   # exercises the ABSTAIN branch

SPEC_NODES = [
    "MARKET_OBSERVATION", "FEATURE_EXTRACTION", "REGIME_ANALYSIS",
    "HISTORICAL_RETRIEVAL", "MODEL_INFERENCE", "RISK_ANALYSIS",
    "DECISION", "VALIDATION", "PREDICTION_COMMIT", "EXECUTION",
    "OUTCOME_TRACKING",
]


def compose(*args: str, service: str = "api") -> str:
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", service, *args],
        capture_output=True, text=True,
    )
    return proc.stdout + proc.stderr


def sql(query: str) -> str:
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "psql", "-U", "iris", "-d", "iris",
         "-tAc", query],
        capture_output=True, text=True,
    )
    return proc.stdout.strip()


def ok(label: str, detail: str = "") -> bool:
    print(f"  {GREEN}PASS{RESET}  {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))
    return True


def bad(label: str, detail: str = "") -> bool:
    print(f"  {RED}FAIL{RESET}  {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))
    return False


def run_agent(seed: int) -> dict:
    out = compose(
        "python", "-m", "agents.runtime.runner",
        "--agent", "AGT-AXIOM", "--asset", "BTC", "--seed", str(seed), "--json",
    )
    match = re.search(r"\{.*\}", out, re.S)
    if not match:
        print(f"{RED}runner produced no JSON:{RESET}\n{out[-1500:]}")
        sys.exit(2)
    return json.loads(match.group(0))


def main() -> int:
    print("\nPhase 3 gate — one agent completes the graph, checkpointed in Neon\n")
    results: list[bool] = []

    # ── the full path ───────────────────────────────────────────────────────
    print("Full graph traversal")
    committed = run_agent(SEED_COMMITS)
    run_id = committed["agent_run_id"]

    results.append(
        ok("run completed", run_id)
        if committed["outcome"] == "COMPLETED"
        else bad("run completed", f"outcome was {committed['outcome']}")
    )
    results.append(
        ok("11 nodes executed")
        if committed["checkpoints"] == 11
        else bad("11 nodes executed", f"got {committed['checkpoints']}")
    )

    nodes = sql(
        f"select string_agg(node, ',' order by seq) from graph_checkpoints "
        f"where agent_run_id = '{run_id}'"
    ).split(",")
    results.append(
        ok("nodes ran in the section 10 order")
        if nodes == SPEC_NODES
        else bad("nodes ran in the section 10 order", " -> ".join(nodes))
    )

    # ── checkpointed in Neon ────────────────────────────────────────────────
    print("\nCheckpointed in Neon")
    count = sql(f"select count(*) from graph_checkpoints where agent_run_id = '{run_id}'")
    results.append(
        ok("graph_checkpoints rows written", f"{count} rows")
        if count == "11"
        else bad("graph_checkpoints rows written", f"{count} rows")
    )

    chained = sql(
        f"select bool_and(c.input_hash = p.output_hash) from graph_checkpoints c "
        f"join graph_checkpoints p on p.agent_run_id = c.agent_run_id "
        f"and p.seq = c.seq - 1 where c.agent_run_id = '{run_id}'"
    )
    results.append(
        ok("checkpoint hashes form an unbroken chain")
        if chained == "t"
        else bad("checkpoint hashes form an unbroken chain", chained)
    )

    lat = sql(
        f"select count(*) from graph_checkpoints "
        f"where agent_run_id = '{run_id}' and latency_ms is null"
    )
    results.append(
        ok("every checkpoint carries a latency")
        if lat == "0"
        else bad("every checkpoint carries a latency", f"{lat} rows missing it")
    )

    lg = sql("select count(*) from checkpoints")
    results.append(
        ok("LangGraph PostgresSaver is checkpointing too", f"{lg} rows")
        if lg.isdigit() and int(lg) > 0
        else bad("LangGraph PostgresSaver is checkpointing too", lg or "no table")
    )

    # ── the commitment ──────────────────────────────────────────────────────
    print("\nPrediction commitment")
    pred = sql(
        f"select status || '|' || length(prediction_hash) || '|' "
        f"|| (committed_at < horizon_end)::text from predictions "
        f"where id = (select prediction_id from agent_runs where id = '{run_id}')"
    )
    status, hashlen, ordered = (pred.split("|") + ["", "", ""])[:3]
    results.append(
        ok("prediction written as COMMITTED")
        if status == "COMMITTED" else bad("prediction written as COMMITTED", status)
    )
    results.append(
        ok("commitment is a sha256 digest", f"{hashlen} chars")
        if hashlen == "64" else bad("commitment is a sha256 digest", hashlen)
    )
    results.append(
        ok("committed strictly before its horizon")
        if ordered == "true" else bad("committed strictly before its horizon", ordered)
    )

    # ── the other branch ────────────────────────────────────────────────────
    print("\nAbstain branch")
    abstained = run_agent(SEED_ABSTAINS)
    results.append(
        ok("a rejected run abstains instead of committing")
        if abstained["outcome"] == "ABSTAINED" and not abstained["prediction_id"]
        else bad("a rejected run abstains instead of committing", str(abstained))
    )
    results.append(
        ok("abstention is not recorded as a failure")
        if sql(
            f"select status from agent_runs where id = '{abstained['agent_run_id']}'"
        ) == "ABSTAINED"
        else bad("abstention is not recorded as a failure")
    )

    print()
    if all(results):
        print(f"{GREEN}Phase 3 gate PASSED{RESET} — {len(results)}/{len(results)} checks.\n")
        return 0
    print(f"{RED}Phase 3 gate FAILED{RESET} — "
          f"{sum(results)}/{len(results)} checks. Do not checkpoint.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
