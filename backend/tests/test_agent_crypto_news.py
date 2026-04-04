import pytest

from agents.crypto_news import CryptoNewsService

def test_extract_coins_detects_symbols():
    service = CryptoNewsService()
    coins = service._extract_coins("BTC and ETH rally while SOL consolidates")
    assert "BTC" in coins
    assert "ETH" in coins
    assert "SOL" in coins

def test_derive_sentiment_paths():
    service = CryptoNewsService()
    assert service._derive_sentiment("Bitcoin rally as bulls gain") == "bullish"
    assert service._derive_sentiment("Exchange hack sparks liquidation fears") == "bearish"
    assert service._derive_sentiment("Market commentary across major tokens") == "neutral"

@pytest.mark.asyncio
async def test_get_latest_news_falls_back_when_sources_fail(monkeypatch):
    service = CryptoNewsService()

    async def no_items(*args, **kwargs):
        return []

    monkeypatch.setattr(service, "_fetch_from_gdelt", no_items)
    monkeypatch.setattr(service, "_fetch_from_apify", no_items)
    monkeypatch.setattr(service, "_fetch_from_news_api", no_items)

    items = await service.get_latest_news(force_refresh=True, limit=2)
    assert len(items) == 2
    assert all(item["provider"] == "fallback" for item in items)

@pytest.mark.asyncio
async def test_get_agent_signals_maps_news_to_signal(monkeypatch):
    service = CryptoNewsService()

    async def fake_news(*args, **kwargs):
        return [
            {
                "title": "BTC rally continues on institutional flows",
                "coins": ["BTC"],
                "sentiment_hint": "bullish",
                "source": "test-source",
                "provider": "test-provider",
            }
        ]

    monkeypatch.setattr(service, "get_latest_news", fake_news)

    signals = await service.get_agent_signals(force_refresh=True, limit=1)
    assert len(signals) == 1
    assert signals[0]["asset"] == "BTC"
    assert signals[0]["sentiment"] > 0
    assert signals[0]["provider"] == "test-provider"
