"""
Getting real prices into the protocol — IRIS_BUILD_PROMPT v2.0 sections 0c and
13, Phase 13.

This is the piece that changes what every number downstream means. Settlement,
the IRIS Score, the risk engine and the allocator were all built to read
`market_events` and to carry its `source` label forward; none of them needed
to change. What changes is that the rows are now observations of a market that
exists.

Two ingest modes, both writing the same table:

  * **backfill** reads completed one-minute bars from a venue's history. It is
    how a cold database gets a tape an agent can compute features over, and how
    a prediction made ten minutes ago becomes settleable now.
  * **stream** polls the current quote. It is how the tape keeps up with the
    clock so that predictions made *now* can be settled when their horizon
    closes.

Both are idempotent against `idx_market_events_ingested_tick`. That matters
more than it sounds: a poller that retries after a timeout, or a backfill run
twice over an overlapping window, would otherwise write the same minute of the
market repeatedly and double-weight it in every feature computed over the
window — an error that makes volatility look real and is invisible in the
series itself.

What this module will not do is invent a price. If every venue is unreachable
it reports the failure and writes nothing; `price_at` then returns None, the
prediction stays WAITING_FOR_OUTCOME, and nothing is scored. An unscored
prediction is a gap in the record. A guessed one is a lie in it.

    python -m agents.market.ingest --asset BTC --minutes 240
    python -m agents.market.ingest --stream --interval 20
    python -m agents.market.ingest --divergence
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence

import psycopg
from psycopg.types.json import Json

from agents.market.providers import (
    ASSETS,
    Candle,
    MarketDataError,
    Provider,
    divergence,
    providers_for,
    utcnow,
)

PRICE_KIND = "PRICE"
LIVE = "LIVE"

# How stale the newest observation may be before the feed counts as down.
# Three minutes: long enough that one missed poll or a slow venue is not an
# outage, short enough that a stopped feed is caught before an agent trades on
# a tape that stopped moving.
STALE_AFTER = timedelta(minutes=3)


@dataclass
class IngestReport:
    asset: str
    mode: str
    provider: Optional[str] = None
    written: int = 0
    skipped: int = 0
    first: Optional[datetime] = None
    last: Optional[datetime] = None
    failures: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.provider is not None

    def __str__(self) -> str:
        if not self.ok:
            reasons = "; ".join(f"{k}: {v}" for k, v in self.failures.items())
            return f"{self.asset}: no venue answered ({reasons or 'no venue configured'})"
        window = ""
        if self.first and self.last:
            window = f" covering {self.first:%H:%M} to {self.last:%H:%M} UTC"
        return (
            f"{self.asset}: {self.written} LIVE observation(s) from "
            f"{self.provider} ({self.mode}), {self.skipped} already present{window}"
        )


def record_observation(
    conn: psycopg.Connection,
    *,
    asset: str,
    price: float,
    at: datetime,
    source: str,
    provider: Optional[str],
    ingest_mode: Optional[str],
    payload: Optional[dict] = None,
) -> bool:
    """
    Write one observation, or decline because it is already there.

    Returns True when a row was inserted. The conflict target names the partial
    unique index exactly, so only rows carrying a provider — the ones this
    pipeline writes — participate in the deduplication.
    """
    body = dict(payload or {})
    body["price"] = float(price)

    row = conn.execute(
        """
        insert into market_events
            (asset, kind, payload, source, provider, ingest_mode, occurred_at)
        values (%s, %s, %s, %s, %s, %s, %s)
        on conflict (asset, kind, occurred_at, source) where provider is not null
        do nothing
        returning id
        """,
        (asset, PRICE_KIND, Json(body), source, provider, ingest_mode, at),
    ).fetchone()
    return row is not None


def _write_candles(
    conn: psycopg.Connection,
    *,
    asset: str,
    provider: Provider,
    candles: Sequence[Candle],
    mode: str,
) -> tuple[int, int]:
    written = skipped = 0
    for candle in candles:
        inserted = record_observation(
            conn,
            asset=asset,
            price=candle.close,
            at=candle.at,
            source=LIVE,
            provider=provider.name,
            ingest_mode=mode,
            payload=candle.as_payload(),
        )
        written += int(inserted)
        skipped += int(not inserted)
    return written, skipped


def backfill(
    conn: psycopg.Connection,
    *,
    asset: str = "BTC",
    minutes: int = 240,
    preferred: Optional[str] = None,
    end: Optional[datetime] = None,
) -> IngestReport:
    """
    Fill the last `minutes` of one-minute bars for `asset`.

    Venues are tried in order and the first that answers wins the whole run —
    not the whole *tape*, but this run's rows all carry one venue's name. See
    the module docstring in `providers` for why a tape must not be blended.
    """
    report = IngestReport(asset=asset, mode="backfill")

    for provider in providers_for(asset, preferred):
        try:
            candles = provider.candles(asset, minutes=minutes, end=end)
        except MarketDataError as exc:
            report.failures[provider.name] = str(exc)
            continue

        if not candles:
            report.failures[provider.name] = "returned no bars"
            continue

        written, skipped = _write_candles(
            conn, asset=asset, provider=provider, candles=candles, mode="backfill"
        )
        report.provider = provider.name
        report.written = written
        report.skipped = skipped
        report.first = candles[0].at
        report.last = candles[-1].at
        return report

    return report


def tick(
    conn: psycopg.Connection,
    *,
    asset: str = "BTC",
    preferred: Optional[str] = None,
) -> IngestReport:
    """Record the current quote for `asset` from the first venue that answers."""
    report = IngestReport(asset=asset, mode="stream")

    for provider in providers_for(asset, preferred):
        try:
            quote = provider.quote(asset)
        except MarketDataError as exc:
            report.failures[provider.name] = str(exc)
            continue

        inserted = record_observation(
            conn,
            asset=asset,
            price=quote.price,
            at=quote.at,
            source=LIVE,
            provider=provider.name,
            ingest_mode="stream",
            payload={"venue_symbol": provider.symbol_for(asset)},
        )
        report.provider = provider.name
        report.written = int(inserted)
        report.skipped = int(not inserted)
        report.first = report.last = quote.at
        return report

    return report


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

def feed_status(
    conn: psycopg.Connection, assets: Iterable[str] = ASSETS
) -> list[dict]:
    """
    Per asset and source: how much data there is and how old the newest is.

    Reads `market_feed_status`, the view added in migration 0005. `stale` is
    the field that matters — a feed that stopped ten minutes ago is
    indistinguishable from a quiet market unless something says so.
    """
    wanted = tuple(a.upper() for a in assets)
    rows = conn.execute(
        """
        select asset, source, provider, observations, first_seen, last_seen, lag_seconds
          from market_feed_status
         where asset = any(%s)
         order by asset, source, provider nulls first
        """,
        (list(wanted),),
    ).fetchall()

    return [
        {
            "asset": r[0],
            "source": r[1],
            "provider": r[2],
            "observations": int(r[3]),
            "first_seen": r[4],
            "last_seen": r[5],
            "lag_seconds": int(r[6]) if r[6] is not None else None,
            "stale": r[6] is None or int(r[6]) > STALE_AFTER.total_seconds(),
        }
        for r in rows
    ]


def live_coverage(
    conn: psycopg.Connection,
    *,
    asset: str,
    minutes: int = 240,
    step_seconds: int = 60,
) -> dict:
    """
    What fraction of the last `minutes` is actually covered by LIVE ticks.

    A count of rows is not coverage: a thousand observations of one minute and
    a thousand spread over a day support very different claims, and only the
    second lets a model compute a window or a settlement find both its legs.
    """
    end = utcnow()
    start = end - timedelta(minutes=minutes)
    row = conn.execute(
        """
        select count(*), count(distinct date_trunc('minute', occurred_at)),
               min(occurred_at), max(occurred_at)
          from market_events
         where asset = %s and kind = %s and source = %s
           and occurred_at between %s and %s
        """,
        (asset, PRICE_KIND, LIVE, start, end),
    ).fetchone()

    observations, distinct_minutes = int(row[0]), int(row[1])
    expected = max(1, int(minutes * 60 / step_seconds))
    return {
        "asset": asset,
        "window_minutes": minutes,
        "observations": observations,
        "distinct_minutes": distinct_minutes,
        "expected_minutes": expected,
        "coverage": round(min(1.0, distinct_minutes / expected), 4),
        "first_seen": row[2],
        "last_seen": row[3],
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _stream(
    dsn: Optional[str], assets: Sequence[str], interval: float, preferred: Optional[str]
) -> int:
    from agents.runtime.persistence import connection

    print(
        f"streaming {', '.join(assets)} every {interval:g}s "
        f"(ctrl-c to stop)",
        file=sys.stderr,
    )
    while True:
        for asset in assets:
            try:
                with connection(dsn) as conn:
                    report = tick(conn, asset=asset, preferred=preferred)
                print(report)
            except Exception as exc:  # noqa: BLE001 - a poller must outlive one failure
                print(f"{asset}: {exc}", file=sys.stderr)
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    from agents.runtime.persistence import connection

    parser = argparse.ArgumentParser(description="Ingest real market data.")
    parser.add_argument("--asset", action="append", default=None,
                        help="repeatable; defaults to BTC")
    parser.add_argument("--minutes", type=int, default=240,
                        help="how much history to backfill")
    parser.add_argument("--provider", default=None,
                        help="preferred venue: binance, coinbase or kraken")
    parser.add_argument("--stream", action="store_true",
                        help="poll the current quote forever")
    parser.add_argument("--interval", type=float, default=20.0)
    parser.add_argument("--once", action="store_true",
                        help="record a single current quote and exit")
    parser.add_argument("--divergence", action="store_true",
                        help="report how far the venues sit apart; writes nothing")
    parser.add_argument("--status", action="store_true",
                        help="report feed health and coverage; writes nothing")
    parser.add_argument("--dsn", default=None)
    args = parser.parse_args(argv)

    assets = [a.upper() for a in (args.asset or ["BTC"])]

    if args.divergence:
        for asset in assets:
            d = divergence(asset)
            quotes = ", ".join(f"{k} {v:,.2f}" for k, v in sorted(d["quotes"].items()))
            spread = "—" if d["spread_bps"] is None else f"{d['spread_bps']:.1f}bps"
            print(f"{asset}: {quotes or 'no venue answered'} | spread {spread}")
            for name, why in d["failures"].items():
                print(f"  {name} unavailable: {why}", file=sys.stderr)
        return 0

    if args.status:
        with connection(args.dsn) as conn:
            for row in feed_status(conn, assets):
                mark = "STALE" if row["stale"] else "ok"
                print(
                    f"{row['asset']:<5} {row['source']:<11} "
                    f"{row['provider'] or '—':<9} {row['observations']:>6} obs  "
                    f"lag {row['lag_seconds']}s  {mark}"
                )
            for asset in assets:
                c = live_coverage(conn, asset=asset)
                print(
                    f"{asset:<5} live coverage {c['coverage']:.1%} "
                    f"({c['distinct_minutes']}/{c['expected_minutes']} minutes)"
                )
        return 0

    if args.stream:
        return _stream(args.dsn, assets, args.interval, args.provider)

    failed = False
    with connection(args.dsn) as conn:
        for asset in assets:
            if args.once:
                report = tick(conn, asset=asset, preferred=args.provider)
            else:
                report = backfill(
                    conn, asset=asset, minutes=args.minutes, preferred=args.provider
                )
            print(report)
            failed = failed or not report.ok

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
