"""
Where a real price comes from — IRIS_BUILD_PROMPT v2.0 section 13, Phase 13.

Three public venues, one interface. Binance, Coinbase and Kraken all publish
unauthenticated spot data, so this package needs no credentials at all — which
matters beyond convenience: section 0 forbids keys in source, and the cheapest
way to guarantee that is for the code to have nothing to hold.

Two decisions here are load-bearing and would be easy to get quietly wrong.

**A candle is stamped at its close, not its open.** Every venue keys a
one-minute bar by the minute it opened, and the natural thing to do is write
`(open_time, close_price)`. That is wrong by exactly one bar: the close price
is what the asset traded at sixty seconds *after* the timestamp it would be
filed under. Settlement then measures every return against prices stamped a
minute early, in the same direction, for every prediction — a systematic bias
that never looks like a bug because the series still moves plausibly.

**A tape stays on one venue.** BTCUSDT on Binance, BTC-USD on Coinbase and
XBTUSD on Kraken are three different instruments that happen to track the same
asset; they differ by a few basis points at any instant, and Binance's leg is
quoted in a stablecoin rather than dollars. Settling a prediction with an
entry from one and an exit from another measures the spread between two venues
and files it as the agent's skill. So `provider` is recorded on every row, the
ingest prefers one venue per asset, and `divergence` exists to make the size of
that spread observable instead of assumed.
"""

from __future__ import annotations

import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Optional, Sequence

USER_AGENT = "iris-protocol/2.0 (market-data ingest)"
TIMEOUT_SECONDS = 20.0
RETRIES = 3
RETRY_BACKOFF = 1.5

# The assets the protocol trades. An asset absent from a venue's map is simply
# not available there; `candles` raises rather than guessing a ticker.
ASSETS = ("BTC", "ETH", "SOL")


class MarketDataError(RuntimeError):
    """A venue could not be read. Never a substitute for a price."""


@dataclass(frozen=True)
class Candle:
    """One completed bar. `at` is the instant `close` was the price."""

    at: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def as_payload(self) -> dict:
        return {
            "price": self.close,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass(frozen=True)
class Quote:
    at: datetime
    price: float


def _utc(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get(url: str) -> object:
    """
    One GET, decoded as JSON, retried on transient failure.

    Retries are bounded and backed off rather than infinite. A venue that is
    down should surface as a `MarketDataError` the caller can fail over from —
    a loop that keeps trying is a feed that reports neither data nor an
    outage.
    """
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - re-raised as MarketDataError below
            last = exc
            if attempt < RETRIES - 1:
                time.sleep(RETRY_BACKOFF ** attempt)
    raise MarketDataError(f"{url}: {last}") from last


@dataclass(frozen=True)
class Provider:
    """
    A venue, reduced to the two questions the protocol asks it.

    `candles` backfills history; `quote` reads the current price. Both return
    real observations or raise — neither ever falls back to a synthetic value,
    because a synthetic value returned from something called a provider is
    exactly how simulated data ends up labelled LIVE.
    """

    name: str
    symbols: dict[str, str]
    _candles: Callable[[str, int, Optional[datetime]], list[Candle]]
    _quote: Callable[[str], Quote]

    def symbol_for(self, asset: str) -> str:
        symbol = self.symbols.get(asset.upper())
        if symbol is None:
            raise MarketDataError(f"{self.name} does not quote {asset}")
        return symbol

    def supports(self, asset: str) -> bool:
        return asset.upper() in self.symbols

    def candles(
        self, asset: str, *, minutes: int = 240, end: Optional[datetime] = None
    ) -> list[Candle]:
        """The last `minutes` one-minute bars, oldest first, close-stamped."""
        bars = self._candles(self.symbol_for(asset), minutes, end)
        bars.sort(key=lambda c: c.at)
        return bars

    def quote(self, asset: str) -> Quote:
        return self._quote(self.symbol_for(asset))


# ─────────────────────────────────────────────────────────────────────────────
# Binance
# ─────────────────────────────────────────────────────────────────────────────

BINANCE_BASE = "https://api.binance.com/api/v3"
BINANCE_PAGE = 1000


def _binance_candles(
    symbol: str, minutes: int, end: Optional[datetime]
) -> list[Candle]:
    finish = end or utcnow()
    start = finish - timedelta(minutes=minutes)
    out: list[Candle] = []
    cursor = start

    while cursor < finish:
        params = urllib.parse.urlencode(
            {
                "symbol": symbol,
                "interval": "1m",
                "startTime": int(cursor.timestamp() * 1000),
                "endTime": int(finish.timestamp() * 1000),
                "limit": BINANCE_PAGE,
            }
        )
        page = _get(f"{BINANCE_BASE}/klines?{params}")
        if not isinstance(page, list) or not page:
            break
        for row in page:
            # [open_time, open, high, low, close, volume, close_time, ...]
            #
            # Stamped at open + 60s, not at the venue's own `close_time`.
            # Binance reports the close as openTime + 59_999ms, which is
            # accurate about its last trade and one millisecond short of the
            # minute boundary — enough for the same bar to land on a different
            # key than Coinbase's or Kraken's, which would defeat the
            # deduplication index and make two venues' tapes impossible to
            # compare. The boundary is the same instant for everyone.
            out.append(
                Candle(
                    at=_utc(int(row[0]) / 1000.0 + 60),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        advanced = _utc(int(page[-1][6]) / 1000.0)
        if advanced <= cursor:
            break
        cursor = advanced
        if len(page) < BINANCE_PAGE:
            break

    return out


def _binance_quote(symbol: str) -> Quote:
    payload = _get(f"{BINANCE_BASE}/ticker/price?symbol={symbol}")
    if not isinstance(payload, dict) or "price" not in payload:
        raise MarketDataError(f"binance returned no price for {symbol}")
    return Quote(at=utcnow(), price=float(payload["price"]))


binance = Provider(
    name="binance",
    symbols={"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"},
    _candles=_binance_candles,
    _quote=_binance_quote,
)


# ─────────────────────────────────────────────────────────────────────────────
# Coinbase Exchange
# ─────────────────────────────────────────────────────────────────────────────

COINBASE_BASE = "https://api.exchange.coinbase.com"
COINBASE_PAGE = 300  # hard limit; the endpoint 400s on a wider range


def _coinbase_candles(
    symbol: str, minutes: int, end: Optional[datetime]
) -> list[Candle]:
    finish = end or utcnow()
    out: list[Candle] = []
    remaining = minutes

    while remaining > 0:
        span = min(remaining, COINBASE_PAGE)
        start = finish - timedelta(minutes=span)
        params = urllib.parse.urlencode(
            {
                "granularity": 60,
                "start": start.replace(microsecond=0).isoformat(),
                "end": finish.replace(microsecond=0).isoformat(),
            }
        )
        page = _get(f"{COINBASE_BASE}/products/{symbol}/candles?{params}")
        if not isinstance(page, list) or not page:
            break
        for row in page:
            # [time, low, high, open, close, volume]; `time` is the bar open.
            out.append(
                Candle(
                    at=_utc(int(row[0]) + 60),
                    open=float(row[3]),
                    high=float(row[2]),
                    low=float(row[1]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        finish = start
        remaining -= span
        time.sleep(0.25)  # the public endpoint is rate limited per IP

    return out


def _coinbase_quote(symbol: str) -> Quote:
    payload = _get(f"{COINBASE_BASE}/products/{symbol}/ticker")
    if not isinstance(payload, dict) or "price" not in payload:
        raise MarketDataError(f"coinbase returned no price for {symbol}")
    return Quote(at=utcnow(), price=float(payload["price"]))


coinbase = Provider(
    name="coinbase",
    symbols={"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"},
    _candles=_coinbase_candles,
    _quote=_coinbase_quote,
)


# ─────────────────────────────────────────────────────────────────────────────
# Kraken
# ─────────────────────────────────────────────────────────────────────────────

KRAKEN_BASE = "https://api.kraken.com/0/public"


def _kraken_result(payload: object, what: str) -> dict:
    if not isinstance(payload, dict):
        raise MarketDataError(f"kraken returned no object for {what}")
    errors = payload.get("error") or []
    if errors:
        raise MarketDataError(f"kraken: {', '.join(errors)}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise MarketDataError(f"kraken returned no result for {what}")
    return result


def _kraken_candles(symbol: str, minutes: int, end: Optional[datetime]) -> list[Candle]:
    finish = end or utcnow()
    since = int((finish - timedelta(minutes=minutes)).timestamp())
    result = _kraken_result(
        _get(f"{KRAKEN_BASE}/OHLC?pair={symbol}&interval=1&since={since}"), symbol
    )
    series = next((v for k, v in result.items() if k != "last"), None)
    if not isinstance(series, list):
        raise MarketDataError(f"kraken returned no series for {symbol}")

    out: list[Candle] = []
    for row in series:
        at = _utc(int(row[0]) + 60)  # bar open + one minute
        if at > finish:
            continue
        out.append(
            Candle(
                at=at,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[6]),
            )
        )
    return out


def _kraken_quote(symbol: str) -> Quote:
    result = _kraken_result(_get(f"{KRAKEN_BASE}/Ticker?pair={symbol}"), symbol)
    ticker = next(iter(result.values()), None)
    if not isinstance(ticker, dict) or "c" not in ticker:
        raise MarketDataError(f"kraken returned no price for {symbol}")
    return Quote(at=utcnow(), price=float(ticker["c"][0]))


kraken = Provider(
    name="kraken",
    symbols={"BTC": "XBTUSD", "ETH": "ETHUSD", "SOL": "SOLUSD"},
    _candles=_kraken_candles,
    _quote=_kraken_quote,
)


# ─────────────────────────────────────────────────────────────────────────────
# Selection
# ─────────────────────────────────────────────────────────────────────────────

ALL: tuple[Provider, ...] = (binance, coinbase, kraken)
_BY_NAME = {p.name: p for p in ALL}


def provider_by_name(name: str) -> Provider:
    try:
        return _BY_NAME[name.lower()]
    except KeyError:
        known = ", ".join(sorted(_BY_NAME))
        raise MarketDataError(f"unknown provider {name!r}; known: {known}") from None


def providers_for(asset: str, preferred: Optional[str] = None) -> list[Provider]:
    """
    The venues that quote `asset`, preferred one first.

    Order is the failover order, not a blend: the ingest takes the first that
    answers and records its name on every row it writes.
    """
    ordered = [p for p in ALL if p.supports(asset)]
    if preferred:
        first = provider_by_name(preferred)
        ordered = [first] + [p for p in ordered if p.name != first.name]
    return ordered


def default_provider(asset: str = "BTC", preferred: Optional[str] = None) -> Provider:
    options = providers_for(asset, preferred)
    if not options:
        raise MarketDataError(f"no configured venue quotes {asset}")
    return options[0]


def divergence(asset: str, sources: Iterable[Provider] = ALL) -> dict:
    """
    How far apart the venues are on `asset`, right now.

    Not used to pick a price — it exists so the cost of the single-venue rule
    above is a measured number rather than an assumption. If two venues sit 40
    bps apart, then a settlement that silently crossed between them attributed
    40 bps of venue spread to an agent's judgement.
    """
    quotes: dict[str, float] = {}
    failures: dict[str, str] = {}
    for provider in sources:
        if not provider.supports(asset):
            continue
        try:
            quotes[provider.name] = provider.quote(asset).price
        except MarketDataError as exc:
            failures[provider.name] = str(exc)

    if len(quotes) < 2:
        return {
            "asset": asset,
            "quotes": quotes,
            "failures": failures,
            "spread_bps": None,
            "median": next(iter(quotes.values()), None),
        }

    values: Sequence[float] = list(quotes.values())
    median = statistics.median(values)
    spread_bps = (max(values) - min(values)) / median * 10_000
    return {
        "asset": asset,
        "quotes": quotes,
        "failures": failures,
        "spread_bps": round(spread_bps, 2),
        "median": median,
    }
