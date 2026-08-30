"""
The protocol event WebSocket — IRIS_BUILD_PROMPT v2.0 section 14, Phase 9.

    ws://localhost:8000/ws/events
    ws://localhost:8000/ws/events?agent=AGT-QUANTA
    ws://localhost:8000/ws/events?kinds=PREDICTION_COMMITTED,AGENT_SLASHED
    ws://localhost:8000/ws/events?since=1042

Distinct from the pre-v2 `/ws/trading` and `/ws/prices` sockets, which
broadcast simulated ticks generated in-process. Every frame here corresponds to
a row in `protocol_events`, written by a trigger on one of the eight tables
phases 3-8 populate, and carries the `source_table` and `source_id` needed to
go and read that row. A client can verify the feed instead of trusting it.

`since` makes reconnection lossless. `protocol_events.seq` is monotonic across
every source, so a client that records the last sequence number it processed
and reconnects with it has missed nothing — which also means a dropped
connection is a delay rather than a hole in the record.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from services.event_stream import DEFAULT_BACKLOG, fetch_since, backlog, stream

logger = logging.getLogger(__name__)
router = APIRouter()

# How long to wait for an event before sending a keepalive. Proxies and load
# balancers close idle WebSockets, and this stream is legitimately quiet
# between agent cycles — without this a working connection looks dead.
IDLE_PING_SECONDS = 20.0


def _connection(dsn: Optional[str] = None):
    import psycopg

    from services.event_stream import stream as default_stream

    return psycopg.connect(dsn or default_stream.dsn)


@router.websocket("/ws/events")
async def ws_events(
    websocket: WebSocket,
    agent: Optional[str] = Query(None, description="only this agent's events"),
    kinds: Optional[str] = Query(None, description="comma-separated event kinds"),
    since: Optional[int] = Query(None, description="resume after this sequence number"),
    replay: int = Query(DEFAULT_BACKLOG, ge=0, le=500,
                        description="how many recent events to send on connect"),
):
    await websocket.accept()

    wanted = {k.strip() for k in kinds.split(",") if k.strip()} if kinds else None
    subscriber = stream.subscribe(agent_id=agent, kinds=wanted)

    try:
        # Catch the client up before subscribing it to live traffic. Done in
        # this order deliberately: the subscription is registered first (above),
        # so an event arriving during the catch-up is queued rather than lost,
        # and the client de-duplicates on `seq`.
        history = await asyncio.to_thread(_catch_up, since, replay, agent)
        await websocket.send_text(json.dumps({
            "kind": "STREAM_OPEN",
            "watermark": stream.watermark,
            "replaying": len(history),
            # Said out loud rather than left for the reader to infer: this feed
            # carries whatever provenance its rows carry, and right now every
            # upstream row is SIMULATION.
            "note": "every frame carries data_source; nothing here is live capital",
        }))
        for event in history:
            if subscriber.wants(event):
                await websocket.send_text(event.to_json())

        while True:
            try:
                event = await asyncio.wait_for(
                    subscriber.queue.get(), timeout=IDLE_PING_SECONDS
                )
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({
                    "kind": "KEEPALIVE", "watermark": stream.watermark,
                }))
                continue
            await websocket.send_text(event.to_json())

    except WebSocketDisconnect:
        pass
    except Exception as exc:                     # pragma: no cover - transport
        logger.warning("event socket closed: %s", exc)
    finally:
        stream.unsubscribe(subscriber)


def _catch_up(since: Optional[int], replay: int, agent: Optional[str]):
    """
    What to send before live events start.

    `since` wins over `replay`: a client that knows where it left off wants
    everything after that, not a fixed window that might not reach back far
    enough.
    """
    with _connection() as conn:
        if since is not None:
            return fetch_since(conn, since)
        if replay:
            return backlog(conn, limit=replay, agent_id=agent)
        return []


@router.get("/api/events")
async def recent_events(
    agent: Optional[str] = Query(None),
    since: Optional[int] = Query(None),
    limit: int = Query(DEFAULT_BACKLOG, ge=1, le=500),
):
    """
    The same stream over HTTP, for clients that cannot hold a socket open.

    Also the thing that makes the WebSocket checkable: a test — or a person —
    can compare what the socket delivered against what this returns, and both
    against the table itself.
    """
    events = await asyncio.to_thread(_catch_up_http, since, limit, agent)
    return {
        "watermark": stream.watermark,
        "count": len(events),
        "events": [json.loads(e.to_json()) for e in events],
    }


def _catch_up_http(since: Optional[int], limit: int, agent: Optional[str]):
    with _connection() as conn:
        if since is not None:
            return fetch_since(conn, since, limit=limit)
        return backlog(conn, limit=limit, agent_id=agent)


@router.get("/api/events/health")
async def event_stream_health():
    """
    Whether the tail is running and how far behind it is.

    Lag is the number that matters. A stream that is up but stalled looks
    identical to a working one from the outside, and the only way to tell is to
    compare its watermark against the table's.
    """
    def read() -> int:
        from services.event_stream import latest_seq

        with _connection() as conn:
            return latest_seq(conn)

    head = await asyncio.to_thread(read)
    return {
        "running": stream._task is not None and not stream._task.done(),
        "watermark": stream.watermark,
        "head": head,
        "lag": max(0, head - stream.watermark),
        "subscribers": stream.subscriber_count,
    }
