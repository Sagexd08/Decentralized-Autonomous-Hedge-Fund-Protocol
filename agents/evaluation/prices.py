"""
The reference price a prediction is settled against — Phase 5.

Settlement needs two numbers: what the asset was worth when the agent
committed, and what it was worth when the horizon closed. Both come from
`market_events`, which carries a `source` column, so an outcome can always say
where its evidence came from.

The single most important behaviour in this module is the one that *doesn't*
produce a number. If there is no observation near the timestamp being asked
about, `price_at` returns None and the prediction stays unsettled. The
alternative — interpolating, or falling back to the last price at any distance
— would quietly manufacture the ground truth an agent's reputation is computed
from. An agent that looks good because settlement guessed in its favour is
exactly the failure section 0c is about.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

import psycopg
from psycopg.types.json import Json

# How far from the requested instant an observation may sit and still count.
# Wide enough to tolerate a feed that ticks every few minutes; narrow enough
# that a stale price cannot be passed off as a settlement.
DEFAULT_TOLERANCE = timedelta(seconds=300)

PRICE_KIND = "PRICE"


@dataclass(frozen=True)
class Observation:
    price: float
    at: datetime
    source: str
    provider: Optional[str] = None

    @property
    def universe(self) -> tuple[str, Optional[str]]:
        """
        The price series this observation belongs to.

        Two observations share a universe when they came from the same kind of
        data *and* the same venue. Settlement pins both of its legs to one, for
        the reason in `price_at`.
        """
        return (self.source, self.provider)


# How much a source is worth when two of them cover the same instant. Strongest
# wins — see `price_at`.
SOURCE_RANK = {"LIVE": 3, "TESTNET": 2, "SIMULATION": 1}

_RANK_SQL = """
    case source when 'LIVE' then 3 when 'TESTNET' then 2 else 1 end
"""


def record_price(
    conn: psycopg.Connection,
    *,
    asset: str,
    price: float,
    at: datetime,
    source: str = "SIMULATION",
    provider: Optional[str] = None,
    ingest_mode: Optional[str] = None,
) -> None:
    """
    Write one price observation. `source` is the honesty label, not a hint.

    `provider` names the venue and is **required** by the schema whenever
    `source` is LIVE — a claim that a price came from a real market has to say
    which one. See `agents.market.ingest.record_observation` for the pipeline
    writer, which additionally deduplicates.
    """
    conn.execute(
        """
        insert into market_events
            (asset, kind, payload, source, provider, ingest_mode, occurred_at)
        values (%s, %s, %s, %s, %s, %s, %s)
        """,
        (asset, PRICE_KIND, Json({"price": float(price)}), source,
         provider, ingest_mode, at),
    )


def price_at(
    conn: psycopg.Connection,
    *,
    asset: str,
    at: datetime,
    tolerance: timedelta = DEFAULT_TOLERANCE,
    source: Optional[str] = None,
    provider: Optional[str] = None,
) -> Optional[Observation]:
    """
    The observation nearest `at`, or None if nothing is close enough.

    Nearest on either side rather than last-before: a settlement timestamp sits
    between two ticks, and the closer of the two is the better estimate of the
    price at that instant regardless of which side it falls on.

    **Source outranks proximity.** When a simulated tape and a real feed both
    cover the same instant, the real one wins even if it sits further from the
    timestamp. This looks like a small preference and is not: BTC is near
    77,000 on an exchange and near 100 on the synthetic tape, so a settlement
    that took its entry from one and its exit from the other would report a
    return of roughly 77,000%. Every downstream number — the IRIS Score, the
    risk engine's drawdown, the allocator's weights — is computed from that
    figure, and none of them can tell it apart from a real one.

    Preferring the strongest source makes the *usual* case coherent; pinning
    with `source` and `provider` makes it guaranteed, which is what settlement
    does once it has resolved its first leg.
    """
    filters = ["asset = %s", "kind = %s", "occurred_at between %s and %s"]
    params: list[object] = [asset, PRICE_KIND, at - tolerance, at + tolerance]
    if source is not None:
        filters.append("source = %s")
        params.append(source)
    if provider is not None:
        filters.append("provider is not distinct from %s")
        params.append(provider)
    params.append(at)

    row = conn.execute(
        f"""
        select (payload->>'price')::float8, occurred_at, source, provider
          from market_events
         where {' and '.join(filters)}
         order by {_RANK_SQL} desc,
                  abs(extract(epoch from (occurred_at - %s)))
         limit 1
        """,
        tuple(params),
    ).fetchone()

    if row is None:
        return None
    return Observation(price=float(row[0]), at=row[1], source=row[2], provider=row[3])


def latest_window(
    conn: psycopg.Connection,
    *,
    asset: str,
    size: int = 64,
    source: Optional[str] = None,
    max_age: Optional[timedelta] = None,
) -> list[Observation]:
    """
    The most recent `size` observations, oldest first.

    This is what an agent looks at. It comes from the same table settlement
    reads, deliberately: the one bug this system has hit twice is the agent and
    the scorer living in different price universes, and the only structural
    cure is for there to be exactly one series.

    Restricted to a single source — the strongest available unless pinned —
    for the reason spelled out in `price_at`. A window that splices a synthetic
    tape onto a real one has a 77,000% return in the middle of it, and every
    feature computed over that window is then a description of the splice.
    """
    resolved = source or strongest_source(conn, asset=asset, max_age=max_age)
    if resolved is None:
        return []

    filters = ["asset = %s", "kind = %s", "source = %s"]
    params: list[object] = [asset, PRICE_KIND, resolved]
    if max_age is not None:
        filters.append("occurred_at >= %s")
        params.append(utcnow() - max_age)
    params.append(size)

    rows = conn.execute(
        f"""
        select (payload->>'price')::float8, occurred_at, source, provider
          from market_events
         where {' and '.join(filters)}
         order by occurred_at desc
         limit %s
        """,
        tuple(params),
    ).fetchall()

    return [
        Observation(price=float(r[0]), at=r[1], source=r[2], provider=r[3])
        for r in reversed(rows)
    ]


def strongest_source(
    conn: psycopg.Connection,
    *,
    asset: str,
    max_age: Optional[timedelta] = None,
) -> Optional[str]:
    """
    The best-provenance source that actually has recent data for `asset`.

    Best available, not best imaginable: if the live feed has stopped and only
    a simulated tape is fresh, this returns SIMULATION and the label rides all
    the way to the UI. Section 0c is satisfied by saying so, not by refusing to
    run.
    """
    filters = ["asset = %s", "kind = %s"]
    params: list[object] = [asset, PRICE_KIND]
    if max_age is not None:
        filters.append("occurred_at >= %s")
        params.append(utcnow() - max_age)

    row = conn.execute(
        f"""
        select source
          from market_events
         where {' and '.join(filters)}
         order by {_RANK_SQL} desc, occurred_at desc
         limit 1
        """,
        tuple(params),
    ).fetchone()
    return row[0] if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Simulated feed
# ─────────────────────────────────────────────────────────────────────────────

def simulated_tape(
    *,
    start: datetime,
    end: datetime,
    step: timedelta = timedelta(seconds=60),
    seed: int = 0,
    start_price: float = 100.0,
) -> Iterator[tuple[datetime, float]]:
    """
    A deterministic Ornstein-Uhlenbeck tape over a time range.

    The same generator shape the agent graph observes, so a settled prediction
    is scored against a series with the same statistical character it was made
    on. Seeded, because section 18 requires simulation to be reproducible — and
    a settlement sweep you cannot replay is a settlement sweep you cannot
    audit.
    """
    rng = random.Random(seed)
    price = start_price
    at = start
    while at <= end:
        price += 0.02 * (start_price - price) + rng.gauss(0, 0.6)
        yield at, round(price, 6)
        at += step


def seed_simulated_prices(
    conn: psycopg.Connection,
    *,
    asset: str,
    start: datetime,
    end: datetime,
    step: timedelta = timedelta(seconds=60),
    seed: int = 0,
) -> int:
    """Populate `market_events` with a labelled simulated tape. Returns the count."""
    written = 0
    for at, price in simulated_tape(start=start, end=end, step=step, seed=seed):
        record_price(conn, asset=asset, price=price, at=at, source="SIMULATION")
        written += 1
    return written


def fill_price_gaps(
    conn: psycopg.Connection,
    *,
    asset: str,
    start: datetime,
    end: datetime,
    step: timedelta = timedelta(seconds=60),
    seed: int = 0,
) -> int:
    """
    Write only the ticks the tape is actually missing.

    Idempotent, which `seed_simulated_prices` is not. Two behaviours were both
    wrong before this existed: re-running the feed duplicated every tick, and
    guarding on "does the range already have observations" refused to extend a
    tape whose tail was missing — which is exactly the case that matters, since
    the tail is where an open prediction's horizon lands.

    A tick is considered present if an observation sits within half a step of
    it, so overlapping runs at slightly different offsets don't stack up.
    """
    existing = [
        row[0]
        for row in conn.execute(
            """select occurred_at from market_events
                where asset = %s and kind = %s and occurred_at between %s and %s
                order by occurred_at""",
            (asset, PRICE_KIND, start - step, end + step),
        ).fetchall()
    ]
    tolerance = step / 2
    written = 0
    index = 0
    for at, price in simulated_tape(start=start, end=end, step=step, seed=seed):
        # `existing` is sorted and `at` advances, so one pass suffices.
        while index < len(existing) and existing[index] < at - tolerance:
            index += 1
        covered = index < len(existing) and existing[index] <= at + tolerance
        if covered:
            continue
        record_price(conn, asset=asset, price=price, at=at, source="SIMULATION")
        written += 1
    return written


def strongest_outcome_source(conn: psycopg.Connection) -> str:
    """
    The best-provenance bucket that actually holds scored outcomes.

    Reputation, risk and allocation are all computed per provenance and never
    across it — a simulated track record must not be aggregated into a live
    one. That left every one of them defaulting to SIMULATION, which was
    correct while it was the only bucket that existed and became a quiet bug
    the moment the protocol started settling against a real market: the
    outcomes were LIVE, the scorers were reading SIMULATION, and every agent
    with a real record showed as "no settled predictions".

    Resolved from the data rather than pinned to LIVE. If the feed is down and
    only simulated outcomes exist, this returns SIMULATION and the label rides
    all the way to the UI, which is the honest answer — not a refusal to run.
    """
    row = conn.execute(
        """
        select data_source
          from prediction_outcomes
         where evaluation_score is not null
         group by data_source
         order by case data_source
                    when 'LIVE' then 3 when 'TESTNET' then 2 else 1
                  end desc
         limit 1
        """
    ).fetchone()
    return row[0] if row else "SIMULATION"


def realised_return(entry: float, exit_: float) -> float:
    """
    Fractional return between two prices.

    Guarded rather than trusting: a zero or negative entry price would make the
    return infinite or sign-flipped, and that number would go straight into an
    agent's score.
    """
    if entry <= 0 or not math.isfinite(entry) or not math.isfinite(exit_):
        raise ValueError(f"cannot compute a return from entry={entry} exit={exit_}")
    return (exit_ - entry) / entry


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """
    Record a labelled price tape so predictions can be settled against it.

    Without something writing prices, the settlement sweep has an entry price
    (recorded by the agent at commit time) and no exit price, so every
    prediction parks in WAITING_FOR_OUTCOME forever. That is the *correct*
    behaviour with no data, but it is not a working system — this is the piece
    that closes the loop.

    In production this is replaced by a real feed. Until then everything it
    writes is stamped SIMULATION, and that label rides through settlement into
    `prediction_outcomes.data_source`, so nothing built on it can be mistaken
    for live performance.

        python -m agents.evaluation.prices --asset BTC --hours 4
    """
    import argparse

    from agents.runtime.persistence import connection

    parser = argparse.ArgumentParser(description="Write a simulated price tape.")
    parser.add_argument("--asset", default="BTC")
    parser.add_argument("--hours", type=float, default=4.0,
                        help="how far back to start the tape")
    parser.add_argument("--forward-minutes", type=float, default=30.0,
                        help="how far past now to extend it")
    parser.add_argument("--step-seconds", type=int, default=60)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    now = utcnow()
    start = now - timedelta(hours=args.hours)
    end = now + timedelta(minutes=args.forward_minutes)

    step = timedelta(seconds=args.step_seconds)

    with connection() as conn:
        # Gap-filling rather than a coverage check. Overlapping ticks are
        # harmless to `price_at`, which takes the nearest observation, but
        # duplicates make settlement non-reproducible — and refusing to write
        # because a range is "mostly covered" leaves exactly the tail gap that
        # open predictions need.
        written = fill_price_gaps(
            conn, asset=args.asset, start=start, end=end, step=step, seed=args.seed,
        )

    if not written:
        print(f"{args.asset}: tape already complete from {start:%H:%M} to {end:%H:%M} UTC")
        return 0

    print(f"{args.asset}: wrote {written} SIMULATION observation(s) "
          f"from {start:%H:%M} to {end:%H:%M} UTC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
