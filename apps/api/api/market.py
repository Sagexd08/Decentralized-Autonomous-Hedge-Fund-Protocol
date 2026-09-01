"""
Market data, and an honest account of where it came from — Phase 13.

Section 0c is the reason this router exists in the shape it does. The protocol
now runs on real exchange data, which means for the first time the UI could
legitimately say "live" — and the moment that becomes possible, saying it
wrongly becomes possible too. A feed that stopped two hours ago still returns
rows; a database with a stale simulated tape still returns rows; a model
trained on a synthetic series still returns confident predictions.

So every endpoint here answers with the evidence for its own claim: which
venue, how many observations, how old the newest one is, what fraction of the
window is actually covered, and what the models were fitted on. `/health`
reports `healthy: false` with a reason rather than an empty body, because the
failure mode this guards against is a green dashboard over a dead feed.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import psycopg
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_LIMIT = 1000

# Mirrored from `ml.inference.artifacts` rather than imported, because that
# module pulls in torch. `tests/unit/test_training_contract.py` asserts they
# stay equal — the same tie-by-test used between the training horizon and the
# decision horizon, and for the same reason: the honest alternative to an
# import that costs half a gigabyte is a test that fails when they drift.
CONTRACT_VERSION = 7
TRAINING_HORIZON_STEPS = 10

_SYNTHETIC_NOTE = (
    "No training snapshot; models fall back to a synthetic tape — not a real market"
)

# The venue comparison calls three exchanges. Cached briefly so a dashboard
# polling this endpoint cannot turn into a rate-limit ban.
_DIVERGENCE_TTL = 30.0
_divergence_cache: dict[str, tuple[float, dict]] = {}


def _dsn() -> str:
    from agents.runtime.persistence import dsn

    return dsn()


def _connect() -> psycopg.Connection:
    try:
        return psycopg.connect(_dsn())
    except Exception as exc:  # noqa: BLE001
        # Surfaced as a 503, never as an empty result set. An empty list of
        # prices and a database outage must not look the same to a caller.
        raise HTTPException(
            status_code=503, detail=f"market data is unavailable: {exc}"
        ) from exc


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else None


@router.get("/prices")
def prices(
    asset: str = Query("BTC"),
    limit: int = Query(120, ge=1, le=MAX_LIMIT),
    source: Optional[str] = Query(None, pattern="^(LIVE|TESTNET|SIMULATION)$"),
) -> dict:
    """
    The recent tape for one asset, oldest first.

    Restricted to a single source — the strongest available unless pinned. A
    series that splices a synthetic tape onto a real one contains a step of
    several orders of magnitude, and any chart or feature computed over it is a
    description of the splice rather than of the market.
    """
    from agents.evaluation.prices import latest_window

    asset = asset.upper()
    with _connect() as conn:
        window = latest_window(conn, asset=asset, size=limit, source=source)

    if not window:
        return {
            "asset": asset,
            "observations": [],
            "count": 0,
            "provenance": _provenance([], note=f"no price data recorded for {asset}"),
        }

    sources = sorted({o.source for o in window})
    venues = sorted({o.provider for o in window if o.provider})
    return {
        "asset": asset,
        "count": len(window),
        "source": window[-1].source,
        "provider": window[-1].provider,
        "first_at": _iso(window[0].at),
        "last_at": _iso(window[-1].at),
        "observations": [
            {"at": _iso(o.at), "price": o.price, "source": o.source,
             "provider": o.provider}
            for o in window
        ],
        "provenance": _provenance(sources, venues=venues),
    }


@router.get("/health")
def health(asset: str = Query("BTC")) -> dict:
    """
    Is the feed actually alive, and is what it holds usable?

    Liveness and usability are different questions and both are answered.
    A poller that is running and writing is not enough if the tape it has
    built covers a tenth of the window an agent needs.
    """
    from agents.market.ingest import feed_status, live_coverage
    from services.market_feed import feed

    asset = asset.upper()
    with _connect() as conn:
        rows = feed_status(conn, assets=[asset])
        coverage = live_coverage(conn, asset=asset, minutes=240)

    live_rows = [r for r in rows if r["source"] == "LIVE"]
    newest = min((r["lag_seconds"] for r in live_rows
                  if r["lag_seconds"] is not None), default=None)

    reasons: list[str] = []
    if not live_rows:
        reasons.append(f"no LIVE observations recorded for {asset}")
    if newest is not None and newest > 300:
        reasons.append(f"newest LIVE observation is {newest}s old")
    if coverage["coverage"] < 0.5:
        reasons.append(
            f"only {coverage['coverage']:.0%} of the last 4h is covered "
            f"({coverage['distinct_minutes']}/{coverage['expected_minutes']} minutes)"
        )

    # A poller that is switched off is not a broken feed.
    #
    # This asked whether *this process* is polling, and reported the feed
    # unhealthy when it was not. That was right while the API was the only
    # thing ingesting. In a split deployment — a sleeping free instance with
    # the scheduled cycle doing the ingest — it is wrong: the tape can be
    # perfectly fresh while nothing in this process has ever polled, and the
    # health check would call it unhealthy, which pushes the §0c banner to
    # "simulated" over genuinely live data.
    #
    # Health is a property of the *data*: how old the newest observation is and
    # how much of the window is covered, both checked above. The poller only
    # earns a reason when it is supposed to be running and is not.
    poller = feed.status()
    if poller.get("enabled", True) and not poller["running"]:
        reasons.append("the live feed poller is enabled but not running")
    if poller["last_error"]:
        reasons.append(f"last poll error: {poller['last_error']}")

    return {
        "asset": asset,
        "healthy": not reasons,
        # Named, never a bare boolean. "unhealthy" that does not say why sends
        # whoever reads it to the logs, which is where this information was
        # already sitting unread.
        "reasons": reasons,
        "lag_seconds": newest,
        "coverage": coverage,
        "sources": [
            {**r, "first_seen": _iso(r["first_seen"]), "last_seen": _iso(r["last_seen"])}
            for r in rows
        ],
        "poller": poller,
    }


@router.get("/venues")
def venues(asset: str = Query("BTC")) -> dict:
    """
    What each exchange says the asset is worth right now, and the spread.

    Not used to choose a price. It exists so the cost of the one-venue-per-tape
    rule is a measured number: if two venues sit 40bps apart, a settlement that
    silently crossed between them would have credited 40bps of venue spread to
    an agent's judgement.
    """
    from agents.market.providers import divergence

    asset = asset.upper()
    cached = _divergence_cache.get(asset)
    now = time.monotonic()
    if cached and now - cached[0] < _DIVERGENCE_TTL:
        return cached[1]

    result = divergence(asset)
    payload = {
        "asset": asset,
        "quotes": result["quotes"],
        "median": result["median"],
        "spread_bps": result["spread_bps"],
        "unavailable": result["failures"],
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Independent quotes from public venues. A tape never mixes them — "
            "see agents/market/providers.py."
        ),
    }
    _divergence_cache[asset] = (now, payload)
    return payload


@router.get("/training")
def training() -> dict:
    """
    What the models were actually fitted on.

    The single most load-bearing honesty endpoint in the protocol. An agent
    reading a live tape through a model trained on a synthetic one produces
    predictions that are real in provenance and nonsense in magnitude — the
    first live run predicted a 2.6-sigma move with 88% confidence and would
    have done so every run. Nothing in the prediction, the hash, the settlement
    or the score reveals it. This does.
    """
    # The database first, then local disk.
    #
    # `ml.training.dataset` reads a pointer file next to the fitted artifacts,
    # which is correct when one machine both fits and serves. It is wrong the
    # moment they are different machines: the scheduled cycle fits the models
    # and holds the snapshot, the API serves the dashboard and has never seen
    # it, so the API would report "no training snapshot" — and the §0c banner
    # would say "synthetic models" over models fitted on real market data.
    #
    # So `refresh()` records the snapshot's identity in `training_snapshots`,
    # and this reads that. The local file remains the fallback for a
    # single-machine setup and for the case where the table is empty.
    from ml.training.dataset import current, latest_recorded

    snapshot = None
    with _connect() as conn:
        recorded = latest_recorded(conn)
    if recorded is None:
        snapshot = current()

    described = recorded or snapshot
    body: dict[str, Any] = {
        "description": described.describe() if described else _SYNTHETIC_NOTE,
        "samples": described.samples if described else 0,
        "contract_version": CONTRACT_VERSION,
        "horizon_steps": TRAINING_HORIZON_STEPS,
        "cache_key": described.digest if described else "synthetic",
        "is_real_market_data": described is not None and described.is_real,
        # Which of the two answered, so a split deployment is diagnosable
        # rather than merely correct.
        "source_of_record": "database" if recorded else
                            ("local" if snapshot else "none"),
    }

    if described is not None:
        body.update(
            {
                "asset": described.asset,
                "source": described.source,
                "provider": described.provider,
                "digest": described.digest,
                "first_at": described.first_at,
                "last_at": described.last_at,
                "frozen_at": described.created_at,
                "return_sd_bps": described.return_sd_bps,
            }
        )
    else:
        body.update(
            {
                "asset": None,
                "source": "SIMULATION",
                "provider": None,
                "warning": (
                    "No training snapshot. Models are fitted on a synthetic "
                    "Ornstein-Uhlenbeck tape whose returns are roughly sixty "
                    "times larger than a real market's; predictions made from "
                    "them on live prices are systematically overstated. Run: "
                    "make train"
                ),
            }
        )

    body["provenance"] = _provenance(
        [body.get("source") or "SIMULATION"],
        venues=[snapshot.provider] if snapshot and snapshot.provider else [],
    )
    return body


@router.get("/summary")
def summary() -> dict:
    """One call for the header strip: feed, training set and venue spread."""
    from services.market_feed import feed

    assets = feed.status()["assets"] or ["BTC"]
    return {
        "assets": [health(asset=a) for a in assets],
        "training": training(),
        "poller": feed.status(),
    }


def _provenance(sources: list[str], *, venues: Optional[list[str]] = None,
                note: str = "") -> dict:
    """
    The same pessimistic rule the protocol router uses: the weakest source wins.

    A response mixing one live row into forty simulated ones is not live, and
    reporting the strongest would let a single real number launder a screen
    full of synthetic ones.
    """
    clean = sorted({s for s in sources if s})
    live = bool(clean) and clean == ["LIVE"]

    if note:
        message = note
    elif live and venues:
        message = (
            f"Real market data from {', '.join(venues)}. Historical bars are "
            f"stamped at the close of the minute they describe."
        )
    elif live:
        message = "Real market data from a public exchange."
    elif clean == ["SIMULATION"] or not clean:
        message = (
            "Simulated market data. Not evidence of live performance."
        )
    else:
        message = (
            f"Mixed provenance ({', '.join(clean)}); treated as the weakest."
        )

    return {"sources": clean or ["SIMULATION"], "live": live,
            "venues": venues or [], "note": message}
