"""
The protocol event stream — IRIS_BUILD_PROMPT v2.0 sections 14 and 19, Phase 9.

Reads `protocol_events` and fans it out to connected WebSocket clients. That is
the whole job, and the narrowness is the point: this module cannot invent an
event, because it has no way to produce one. Events are written by triggers on
the eight tables phases 3-8 touch (see `db/migrations/0004_events.sql`), so
every frame a client receives names a `source_table` and a `source_id` it can
go and read for itself.

That property is what Phase 9's DoD is actually asking for. "Real events reach
a connected client" is trivially satisfiable by a generator emitting plausible
traffic on a timer — which is exactly what the pre-v2 sockets in this repo do —
and the difference is invisible from the client side. Making the event a row
first, and the socket a reader second, is the only version of this that can be
checked.

Delivery is at-least-once from the client's point of view: a client that
reconnects with `?since=<seq>` gets everything after that sequence number.
`protocol_events.seq` is monotonic across every source table, so a prediction
can never arrive before the run that produced it, and a reconnecting client
never has to guess whether it missed something.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

# How often to sweep for new rows when LISTEN/NOTIFY is unavailable. A fallback,
# not the primary path: the triggers call pg_notify, so the normal case is
# push. Polling exists because a dropped listener connection must degrade to a
# slower stream rather than a silent one.
POLL_SECONDS = float(os.getenv("IRIS_EVENT_POLL_SECONDS", "1.0"))

# Rows per fetch. Bounded so a client connecting after a long backlog gets a
# steady stream rather than one enormous frame.
BATCH = 200

# What a new client is sent before live events start. Enough to render a
# dashboard immediately; not so much that a reconnect replays the whole history.
DEFAULT_BACKLOG = 50

CHANNEL = "iris_events"


@dataclass(frozen=True)
class Event:
    """One row of `protocol_events`, as it goes over the wire."""

    seq: int
    kind: str
    source_table: str
    source_id: str
    agent_id: Optional[str]
    data_source: str
    payload: dict[str, Any]
    created_at: str

    def to_json(self) -> str:
        return json.dumps({
            "seq": self.seq,
            "kind": self.kind,
            # The two fields that make this checkable rather than merely
            # plausible: a client can read the row this came from.
            "source_table": self.source_table,
            "source_id": self.source_id,
            "agent_id": self.agent_id,
            # Never omitted. A frame without it hands the UI a number with no
            # way to know it came from a simulated tape (section 0c).
            "data_source": self.data_source,
            "payload": self.payload,
            "created_at": self.created_at,
        }, default=str)


def row_to_event(row: tuple) -> Event:
    return Event(
        seq=int(row[0]),
        kind=row[1],
        source_table=row[2],
        source_id=row[3],
        agent_id=row[4],
        data_source=row[5],
        payload=row[6] if isinstance(row[6], dict) else json.loads(row[6] or "{}"),
        created_at=row[7].isoformat() if row[7] else "",
    )


SELECT = """
    select seq, kind, source_table, source_id, agent_id, data_source,
           payload, created_at
      from protocol_events
     where seq > %s
  order by seq
     limit %s
"""


def fetch_since(conn, since: int, limit: int = BATCH) -> list[Event]:
    """Every event after `since`, in order."""
    return [row_to_event(r) for r in conn.execute(SELECT, (since, limit)).fetchall()]


def latest_seq(conn) -> int:
    row = conn.execute("select coalesce(max(seq), 0) from protocol_events").fetchone()
    return int(row[0]) if row else 0


def backlog(conn, limit: int = DEFAULT_BACKLOG, agent_id: Optional[str] = None) -> list[Event]:
    """
    The most recent events, oldest first.

    Reversed after fetching rather than ordered ascending with an OFFSET: the
    index is on `seq DESC`, and a dashboard opening against a long history
    should not scan the whole table to find its last fifty rows.
    """
    sql = """
        select seq, kind, source_table, source_id, agent_id, data_source,
               payload, created_at
          from protocol_events
         {where}
      order by seq desc
         limit %s
    """.format(where="where agent_id = %s" if agent_id else "")
    params = (agent_id, limit) if agent_id else (limit,)
    rows = conn.execute(sql, params).fetchall()
    return [row_to_event(r) for r in reversed(rows)]


# ─────────────────────────────────────────────────────────────────────────────
# Fan-out
# ─────────────────────────────────────────────────────────────────────────────

class Subscriber:
    """
    One connected client, with a bounded queue.

    Bounded on purpose. An unbounded queue behind a client that has stopped
    reading is a slow memory leak that only shows up under the load it is least
    able to survive — so a subscriber that falls far enough behind is dropped
    and told to reconnect with a watermark, which it can do losslessly because
    `seq` is monotonic.
    """

    MAX_PENDING = 1000

    def __init__(self, agent_id: Optional[str] = None, kinds: Optional[set[str]] = None):
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self.MAX_PENDING)
        self.agent_id = agent_id
        self.kinds = kinds
        self.dropped = False

    def wants(self, event: Event) -> bool:
        if self.agent_id and event.agent_id != self.agent_id:
            return False
        if self.kinds and event.kind not in self.kinds:
            return False
        return True

    def offer(self, event: Event) -> None:
        if not self.wants(event):
            return
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            self.dropped = True


class EventStream:
    """
    The single reader. One database tail feeding every client.

    One connection rather than one per client: a hundred dashboards must not
    become a hundred `LISTEN` connections, and the ordering guarantee is easier
    to reason about when there is exactly one place that advances the watermark.
    """

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or os.getenv(
            "DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris"
        )
        self._subscribers: set[Subscriber] = set()
        self._watermark = 0
        self._task: Optional[asyncio.Task] = None
        self._started = asyncio.Event()

    # ── subscription ────────────────────────────────────────────────────────

    def subscribe(
        self, *, agent_id: Optional[str] = None, kinds: Optional[Iterable[str]] = None
    ) -> Subscriber:
        sub = Subscriber(agent_id=agent_id, kinds=set(kinds) if kinds else None)
        self._subscribers.add(sub)
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        self._subscribers.discard(sub)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def watermark(self) -> int:
        return self._watermark

    # ── the tail ────────────────────────────────────────────────────────────

    async def start(self, *, from_seq: Optional[int] = None) -> None:
        if self._task and not self._task.done():
            return
        self._watermark = from_seq if from_seq is not None else await self._latest()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def wait_started(self, timeout: float = 5.0) -> None:
        await asyncio.wait_for(self._started.wait(), timeout=timeout)

    async def _latest(self) -> int:
        import psycopg

        def read() -> int:
            with psycopg.connect(self.dsn) as conn:
                return latest_seq(conn)

        return await asyncio.to_thread(read)

    async def _drain(self) -> list[Event]:
        import psycopg

        def read() -> list[Event]:
            with psycopg.connect(self.dsn) as conn:
                return fetch_since(conn, self._watermark)

        return await asyncio.to_thread(read)

    async def _run(self) -> None:
        """
        Tail the log and fan out.

        Polls rather than blocking on LISTEN. The triggers do call `pg_notify`,
        and a notify-driven loop is the obvious design — but psycopg's notify
        generator holds a connection open in a way that is awkward to cancel
        cleanly from a FastAPI lifespan, and a stream that cannot be shut down
        makes the test suite hang rather than fail. One query per second against
        an indexed `seq > n` is cheap, and correctness here matters more than
        latency: nothing downstream is sub-second.
        """
        self._started.set()
        while True:
            try:
                events = await self._drain()
                if events:
                    self._watermark = events[-1].seq
                    for event in events:
                        self._dispatch(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:            # a dead connection must not kill the tail
                logger.warning("event stream read failed: %s", exc)
            await asyncio.sleep(POLL_SECONDS)

    def _dispatch(self, event: Event) -> None:
        for sub in list(self._subscribers):
            sub.offer(event)
            if sub.dropped:
                logger.warning("subscriber fell behind and was dropped")
                self._subscribers.discard(sub)


# The process-wide stream. One tail, however many clients.
stream = EventStream()


def main(argv: list[str] | None = None) -> int:
    """
    Tail the event log on the terminal.

    The same rows the WebSocket delivers, printed. Useful for the thing a
    dashboard cannot show you: whether an event exists at all, independently of
    whether anything is rendering it.

        python -m services.event_stream
    """
    import argparse
    import time

    import psycopg

    parser = argparse.ArgumentParser(description="Tail the protocol event stream.")
    parser.add_argument("--agent", default=None)
    parser.add_argument("--since", type=int, default=None)
    parser.add_argument("--replay", type=int, default=20)
    parser.add_argument("--follow", action="store_true", help="keep tailing")
    args = parser.parse_args(argv)

    dsn = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")

    def show(event: Event) -> None:
        agent = event.agent_id or "—"
        print(f"{event.seq:>7}  {event.kind:<24}{agent:<14}"
              f"{event.source_table:<20}{event.data_source}")

    with psycopg.connect(dsn) as conn:
        print(f"{'seq':>7}  {'kind':<24}{'agent':<14}{'source':<20}provenance")
        print("-" * 78)
        if args.since is not None:
            events = fetch_since(conn, args.since, limit=500)
        else:
            events = backlog(conn, limit=args.replay, agent_id=args.agent)
        for event in events:
            show(event)
        cursor = events[-1].seq if events else latest_seq(conn)

    if not args.follow:
        return 0

    while True:
        try:
            with psycopg.connect(dsn) as conn:
                for event in fetch_since(conn, cursor, limit=500):
                    show(event)
                    cursor = event.seq
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            logger.warning("tail failed: %s", exc)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
