#!/usr/bin/env python
"""
Phase 9 gate — IRIS_BUILD_PROMPT v2.0 section 27.

DoD: "WebSocket infrastructure — real events from phases 3-8 reach a connected
client."

The load-bearing word is *real*, and it is the reason this gate is not simply
"open a socket and see if anything arrives". A generator emitting plausible
traffic on a timer satisfies that, is indistinguishable from a working system
on the client side, and is exactly what the pre-v2 sockets in this repo do.

So the gate connects a real client, then makes the protocol *do* things — runs
an agent, settles predictions, scores, allocates, sweeps risk — and checks that
what arrived on the socket corresponds to rows that exist in the database. Every
frame names a `source_table` and a `source_id`; the gate reads those rows back
and fails if any of them is missing.

It also checks the two ways a stream lies quietly: dropping the provenance
label, and losing events across a reconnect.

    python scripts/verify_phase9.py
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import psycopg
    import websockets
except ModuleNotFoundError:  # pragma: no cover - host path
    print("dependencies unavailable here; running the gate inside the api container.",
          flush=True)
    raise SystemExit(
        subprocess.run(
            ["docker", "compose", "exec", "-T", "api",
             "python", "/repo/scripts/verify_phase9.py"],
        ).returncode
    )

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")
WS = os.getenv("IRIS_WS_URL", "ws://localhost:8000/ws/events")

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
results: list[tuple[bool, str, str]] = []

AGENT = "AGT-QUANTA"

# The eight tables phases 3-8 write. An event stream that cannot carry all of
# them is not carrying "phases 3-8".
PHASE_TABLES = {
    "agent_runs", "graph_checkpoints", "predictions", "prediction_outcomes",
    "reputation_scores", "allocation_history", "risk_events", "slash_events",
}

# The primary key column for each source, so a frame can be checked against the
# row it claims to describe.
PRIMARY_KEY = {
    "agent_runs": "id", "graph_checkpoints": "id", "predictions": "id",
    "prediction_outcomes": "prediction_id", "reputation_scores": "id",
    "allocation_history": "id", "risk_events": "id", "slash_events": "id",
    "agents": "id",
}


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label, detail))
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  {mark}  {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))


def exercise_the_protocol() -> None:
    """
    Make phases 3-8 actually happen, so there is something real to stream.

    Driven through the same entry points a person would use. A gate that
    inserted into `protocol_events` directly would be testing the socket
    against its own fixture.
    """
    from agents.allocation.allocator import allocate
    from agents.evaluation.prices import record_price
    from agents.evaluation.settlement import run_sweep as settle
    from agents.reputation.score import score_all
    from agents.risk.engine import run_sweep as risk_sweep
    from agents.runtime.runner import run_agent

    run_agent(agent_id=AGENT, asset="BTC", seed=3,
              use_langgraph_checkpointer=False)

    now = datetime.now(timezone.utc)
    with psycopg.connect(DSN) as conn:
        model_version_id = conn.execute(
            "select id from model_versions where agent_id = %s limit 1", (AGENT,)
        ).fetchone()[0]
        for i in range(3):
            asset = f"P9-{uuid.uuid4().hex[:8]}"
            at = now - timedelta(hours=2) + timedelta(minutes=i)
            conn.execute(
                """
                insert into predictions
                    (agent_id, model_version_id, asset, direction, expected_return,
                     confidence, horizon_seconds, prediction_hash, status,
                     predicted_at, committed_at, horizon_end)
                values (%s, %s, %s, 'BUY', 0.01, 0.8, 1800, %s, 'COMMITTED',
                        %s, %s, %s)
                """,
                (AGENT, model_version_id, asset,
                 uuid.uuid4().hex + uuid.uuid4().hex[:32],
                 at, at, at + timedelta(seconds=1800)),
            )
            record_price(conn, asset=asset, price=100.0, at=at)
            record_price(conn, asset=asset, price=101.5,
                         at=at + timedelta(seconds=1800))

        settle(conn, now=now)
        score_all(conn, persist=True)
        risk_sweep(conn)
        allocate(conn, persist=True)
        conn.commit()


async def collect(duration: float, since: int | None = None) -> list[dict]:
    """Everything the socket delivers within `duration` seconds."""
    url = WS + (f"?since={since}" if since is not None else "?replay=0")
    frames: list[dict] = []
    async with websockets.connect(url) as socket:
        deadline = asyncio.get_event_loop().time() + duration
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                raw = await asyncio.wait_for(socket.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            frames.append(json.loads(raw))
    return frames


async def run_client_while_protocol_runs(duration: float = 14.0) -> list[dict]:
    """
    Connect first, act second.

    The order matters: a client that connects *after* the work is done proves
    only that history can be replayed. Phase 9 is about events reaching a
    connected client while the protocol is running.
    """
    async with websockets.connect(WS + "?replay=0") as socket:
        opening = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))
        assert opening["kind"] == "STREAM_OPEN", opening

        await asyncio.to_thread(exercise_the_protocol)

        frames: list[dict] = []
        deadline = asyncio.get_event_loop().time() + duration
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                raw = await asyncio.wait_for(socket.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            frames.append(json.loads(raw))
    return frames


def main() -> int:
    print("\nIRIS Phase 9 gate — the protocol event stream\n")

    before = 0
    with psycopg.connect(DSN) as conn:
        before = conn.execute(
            "select coalesce(max(seq), 0) from protocol_events"
        ).fetchone()[0]

    frames = asyncio.run(run_client_while_protocol_runs())
    events = [f for f in frames if f.get("kind") not in ("KEEPALIVE", "STREAM_OPEN")]

    check(len(events) > 0,
          "a connected client receives events while the protocol runs",
          f"{len(events)} frames")

    # ── every event is a real row ───────────────────────────────────────────
    missing: list[str] = []
    with psycopg.connect(DSN) as conn:
        for event in events:
            table = event.get("source_table")
            key = PRIMARY_KEY.get(table)
            if not key:
                missing.append(f"{table}: unknown source table")
                continue
            found = conn.execute(
                f"select 1 from {table} where {key}::text = %s",
                (event["source_id"],),
            ).fetchone()
            if not found:
                missing.append(f"{table}/{event['source_id']}")

    check(not missing,
          "every event names a row that actually exists",
          f"{len(events)} frames checked against their source rows"
          if not missing else f"{len(missing)} phantom: {missing[:3]}")

    # ── phases 3-8 are all represented ──────────────────────────────────────
    tables = {e["source_table"] for e in events}
    covered = PHASE_TABLES & tables
    check(len(covered) >= 6,
          "events span the phases, not just one of them",
          f"{len(covered)}/8 tables: {', '.join(sorted(covered))}")

    kinds = {e["kind"] for e in events}
    expected_kinds = {
        "RUN_STARTED", "NODE_COMPLETED", "PREDICTION_COMMITTED",
        "PREDICTION_SETTLED", "REPUTATION_UPDATED", "ALLOCATION_UPDATED",
    }
    check(expected_kinds <= kinds,
          "the whole cycle is visible on the wire",
          f"{len(kinds)} kinds; missing {sorted(expected_kinds - kinds) or 'none'}")

    # ── provenance survives the wire ────────────────────────────────────────
    unlabelled = [e for e in events if not e.get("data_source")]
    check(not unlabelled,
          "every frame carries its provenance label",
          "a frame without data_source is a number the UI cannot qualify"
          if not unlabelled else f"{len(unlabelled)} unlabelled")

    check(all(e["data_source"] in ("SIMULATION", "TESTNET", "LIVE") for e in events),
          "provenance is one of the three the schema allows",
          ", ".join(sorted({e["data_source"] for e in events})))

    # ── ordering and resumability ───────────────────────────────────────────
    seqs = [e["seq"] for e in events]
    check(seqs == sorted(seqs),
          "events arrive in order",
          f"seq {seqs[0]} → {seqs[-1]}" if seqs else "")

    check(len(set(seqs)) == len(seqs),
          "no event is delivered twice in one connection")

    replayed = asyncio.run(collect(3.0, since=before))
    replayed_events = [
        f for f in replayed if f.get("kind") not in ("KEEPALIVE", "STREAM_OPEN")
    ]
    replayed_seqs = {e["seq"] for e in replayed_events}
    check(set(seqs) <= replayed_seqs,
          "a client reconnecting with a watermark loses nothing",
          f"{len(replayed_seqs)} replayed ⊇ {len(seqs)} live")

    # ── the stream is not inventing anything ────────────────────────────────
    with psycopg.connect(DSN) as conn:
        rows = conn.execute(
            "select count(*) from protocol_events where seq > %s", (before,)
        ).fetchone()[0]
    check(len(set(seqs)) <= rows,
          "the socket delivered no more events than the table contains",
          f"{len(set(seqs))} delivered, {rows} rows written")

    # ── the log cannot be rewritten ─────────────────────────────────────────
    with psycopg.connect(DSN) as conn:
        conn.execute("savepoint probe")
        try:
            conn.execute("update protocol_events set kind = 'FAKE' where seq = %s",
                         (seqs[0] if seqs else 1,))
            mutable = True
        except psycopg.errors.IntegrityConstraintViolation:
            mutable = False
        conn.rollback()
    check(not mutable,
          "the event log is append-only",
          "the record the Observatory renders cannot be edited")

    # ── health reports lag, not just liveness ───────────────────────────────
    import urllib.request

    with urllib.request.urlopen("http://localhost:8000/api/events/health", timeout=10) as r:
        health = json.load(r)
    check(health["running"] and health["lag"] < 50,
          "the stream reports its lag, not just that it is up",
          f"watermark {health['watermark']}, head {health['head']}, "
          f"lag {health['lag']}")

    print()
    passed = sum(1 for ok, _, _ in results if ok)
    total = len(results)
    if passed == total:
        print(f"{GREEN}Phase 9 gate PASSED{RESET} — {passed}/{total} checks.\n")
        return 0
    print(f"{RED}Phase 9 gate FAILED{RESET} — {passed}/{total}.")
    for ok, label, _ in results:
        if not ok:
            print(f"  - {label}")
    print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
