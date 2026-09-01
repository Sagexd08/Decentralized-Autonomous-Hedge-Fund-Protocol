"""
The live market feed, running inside the API — Phase 13.

A protocol whose prices arrive only when someone remembers to run a CLI is not
a live protocol. This is the loop that keeps `market_events` up with the clock,
so that a prediction committed now can actually be settled when its horizon
closes ten minutes from now.

Three behaviours are deliberate:

**It backfills before it streams.** A cold database has no window for an agent
to compute a feature over, and no entry price for a prediction made a minute
after boot. The backfill runs as a task rather than inside the lifespan, so a
slow venue delays the feed rather than the API.

**It reports its own failures instead of absorbing them.** `status()` carries
the last error, the consecutive failure count and the age of the newest tick.
A feed that has stopped looks exactly like a calm market from the outside, and
the only difference visible to a caller is whether something says so.

**It never fabricates a tick.** If every venue is unreachable, nothing is
written. Downstream, `price_at` finds no evidence, the prediction parks in
WAITING_FOR_OUTCOME, and it is never scored. That gap is the correct output.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

DEFAULT_ASSETS: tuple[str, ...] = tuple(
    a.strip().upper()
    for a in os.getenv("IRIS_FEED_ASSETS", "BTC,ETH,SOL").split(",")
    if a.strip()
)
DEFAULT_INTERVAL = float(os.getenv("IRIS_FEED_INTERVAL_SECONDS", "30"))

# Whether this process should poll at all.
#
# On a host that suspends an idle service — Render's free tier stops one after
# fifteen minutes without inbound traffic — a poller inside the API is not a
# feed, it is a feed that runs only while somebody happens to be looking. The
# scheduled cycle ingests too, and its window is computed from the oldest
# prediction still awaiting evidence, so it covers the gaps this would leave.
# Turning the poller off there is honest; leaving it on would produce a tape
# with holes shaped like the traffic pattern.
ENABLED = os.getenv("IRIS_FEED_ENABLED", "true").strip().lower() not in {
    "false", "0", "no", "off",
}
BACKFILL_MINUTES = int(os.getenv("IRIS_FEED_BACKFILL_MINUTES", "720"))
PREFERRED_PROVIDER = os.getenv("IRIS_FEED_PROVIDER") or None

# Below this, the backfill runs on boot. Above it, the tape is already good
# enough to compute a window over and re-reading history is wasted requests.
COVERAGE_FLOOR = 0.80


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LiveFeed:
    """Polls public venues and writes LIVE observations into `market_events`."""

    def __init__(
        self,
        assets: Sequence[str] = DEFAULT_ASSETS,
        interval: float = DEFAULT_INTERVAL,
        preferred: Optional[str] = PREFERRED_PROVIDER,
    ) -> None:
        self.assets = tuple(assets)
        self.interval = max(5.0, float(interval))
        self.preferred = preferred

        self._task: Optional[asyncio.Task] = None
        self._backfill: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()

        self.started_at: Optional[datetime] = None
        self.last_tick_at: Optional[datetime] = None
        self.last_provider: Optional[str] = None
        self.written = 0
        self.polls = 0
        self.consecutive_failures = 0
        self.last_error: Optional[str] = None
        self.backfill_summary: list[str] = []

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        if not ENABLED:
            logger.info(
                "Live market feed disabled (IRIS_FEED_ENABLED); the scheduled "
                "cycle ingests instead."
            )
            return
        if self._task is not None:
            return
        self._stopping.clear()
        self.started_at = _utcnow()
        self._backfill = asyncio.create_task(self._backfill_if_thin())
        self._task = asyncio.create_task(self._run())
        logger.info(
            "Live market feed started: %s every %.0fs (venue: %s)",
            ", ".join(self.assets), self.interval, self.preferred or "first available",
        )

    async def stop(self) -> None:
        self._stopping.set()
        for task in (self._task, self._backfill):
            if task is None:
                continue
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._task = self._backfill = None

    # ── work ─────────────────────────────────────────────────────────────────

    async def _backfill_if_thin(self) -> None:
        """Fill history for any asset whose recent coverage is poor."""
        try:
            for asset in self.assets:
                if self._stopping.is_set():
                    return
                summary = await asyncio.to_thread(self._backfill_asset, asset)
                if summary:
                    self.backfill_summary.append(summary)
                    logger.info("Market backfill — %s", summary)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Market backfill failed: %s", exc)

    def _backfill_asset(self, asset: str) -> Optional[str]:
        from agents.market.ingest import backfill, live_coverage
        from agents.runtime.persistence import connection

        with connection() as conn:
            coverage = live_coverage(conn, asset=asset, minutes=BACKFILL_MINUTES)
            if coverage["coverage"] >= COVERAGE_FLOOR:
                return (
                    f"{asset}: {coverage['coverage']:.0%} of the last "
                    f"{BACKFILL_MINUTES}m already present, skipped"
                )
            report = backfill(
                conn, asset=asset, minutes=BACKFILL_MINUTES, preferred=self.preferred
            )
        return str(report)

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                await asyncio.to_thread(self._poll_once)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - the loop must outlive a failure
                self.consecutive_failures += 1
                self.last_error = str(exc)
                logger.warning("Market feed poll failed: %s", exc)

            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                continue

    def _poll_once(self) -> None:
        from agents.market.ingest import tick
        from agents.runtime.persistence import connection

        wrote = False
        failures: list[str] = []

        with connection() as conn:
            for asset in self.assets:
                report = tick(conn, asset=asset, preferred=self.preferred)
                if not report.ok:
                    failures.append(
                        f"{asset}: " + "; ".join(report.failures.values())
                    )
                    continue
                self.written += report.written
                self.last_provider = report.provider
                wrote = True

        self.polls += 1
        if wrote:
            self.last_tick_at = _utcnow()
            self.consecutive_failures = 0
            self.last_error = None
        else:
            self.consecutive_failures += 1
            self.last_error = " | ".join(failures) or "no venue answered"

    # ── introspection ────────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def status(self) -> dict:
        """What this poller is doing, including deliberately nothing."""
        age = (
            (_utcnow() - self.last_tick_at).total_seconds()
            if self.last_tick_at
            else None
        )
        return {
            "running": self.running,
            # Distinguished from "running": false so a health check can tell a
            # poller that was switched off from one that crashed.
            "enabled": ENABLED,
            "assets": list(self.assets),
            "interval_seconds": self.interval,
            "provider": self.last_provider,
            "preferred_provider": self.preferred,
            "polls": self.polls,
            "observations_written": self.written,
            "last_tick_at": self.last_tick_at.isoformat() if self.last_tick_at else None,
            "seconds_since_last_tick": None if age is None else round(age, 1),
            "consecutive_failures": self.consecutive_failures,
            # Reported, not swallowed. A feed with a persistent error and a
            # green "running" flag is the exact shape of a dashboard that lies.
            "last_error": self.last_error,
            "healthy": self.running and self.consecutive_failures == 0
                       and self.last_tick_at is not None,
            "backfill": list(self.backfill_summary),
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }


feed = LiveFeed()
