#!/usr/bin/env python3
"""
Phase 1 gate check — IRIS_BUILD_PROMPT v2.0 section 27.

Definition of Done:
    `docker compose up` boots web+api+db with a health-check route returning
    200 on all three.

This is the SELF-TEST step of the section 0 loop, so it asserts rather than
eyeballs. Run it against a stack that is already up:

    docker compose up -d --build
    python scripts/verify_phase1.py

Exit code 0 means the phase may checkpoint; anything else means it may not.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

WEB_HEALTH = "http://localhost:3000/health"
API_HEALTH = "http://localhost:8000/health"
API_DB_HEALTH = "http://localhost:8000/health/db"

# Web is slowest: the Next dev server compiles the route on first request.
DEADLINE_SECONDS = 240
POLL_SECONDS = 3

# Every table required by v2 section 13.
REQUIRED_TABLES = [
    "users", "agents", "model_versions", "agent_stakes", "vaults", "deposits",
    "predictions", "prediction_outcomes", "agent_performance",
    "reputation_scores", "allocation_history", "trades", "positions",
    "risk_events", "slash_events", "agent_runs", "graph_checkpoints",
    "market_events", "news_events", "governance_proposals", "governance_votes",
]

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def probe(url: str) -> tuple[int, str]:
    """Return (status, body). Status 0 means the connection itself failed."""
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")[:300]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:300]
    except Exception as exc:
        return 0, str(exc)


def wait_for(name: str, url: str, deadline: float) -> bool:
    while time.time() < deadline:
        status, body = probe(url)
        if status == 200:
            print(f"  {GREEN}PASS{RESET}  {name:<12} 200  {DIM}{body.strip()}{RESET}")
            return True
        time.sleep(POLL_SECONDS)

    status, body = probe(url)
    shown = f"{status}" if status else "unreachable"
    print(f"  {RED}FAIL{RESET}  {name:<12} {shown}  {DIM}{body.strip()}{RESET}")
    return False


def check_tables() -> bool:
    """Confirm the 21 tables from v2 section 13 exist in the running database."""
    query = (
        "select table_name from information_schema.tables "
        "where table_schema = 'public'"
    )
    try:
        out = subprocess.run(
            ["docker", "compose", "exec", "-T", "db",
             "psql", "-U", "iris", "-d", "iris", "-tAc", query],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:
        print(f"  {RED}FAIL{RESET}  schema       could not query database: {exc}")
        return False

    if out.returncode != 0:
        print(f"  {RED}FAIL{RESET}  schema       psql exited {out.returncode}: "
              f"{out.stderr.strip()[:200]}")
        return False

    present = {line.strip() for line in out.stdout.splitlines() if line.strip()}
    missing = [t for t in REQUIRED_TABLES if t not in present]

    if missing:
        print(f"  {RED}FAIL{RESET}  schema       {len(missing)} of "
              f"{len(REQUIRED_TABLES)} tables missing: {', '.join(missing)}")
        return False

    print(f"  {GREEN}PASS{RESET}  schema       all {len(REQUIRED_TABLES)} tables present")
    return True


def main() -> int:
    print("\nPhase 1 gate — docker compose up boots web+api+db\n")
    deadline = time.time() + DEADLINE_SECONDS

    results = [
        ("api  /health",    wait_for("api", API_HEALTH, deadline)),
        ("api  /health/db", wait_for("api-db", API_DB_HEALTH, deadline)),
        ("web  /health",    wait_for("web", WEB_HEALTH, deadline)),
        ("db   schema",     check_tables()),
    ]

    print()
    if all(ok for _, ok in results):
        print(f"{GREEN}Phase 1 gate PASSED{RESET} — may checkpoint.\n")
        return 0

    failed = [name for name, ok in results if not ok]
    print(f"{RED}Phase 1 gate FAILED{RESET} — {', '.join(failed)}. "
          f"Do not checkpoint; see `docker compose logs`.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
