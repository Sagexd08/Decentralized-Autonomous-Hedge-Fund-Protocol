"""
The series the models are fitted on — IRIS_BUILD_PROMPT v2.0 sections 11, 12
and 18; invariant 3. Phase 13.

Every model in this system was trained on a seeded Ornstein-Uhlenbeck tape
starting at 100.0 with a noise term of 0.6. That is a one-step return with a
standard deviation near 60 basis points. Real one-minute BTC returns have a
standard deviation nearer *one* basis point.

The consequence is not subtle and it is not visible in any type or test. Feed
a model trained on the synthetic tape a window of real prices and it predicts a
move roughly sixty times too large — the first live run produced BUY +0.83%
over a ten-minute horizon on a tape whose realised volatility was 10bps, a
2.6-sigma call made with 88% confidence, and it would have made one every
single run. Nothing crashes. The prediction commits, the hash is honest, the
settlement is honest, and the agent is simply wrong in a fixed direction
forever because it is answering a question about a different market.

So the training set becomes real too. Two properties matter:

**It is a frozen snapshot, not a live query.** If the training series were
"the last 600 ticks", it would change every minute, the artifact cache key
would change with it, and every agent would retrain on every run — 25 seconds
per transformer, and a new `model_hash` each time. Invariant 3 says model
identity is persistent and versioned; a version history where every entry is
new is not a version history. Retraining is therefore an explicit act
(`--refresh`), recorded with a digest, and the runtime only ever reads the
pointer.

**It degrades to synthetic rather than to nothing.** With no snapshot the
models still fit, on the tape they always used, and `source` says SIMULATION
all the way through to the UI.

    python -m ml.training.dataset --refresh --asset BTC --samples 2000
    python -m ml.training.dataset --show
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

# Shared with the fitted artifacts so one volume holds everything a cold
# container needs to answer without retraining.
DATA_DIR = Path(os.getenv("IRIS_MODEL_DIR", "/app/var/models"))
POINTER = "training-current.json"

# Enough samples for `build_dataset` to produce a usable set after it consumes
# `window` points of history per row. Below this the snapshot is refused rather
# than written short — a model fitted on 40 samples has a model_hash and a
# version number and no information.
MIN_SAMPLES = 300


@dataclass(frozen=True)
class Snapshot:
    """A frozen training series and everything needed to account for it."""

    series: np.ndarray
    asset: str
    source: str
    provider: Optional[str]
    digest: str
    samples: int
    first_at: Optional[str]
    last_at: Optional[str]
    created_at: str

    @property
    def is_real(self) -> bool:
        return self.source == "LIVE"

    @property
    def return_sd_bps(self) -> Optional[float]:
        """
        The one-step return scale, in basis points.

        The number that made the whole scale mismatch visible: the synthetic
        tape sits near 60, one-minute BTC near 3.4. Carried on the snapshot so
        a reader can tell at a glance which kind of series a model was fitted
        on, without loading the series.
        """
        if self.series.size < 2:
            return None
        returns = np.diff(self.series) / self.series[:-1]
        return round(float(np.std(returns)) * 10_000, 4)

    def describe(self) -> str:
        span = ""
        if self.first_at and self.last_at:
            span = f", {self.first_at[:16]} to {self.last_at[:16]}"
        venue = self.provider or "synthetic"
        return (
            f"{self.asset} {self.source} via {venue}: "
            f"{self.samples} samples{span} [{self.digest}]"
        )

    def meta(self) -> dict:
        return {
            "asset": self.asset,
            "source": self.source,
            "provider": self.provider,
            "digest": self.digest,
            "samples": self.samples,
            "first_at": self.first_at,
            "last_at": self.last_at,
            "created_at": self.created_at,
        }


def digest_of(series: np.ndarray, asset: str, source: str, provider: Optional[str]) -> str:
    """
    A short, stable identity for a training series.

    Rounded before hashing: the same prices read back through psycopg, numpy
    and a npz round trip must produce the same key, or the artifact cache
    misses on every boot and the models retrain forever.
    """
    body = np.round(np.asarray(series, dtype=np.float64), 8).tobytes()
    head = f"{asset}|{source}|{provider or '-'}|{len(series)}".encode("utf-8")
    return hashlib.sha256(head + body).hexdigest()[:16]


def _pointer_path() -> Path:
    return DATA_DIR / POINTER


def _snapshot_path(digest: str) -> Path:
    return DATA_DIR / f"training-{digest}.npz"


# ─────────────────────────────────────────────────────────────────────────────
# Building
# ─────────────────────────────────────────────────────────────────────────────

def build(conn, *, asset: str = "BTC", samples: int = 2000,
          source: str = "LIVE") -> Snapshot:
    """
    Read the most recent `samples` observations for `asset` out of the feed.

    One source and one venue, for the reason in `agents.evaluation.prices`: a
    series spliced across two price universes has a discontinuity in it, and a
    model fitted on that learns the splice.
    """
    rows = conn.execute(
        """
        select (payload->>'price')::float8, occurred_at, provider
          from market_events
         where asset = %s and kind = 'PRICE' and source = %s
         order by occurred_at desc
         limit %s
        """,
        (asset, source, samples),
    ).fetchall()

    if len(rows) < MIN_SAMPLES:
        raise ValueError(
            f"{asset} has {len(rows)} {source} observation(s); "
            f"at least {MIN_SAMPLES} are needed to fit a model. "
            f"Run: python -m agents.market.ingest --asset {asset} --minutes 2880"
        )

    rows.reverse()  # oldest first

    # The dominant venue wins the whole snapshot, and any stragglers from a
    # failover are dropped rather than blended in.
    venues = [r[2] for r in rows if r[2]]
    provider = max(set(venues), key=venues.count) if venues else None
    if provider is not None:
        rows = [r for r in rows if r[2] == provider]

    series = np.asarray([float(r[0]) for r in rows], dtype=np.float64)
    return Snapshot(
        series=series,
        asset=asset,
        source=source,
        provider=provider,
        digest=digest_of(series, asset, source, provider),
        samples=int(series.size),
        first_at=rows[0][1].isoformat(),
        last_at=rows[-1][1].isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def save(snapshot: Snapshot) -> Path:
    """Write the snapshot and repoint `training-current.json` at it."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _snapshot_path(snapshot.digest)
    np.savez_compressed(path, series=snapshot.series)

    pointer = _pointer_path()
    tmp = pointer.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot.meta(), indent=2), encoding="utf-8")
    os.replace(tmp, pointer)  # atomic: a concurrent reader never sees a half file
    return path


def current() -> Optional[Snapshot]:
    """
    The snapshot the models are currently fitted on, or None.

    Any failure reads as "no snapshot" and the caller falls back to the
    synthetic tape. A half-written pointer or a missing npz must not take the
    protocol down, and must not silently load a series that does not match its
    recorded digest — which is checked here, because an artifact cache keyed by
    a digest that no longer describes the data is worse than no cache.
    """
    pointer = _pointer_path()
    if not pointer.exists():
        return None
    try:
        meta = json.loads(pointer.read_text(encoding="utf-8"))
        path = _snapshot_path(meta["digest"])
        with np.load(path) as archive:
            series = np.asarray(archive["series"], dtype=np.float64)
    except Exception:
        return None

    recomputed = digest_of(series, meta["asset"], meta["source"], meta.get("provider"))
    if recomputed != meta["digest"]:
        return None

    return Snapshot(
        series=series,
        asset=meta["asset"],
        source=meta["source"],
        provider=meta.get("provider"),
        digest=meta["digest"],
        samples=int(series.size),
        first_at=meta.get("first_at"),
        last_at=meta.get("last_at"),
        created_at=meta.get("created_at", ""),
    )


def record(conn, snapshot: Snapshot) -> bool:
    """
    Write the snapshot's identity to `training_snapshots`.

    The series stays on disk; only what it *is* goes to the database. That is
    what lets a process which did not fit the models still report honestly on
    them — the API on a small instance, say, while the scheduled cycle does the
    fitting somewhere else. Without it that API answers "no training snapshot"
    and the §0c banner calls real models synthetic.

    Idempotent on the digest, because re-freezing an identical series is not a
    new fact. Returns whether a row was inserted.
    """
    row = conn.execute(
        """
        insert into training_snapshots
            (digest, asset, source, provider, samples, first_at, last_at,
             return_sd_bps)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (digest) do nothing
        returning digest
        """,
        (snapshot.digest, snapshot.asset, snapshot.source, snapshot.provider,
         snapshot.samples, snapshot.first_at, snapshot.last_at,
         snapshot.return_sd_bps),
    ).fetchone()
    return row is not None


@dataclass(frozen=True)
class RecordedSnapshot:
    """
    A snapshot as the database knows it — identity without the series.

    Deliberately not a `Snapshot`: it cannot be fitted on, and a type that
    could be mistaken for one would invite exactly that.
    """

    digest: str
    asset: str
    source: str
    provider: Optional[str]
    samples: int
    first_at: Optional[str]
    last_at: Optional[str]
    return_sd_bps: Optional[float]
    created_at: str

    @property
    def is_real(self) -> bool:
        return self.source == "LIVE"

    def describe(self) -> str:
        span = ""
        if self.first_at and self.last_at:
            span = f", {self.first_at[:16]} to {self.last_at[:16]}"
        venue = self.provider or "synthetic"
        return (
            f"{self.asset} {self.source} via {venue}: "
            f"{self.samples} samples{span} [{self.digest}]"
        )


def latest_recorded(conn) -> Optional[RecordedSnapshot]:
    """The most recently frozen snapshot, as recorded in the database."""
    try:
        row = conn.execute(
            """select digest, asset, source, provider, samples, first_at,
                      last_at, return_sd_bps, created_at
                 from training_snapshots
                order by created_at desc limit 1"""
        ).fetchone()
    except Exception:  # noqa: BLE001 - before migration 0006, or no table
        return None
    if row is None:
        return None
    return RecordedSnapshot(
        digest=row[0], asset=row[1], source=row[2], provider=row[3],
        samples=int(row[4]),
        first_at=row[5].isoformat() if row[5] else None,
        last_at=row[6].isoformat() if row[6] else None,
        return_sd_bps=float(row[7]) if row[7] is not None else None,
        created_at=row[8].isoformat() if row[8] else "",
    )


def refresh(*, asset: str = "BTC", samples: int = 2000, source: str = "LIVE",
            dsn: Optional[str] = None) -> Snapshot:
    """Pull a fresh series from the feed, freeze it, and point the models at it."""
    from agents.runtime.persistence import connection

    with connection(dsn) as conn:
        snapshot = build(conn, asset=asset, samples=samples, source=source)
        save(snapshot)
        # Recorded inside the same transaction as the read that produced it, so
        # a snapshot cannot be announced in the database without the file that
        # backs it having been written first.
        record(conn, snapshot)
    return snapshot


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the model training set.")
    parser.add_argument("--refresh", action="store_true",
                        help="rebuild the snapshot from the feed")
    parser.add_argument("--show", action="store_true",
                        help="describe the current snapshot")
    parser.add_argument("--asset", default="BTC")
    parser.add_argument("--samples", type=int, default=2000)
    parser.add_argument("--source", default="LIVE",
                        choices=("LIVE", "TESTNET", "SIMULATION"))
    parser.add_argument("--dsn", default=None)
    args = parser.parse_args(argv)

    if args.refresh:
        snapshot = refresh(
            asset=args.asset, samples=args.samples, source=args.source, dsn=args.dsn
        )
        returns = np.diff(snapshot.series) / snapshot.series[:-1]
        print(f"snapshot   {snapshot.describe()}")
        print(f"1-step return sd  {float(np.std(returns)) * 10_000:.2f}bps")
        print("Models refit on next use — their model_hash changes with the data.")
        return 0

    snapshot = current()
    if snapshot is None:
        print("no snapshot; models fall back to the synthetic tape (SIMULATION)")
        return 1

    returns = np.diff(snapshot.series) / snapshot.series[:-1]
    print(f"snapshot   {snapshot.describe()}")
    print(f"created    {snapshot.created_at}")
    print(f"prices     {snapshot.series.min():,.2f} to {snapshot.series.max():,.2f}")
    print(f"1-step return sd  {float(np.std(returns)) * 10_000:.2f}bps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
