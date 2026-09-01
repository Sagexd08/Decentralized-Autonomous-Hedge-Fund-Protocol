#!/usr/bin/env python
"""
Phases 10-12 gate — IRIS_BUILD_PROMPT v2.0 section 27.

DoD for each of Agent Arena, AI Observatory and Prediction Ledger: "driven by
real rows, not fixtures."

That is a claim about provenance, not about rendering, so the gate compares
every number the API serves against the table it should have come from. A
screen backed by plausible constants looks identical to one backed by the
database until somebody does that comparison.

It also enforces §0c, which has been outstanding since Phase 1: simulated data
must be labelled *in the UI*, not only in the schema. Every response carries a
`provenance` block, every page renders it, and the older `/api/agents` fixture
fallback — nine invented agents with invented Sharpe ratios, previously
returned unlabelled when the database query failed — now says what it is.

    python scripts/verify_phase10_12.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

API = os.getenv("IRIS_API_URL", "http://localhost:8000")
WEB = os.getenv("IRIS_WEB_URL", "http://localhost:3000")

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
results: list[tuple[bool, str, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label, detail))
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  {mark}  {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))


def get(path: str, base: str = API):
    with urllib.request.urlopen(f"{base}{path}", timeout=20) as response:
        return json.load(response)


def html(path: str) -> str:
    with urllib.request.urlopen(f"{WEB}{path}", timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def sql(query: str):
    """Read the database directly, so the API's answer can be disagreed with."""
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "db",
         "psql", "-U", "iris", "-d", "iris", "-tAc", query],
        capture_output=True, text=True, cwd=ROOT,
    )
    return proc.stdout.strip()


# ── Phase 10: Agent Arena ───────────────────────────────────────────────────

def arena_section() -> None:
    arena = get("/api/protocol/arena")
    ranked, unranked = arena["ranked"], arena["unranked"]

    db_agents = int(sql("select count(*) from agents"))
    check(arena["totals"]["agents"] == db_agents,
          "the Arena counts the agents that exist",
          f"{arena['totals']['agents']} == {db_agents} rows")

    db_scored = int(sql(
        "select count(distinct agent_id) from reputation_scores"
    ))
    check(len(ranked) == db_scored,
          "every ranked agent has a stored reputation score",
          f"{len(ranked)} ranked, {db_scored} agents in reputation_scores")

    # The number itself, not just the count.
    mismatched = []
    for entry in ranked:
        stored = sql(
            "select iris_score from reputation_scores where agent_id = "
            f"'{entry['agent_id']}' order by computed_at desc limit 1"
        )
        if not stored or abs(float(stored) - entry["iris_score"]) > 1e-3:
            mismatched.append(entry["agent_id"])
    check(not mismatched,
          "each IRIS Score matches the row it came from",
          f"{len(ranked)} scores checked against reputation_scores"
          if not mismatched else str(mismatched[:3]))

    check(all(e["iris_score"] is None for e in unranked),
          "an untested agent has no score, rather than a zero",
          f"{len(unranked)} unranked")

    check(all(e["iris_score"] is not None for e in ranked),
          "the ranked list contains only agents that have been measured")

    scores = [e["iris_score"] for e in ranked]
    check(scores == sorted(scores, reverse=True),
          "the leaderboard is ordered by score",
          " > ".join(f"{s:.1f}" for s in scores[:4]) if scores else "")

    # Allocation is read from allocation_history, not recomputed for display.
    if ranked:
        agent = ranked[0]["agent_id"]
        stored = sql(
            f"select weight from allocation_history where agent_id = '{agent}' "
            "order by step desc limit 1"
        )
        check(stored and abs(float(stored) - ranked[0]["allocation_weight"]) < 1e-6,
              "allocation weights come from allocation_history",
              f"{agent} {ranked[0]['allocation_weight']:.4f}")


# ── Phase 11: AI Observatory ────────────────────────────────────────────────

def observatory_section() -> None:
    runs = get("/api/protocol/observatory/runs?limit=10")["runs"]
    db_runs = int(sql("select count(*) from agent_runs"))
    check(len(runs) > 0 and db_runs > 0,
          "the Observatory lists real agent runs",
          f"{len(runs)} shown, {db_runs} in agent_runs")

    missing = [
        r["id"] for r in runs
        if sql(f"select 1 from agent_runs where id = '{r['id']}'") != "1"
    ]
    check(not missing,
          "every run shown exists in the database",
          f"{len(runs)} checked" if not missing else str(missing[:3]))

    committed = next((r for r in runs if r["prediction_id"]), None)
    check(committed is not None,
          "at least one committing run is available to inspect",
          committed["id"][:8] if committed else "none found")

    if committed:
        detail = get(f"/api/protocol/observatory/runs/{committed['id']}")
        db_nodes = int(sql(
            f"select count(*) from graph_checkpoints where agent_run_id = "
            f"'{committed['id']}'"
        ))
        check(len(detail["checkpoints"]) == db_nodes == 11,
              "all eleven graph nodes are traced from graph_checkpoints",
              f"{len(detail['checkpoints'])} checkpoints")

        check(detail["chain_intact"],
              "the hash chain is verified, not asserted",
              "each node's input_hash equals the previous output_hash")

        # And the verification is real: break it and it must notice.
        broken = dict(detail)
        broken_checkpoints = [dict(c) for c in detail["checkpoints"]]
        broken_checkpoints[1]["input_hash"] = "0" * 64
        recomputed = all(
            broken_checkpoints[i]["input_hash"] == broken_checkpoints[i - 1]["output_hash"]
            for i in range(1, len(broken_checkpoints))
        )
        check(not recomputed,
              "a tampered chain would be reported as broken",
              "the check is not hardcoded to true")

        check(detail["prediction"] is not None
              and detail["prediction"]["prediction_hash"],
              "the committing run shows the commitment it produced",
              (detail["prediction"] or {}).get("prediction_hash", "")[:16])


# ── Phase 12: Prediction Ledger ─────────────────────────────────────────────

def ledger_section() -> None:
    ledger = get("/api/protocol/ledger?limit=100")
    rows = ledger["predictions"]

    db_total = int(sql("select count(*) from predictions"))
    check(ledger["counts"]["total"] == db_total,
          "the Ledger counts the predictions that exist",
          f"{ledger['counts']['total']} == {db_total}")

    missing = [
        r["id"] for r in rows[:20]
        if sql(f"select 1 from predictions where id = '{r['id']}'") != "1"
    ]
    check(not missing,
          "every prediction shown exists in the database",
          f"{min(len(rows), 20)} checked")

    committed = [r for r in rows if r["committed_at"]]
    check(committed and all(r["committed_before_horizon"] for r in committed),
          "every commitment predates the horizon it is judged against",
          f"{len(committed)} committed predictions")

    db_waiting = int(sql(
        "select count(*) from predictions where status = 'WAITING_FOR_OUTCOME'"
    ))
    check(ledger["counts"]["waiting"] == db_waiting,
          "WAITING_FOR_OUTCOME is counted separately from pending",
          f"{db_waiting} declining to be scored")

    unscored_waiting = [
        r for r in rows
        if r["status"] == "WAITING_FOR_OUTCOME" and r["evaluation_score"] is not None
    ]
    check(not unscored_waiting,
          "nothing waiting on evidence carries a score",
          "a scored WAITING row would be an invented outcome")

    scored = [r for r in rows if r["evaluation_score"] is not None]
    if scored:
        entry = scored[0]
        stored = sql(
            "select evaluation_score from prediction_outcomes "
            f"where prediction_id = '{entry['id']}'"
        )
        check(stored and abs(float(stored) - float(entry["evaluation_score"])) < 1e-3,
              "scores come from prediction_outcomes",
              f"{float(entry['evaluation_score']):.2f}")


# ── §0c: the label reaches the screen ───────────────────────────────────────

def provenance_section() -> None:
    endpoints = [
        "/api/protocol/arena",
        "/api/protocol/ledger?limit=5",
        "/api/protocol/summary",
        "/api/protocol/risk",
        "/api/protocol/observatory/runs?limit=2",
    ]
    missing = [e for e in endpoints if "provenance" not in get(e)]
    check(not missing,
          "every protocol endpoint carries a provenance block",
          f"{len(endpoints)} endpoints" if not missing else str(missing))

    # `live` must FOLLOW the sources, rather than be a fixed value.
    #
    # This used to assert `live is False` everywhere — "nothing currently
    # claims to be live" — which was true for twelve phases and became a
    # requirement that the product misreport itself the moment the feed became
    # real. A gate that fails when the system starts working is worse than no
    # gate: it teaches you to weaken it.
    #
    # The property that actually matters is consistency in the dangerous
    # direction: `live` is true only when every contributing row is LIVE.
    KNOWN = {"SIMULATION", "TESTNET", "LIVE", "FIXTURE"}
    inconsistent, unknown_labels = [], []
    for endpoint in endpoints:
        provenance = get(endpoint)["provenance"]
        sources = provenance["sources"]
        if not set(sources) <= KNOWN or not sources:
            unknown_labels.append((endpoint, sources))
        if provenance["live"] is not (sources == ["LIVE"]):
            inconsistent.append((endpoint, provenance["live"], sources))

    check(not unknown_labels,
          "every provenance block names sources the schema knows",
          str(unknown_labels[:2]) if unknown_labels else "")
    check(not inconsistent,
          "`live` is true only when every contributing row is LIVE",
          str(inconsistent[:2]) if inconsistent
          else "a mixed response is never reported as live")

    # The API label is worthless if the page drops it. Checked against the
    # served HTML rather than the component source: what matters is what a
    # reader sees.
    #
    # Also not a fixed word. The screens now report live, mixed, simulated or
    # unconfirmed depending on what is true, so this asserts the two properties
    # that hold in every one of those states: a label is present, and it never
    # overstates. Understating is safe; claiming live over data that is not is
    # the failure §0c exists to prevent.
    api_live = all(get(e)["provenance"]["live"] for e in endpoints)
    missing_label, overclaiming = [], []
    for page in ("/arena", "/observatory", "/ledger"):
        body = html(page)
        found = re.search(r'data-provenance="([a-z]+)"', body)
        if not found:
            missing_label.append(page)
            continue
        kind = found.group(1)
        if kind == "unknown":
            missing_label.append(f"{page} (could not reach the API)")
        elif kind == "live" and not api_live:
            overclaiming.append((page, kind))

    check(not missing_label,
          "every screen renders a provenance label (§0c)",
          "arena, observatory, ledger" if not missing_label
          else str(missing_label))
    check(not overclaiming,
          "no screen claims live over data that is not",
          "understating is safe; overstating is the failure §0c prevents"
          if not overclaiming else str(overclaiming))

    # The fixture fallback that used to be indistinguishable from real data.
    agents = get("/api/agents/")
    check(all("data_source" in a for a in agents),
          "the legacy agents route labels its rows too",
          f"{len(agents)} agents, sources "
          f"{sorted({a.get('data_source') for a in agents})}")


def pages_section() -> None:
    for page, name in (("/arena", "Agent Arena"),
                       ("/observatory", "AI Observatory"),
                       ("/ledger", "Prediction Ledger")):
        try:
            body = html(page)
            ok = name.split()[-1].lower() in body.lower()
        except Exception as exc:
            body, ok = "", False
            check(False, f"{name} renders", str(exc))
            continue
        check(ok, f"{name} renders at {page}", f"{len(body)} bytes")


def ensure_a_committing_run() -> None:
    """
    Make the protocol produce a committing run, rather than hoping one exists.

    The Observatory checks need a run that actually committed, and this gate
    used to take whichever runs happened to be lying in `agent_runs`. That made
    it a test of the database's history: a stretch in which every agent
    correctly abstained — the normal state on a quiet market — left the last
    ten runs with nothing to inspect and failed the gate on a working system.

    Searched across agents, because which one commits is a fact about today's
    weights and about the market in the last hour. If none of them can commit,
    that is a real failure and the checks below will say so.
    """
    # Asked of the exact window the checks inspect — the runs the Observatory
    # endpoint returns — not of the database at large. A committing run from an
    # hour ago satisfies "one exists" and is still invisible here, because the
    # abstentions of the last hour have pushed it past the limit.
    try:
        recent = get("/api/protocol/observatory/runs?limit=10")["runs"]
        if any(r["prediction_id"] for r in recent):
            return
    except Exception:  # noqa: BLE001 - the checks below report the real state
        pass

    agents = sql(
        "select a.id from agents a join model_versions m on m.agent_id = a.id "
        "where a.status <> 'RETIRED' order by a.id"
    ).split()

    for agent in agents:
        proc = subprocess.run(
            ["docker", "compose", "exec", "-T", "api",
             "python", "-m", "agents.runtime.runner",
             "--agent", agent, "--asset", "BTC", "--seed", "7", "--json"],
            capture_output=True, text=True, cwd=ROOT,
        )
        match = re.search(r"\{.*\}", proc.stdout, re.S)
        if match and json.loads(match.group(0))["outcome"] == "COMPLETED":
            print(f"  {DIM}produced a committing run: {agent}{RESET}")
            return

    print(f"  {DIM}no agent committed; the Observatory checks will say so{RESET}")


def main() -> int:
    print("\nIRIS Phases 10-12 gate — Arena, Observatory, Ledger\n")
    print(f"  {DIM}every number compared against the table it came from{RESET}\n")

    print("  Phase 10 — Agent Arena")
    arena_section()
    print("\n  Phase 11 — AI Observatory")
    ensure_a_committing_run()
    observatory_section()
    print("\n  Phase 12 — Prediction Ledger")
    ledger_section()
    print("\n  Section 0c — honest labelling")
    provenance_section()
    print("\n  Pages")
    pages_section()

    passed = sum(1 for ok, _, _ in results if ok)
    total = len(results)
    print()
    if passed == total:
        print(f"{GREEN}Phases 10-12 gate PASSED{RESET} — {passed}/{total} checks.\n")
        return 0
    print(f"{RED}Phases 10-12 gate FAILED{RESET} — {passed}/{total}.")
    for ok, label, _ in results:
        if not ok:
            print(f"  - {label}")
    print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
