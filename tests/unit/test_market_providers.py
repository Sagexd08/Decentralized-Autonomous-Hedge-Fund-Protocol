"""
Market data providers — Phase 13.

No network. Every venue is exercised against a captured response shape, so the
suite asserts what this code does with an answer rather than whether an
exchange happened to be up.

The tests are grouped by the mistake they exist to prevent. Two of those
mistakes produce a series that looks completely normal:

  * stamping a bar at its open, which files every close price one minute early
    and biases every settled return in the same direction, and
  * blending two venues into one tape, which files the spread between two
    instruments as an agent's judgement.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.market import providers  # noqa: E402
from agents.market.providers import (  # noqa: E402
    ALL,
    Candle,
    MarketDataError,
    Quote,
    binance,
    coinbase,
    default_provider,
    divergence,
    kraken,
    provider_by_name,
    providers_for,
)

# One real bar as each venue returns it. Open 100, close 110, over the minute
# beginning at 1_700_000_000 — so the close is the price at +60s.
OPEN_TS = 1_699_999_980  # on a minute boundary, as a real bar is
CLOSE_AT = datetime.fromtimestamp(OPEN_TS + 60, tz=timezone.utc)

BINANCE_ROW = [
    OPEN_TS * 1000, "100.0", "115.0", "95.0", "110.0", "12.5",
    (OPEN_TS + 60) * 1000 - 1, "0", 0, "0", "0", "0",
]
COINBASE_ROW = [OPEN_TS, 95.0, 115.0, 100.0, 110.0, 12.5]
KRAKEN_ROW = [OPEN_TS, "100.0", "115.0", "95.0", "110.0", "105.0", "12.5", 9]


@pytest.fixture
def no_sleep(monkeypatch):
    """Coinbase paces itself against a rate limit; the tests need not."""
    monkeypatch.setattr(providers.time, "sleep", lambda _s: None)


# ── the bar is stamped at its close ─────────────────────────────────────────

def test_binance_stamps_a_bar_at_its_close(monkeypatch):
    """
    The close price is what the asset traded at at the END of the minute.

    Every venue keys a bar by the minute it opened. Filing the close under the
    open time would put every price sixty seconds early, in the same direction,
    for every observation — and the series would still look entirely normal.
    """
    monkeypatch.setattr(providers, "_get", lambda url: [BINANCE_ROW])
    (candle,) = binance.candles("BTC", minutes=1)

    assert candle.close == 110.0
    assert candle.at == CLOSE_AT
    assert candle.at.second == 0
    # ...and specifically NOT the open time.
    assert candle.at != datetime.fromtimestamp(OPEN_TS, tz=timezone.utc)


def test_coinbase_stamps_a_bar_at_its_close(monkeypatch, no_sleep):
    monkeypatch.setattr(providers, "_get", lambda url: [COINBASE_ROW])
    candles = coinbase.candles("BTC", minutes=1)
    assert candles[0].at == CLOSE_AT
    assert candles[0].close == 110.0


def test_kraken_stamps_a_bar_at_its_close(monkeypatch):
    monkeypatch.setattr(
        providers, "_get",
        lambda url: {"error": [], "result": {"XXBTZUSD": [KRAKEN_ROW], "last": 0}},
    )
    candles = kraken.candles("BTC", minutes=1, end=CLOSE_AT + timedelta(minutes=5))
    assert candles[0].at == CLOSE_AT
    assert candles[0].close == 110.0


def test_every_venue_reads_the_same_bar_identically(monkeypatch, no_sleep):
    """
    Three venues, three wire formats, one Candle.

    Coinbase orders its row [time, low, high, open, close, volume] while
    Binance uses [time, open, high, low, close, ...]. Reading one with the
    other's field order silently swaps high and low.
    """
    monkeypatch.setattr(providers, "_get", lambda url: [BINANCE_ROW])
    a = binance.candles("BTC", minutes=1)[0]

    monkeypatch.setattr(providers, "_get", lambda url: [COINBASE_ROW])
    b = coinbase.candles("BTC", minutes=1)[0]

    monkeypatch.setattr(
        providers, "_get",
        lambda url: {"error": [], "result": {"XXBTZUSD": [KRAKEN_ROW]}},
    )
    c = kraken.candles("BTC", minutes=1, end=CLOSE_AT + timedelta(minutes=5))[0]

    for candle in (a, b, c):
        assert (candle.open, candle.high, candle.low, candle.close) == (
            100.0, 115.0, 95.0, 110.0
        )
        assert candle.at == CLOSE_AT


def test_candles_come_back_oldest_first(monkeypatch):
    """
    Coinbase returns newest-first. A window in the wrong order turns every
    return in it inside out, and `extract` would compute momentum backwards.
    """
    rows = [
        [OPEN_TS * 1000, "1", "1", "1", "1", "1", (OPEN_TS + 60) * 1000 - 1,
         "0", 0, "0", "0", "0"],
        [(OPEN_TS - 60) * 1000, "1", "1", "1", "1", "1", OPEN_TS * 1000 - 1,
         "0", 0, "0", "0", "0"],
    ]
    monkeypatch.setattr(providers, "_get", lambda url: rows)
    candles = binance.candles("BTC", minutes=5)
    assert [c.at for c in candles] == sorted(c.at for c in candles)


# ── symbols and support ─────────────────────────────────────────────────────

def test_each_venue_maps_the_asset_to_its_own_ticker():
    assert binance.symbol_for("BTC") == "BTCUSDT"
    assert coinbase.symbol_for("BTC") == "BTC-USD"
    assert kraken.symbol_for("BTC") == "XBTUSD"


def test_an_unquoted_asset_raises_rather_than_guessing():
    """
    Guessing a ticker is how a tape ends up holding the wrong instrument's
    prices under the right asset's name.
    """
    with pytest.raises(MarketDataError, match="does not quote"):
        binance.symbol_for("DOGECOIN-XYZ")
    assert not binance.supports("NOTATOKEN")


def test_asset_lookup_is_case_insensitive():
    assert binance.symbol_for("btc") == "BTCUSDT"
    assert binance.supports("btc")


# ── selection and failover ──────────────────────────────────────────────────

def test_preferred_venue_comes_first_and_the_rest_remain_as_failover():
    order = providers_for("BTC", preferred="kraken")
    assert order[0].name == "kraken"
    assert {p.name for p in order} == {p.name for p in ALL}
    # exactly once each — a duplicated venue would be tried twice on failover
    assert len(order) == len({p.name for p in order})


def test_default_venue_honours_the_preference():
    assert default_provider("BTC", preferred="coinbase").name == "coinbase"
    assert default_provider("BTC").name == ALL[0].name


def test_unknown_venue_names_the_ones_that_exist():
    with pytest.raises(MarketDataError, match="binance"):
        provider_by_name("nasdaq")


# ── transport ───────────────────────────────────────────────────────────────

def test_a_failing_venue_raises_rather_than_returning_a_price(monkeypatch):
    """
    The one behaviour that must never be softened. A provider that returns a
    fallback number on failure is how synthetic data acquires a venue's name.
    """
    monkeypatch.setattr(providers.time, "sleep", lambda _s: None)

    def boom(request, timeout):
        raise TimeoutError("connection reset")

    # Patched at the transport, so the wrapping in `_get` is what is tested
    # rather than bypassed.
    monkeypatch.setattr(providers.urllib.request, "urlopen", boom)
    with pytest.raises(MarketDataError):
        binance.candles("BTC", minutes=5)


def test_get_retries_then_gives_up(monkeypatch):
    calls = {"n": 0}

    def flaky(request, timeout):
        calls["n"] += 1
        raise OSError("nope")

    monkeypatch.setattr(providers.time, "sleep", lambda _s: None)
    monkeypatch.setattr(providers.urllib.request, "urlopen", flaky)

    with pytest.raises(MarketDataError):
        providers._get("https://example.invalid/x")
    assert calls["n"] == providers.RETRIES


def test_kraken_surfaces_its_error_envelope(monkeypatch):
    """Kraken answers 200 with an error list; a 200 is not a success."""
    monkeypatch.setattr(
        providers, "_get",
        lambda url: {"error": ["EQuery:Unknown asset pair"], "result": {}},
    )
    with pytest.raises(MarketDataError, match="Unknown asset pair"):
        kraken.quote("BTC")


# ── divergence ──────────────────────────────────────────────────────────────

def test_divergence_measures_the_spread_between_venues(monkeypatch):
    prices = {"binance": 100.0, "coinbase": 100.5, "kraken": 100.25}

    def quote(self, asset):
        return Quote(at=datetime.now(timezone.utc), price=prices[self.name])

    monkeypatch.setattr(providers.Provider, "quote", quote, raising=False)
    result = divergence("BTC")

    assert result["median"] == 100.25
    # (100.5 - 100.0) / 100.25 * 10_000
    assert result["spread_bps"] == pytest.approx(49.88, abs=0.05)
    assert set(result["quotes"]) == set(prices)


def test_divergence_records_a_venue_that_did_not_answer(monkeypatch):
    def quote(self, asset):
        if self.name == "kraken":
            raise MarketDataError("kraken down")
        return Quote(at=datetime.now(timezone.utc), price=100.0)

    monkeypatch.setattr(providers.Provider, "quote", quote, raising=False)
    result = divergence("BTC")

    assert "kraken" in result["failures"]
    assert "kraken" not in result["quotes"]
    # A silent drop would make two venues agreeing look like three.
    assert len(result["quotes"]) == 2


def test_divergence_with_one_venue_reports_no_spread(monkeypatch):
    """
    None, not zero. Zero spread is a claim that the venues agree; with one
    quote there is nothing to compare and saying so is the honest answer.
    """
    def quote(self, asset):
        if self.name != "binance":
            raise MarketDataError("down")
        return Quote(at=datetime.now(timezone.utc), price=100.0)

    monkeypatch.setattr(providers.Provider, "quote", quote, raising=False)
    assert divergence("BTC")["spread_bps"] is None


# ── payload ─────────────────────────────────────────────────────────────────

def test_candle_payload_keeps_the_full_bar_and_names_the_settlement_price():
    """
    `price` is what settlement reads; the OHLC stays alongside it so a chart
    or a later feature does not need a second round trip to the venue.
    """
    candle = Candle(at=CLOSE_AT, open=1.0, high=4.0, low=0.5, close=3.0, volume=9.0)
    payload = candle.as_payload()
    assert payload["price"] == payload["close"] == 3.0
    assert payload["high"] == 4.0 and payload["low"] == 0.5
