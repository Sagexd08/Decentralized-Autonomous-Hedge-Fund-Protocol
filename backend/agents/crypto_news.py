import asyncio
import logging
import time
from typing import Any

import aiohttp

from core.settings import settings

logger = logging.getLogger(__name__)

class CryptoNewsService:
    def __init__(self):
        self._cache: list[dict[str, Any]] = []
        self._last_fetch: float = 0.0
        self._ttl_seconds = 180

    async def get_agent_signals(self, force_refresh: bool = False, limit: int = 10) -> list[dict[str, Any]]:
        articles = await self.get_latest_news(force_refresh=force_refresh, limit=limit)
        signals = []
        for item in articles:
            asset = (item.get("coins") or ["BTC"])[0]
            sentiment_score = self._sentiment_to_score(item.get("sentiment_hint", "neutral"))
            signals.append({
                "asset": asset,
                "sentiment": sentiment_score,
                "event": self._infer_event(item.get("title", "")),
                "confidence": self._infer_confidence(item),
                "source": item.get("source", "unknown"),
                "provider": item.get("provider", "unknown"),
                "title": item.get("title", ""),
            })
        return signals

    async def get_latest_news(self, force_refresh: bool = False, limit: int = 20) -> list[dict[str, Any]]:
        now = time.time()
        if not force_refresh and self._cache and (now - self._last_fetch) < self._ttl_seconds:
            return self._cache[:limit]

        items = await self._fetch_from_gdelt()
        if not items:
            items = await self._fetch_from_apify()
        if not items:
            items = await self._fetch_from_news_api()
        if not items:
            items = self._fallback_items()

        self._cache = items
        self._last_fetch = now
        return items[:limit]

    async def _fetch_from_gdelt(self) -> list[dict[str, Any]]:
        url = settings.gdelt_api_url
        if not url:
            return []
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return []
                    payload = await response.json(content_type=None)
                    articles = payload.get("articles", [])
                    return [self._normalize_gdelt_item(article) for article in articles if article.get("title")]
        except Exception as exc:
            logger.warning(f"GDELT fetch failed: {exc}")
            return []

    async def _fetch_from_apify(self) -> list[dict[str, Any]]:
        if not settings.apify_api_token:
            return []
        try:
            from apify_client import ApifyClient
        except Exception as exc:
            logger.warning(f"Apify client unavailable: {exc}")
            return []

        try:
            def run_actor() -> list[dict[str, Any]]:
                client = ApifyClient(settings.apify_api_token)
                run_input = {
                    "category": "top-news",
                    "filter": "show-all",
                }
                run = client.actor(settings.apify_cryptopanic_actor_id).call(run_input=run_input)
                dataset = client.dataset(run["defaultDatasetId"])
                return [self._normalize_apify_item(item) for item in dataset.iterate_items()]

            items = await asyncio.to_thread(run_actor)
            return [item for item in items if item]
        except Exception as exc:
            logger.warning(f"Apify crypto news fetch failed: {exc}")
            return []

    async def _fetch_from_news_api(self) -> list[dict[str, Any]]:
        if not settings.news_api_key:
            return []

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": "crypto OR bitcoin OR ethereum OR zksync OR solana defi",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "apiKey": settings.news_api_key,
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return []
                    payload = await response.json(content_type=None)
                    articles = payload.get("articles", [])
                    return [self._normalize_news_api_item(article) for article in articles if article.get("title")]
        except Exception as exc:
            logger.warning(f"News API fetch failed: {exc}")
            return []

    def _normalize_apify_item(self, item: dict[str, Any]) -> dict[str, Any]:
        title = item.get("title")
        if not title:
            return {}
        return {
            "title": title,
            "published": item.get("date", "unknown"),
            "coins": item.get("coins", []),
            "votes": item.get("votes", []),
            "source": item.get("source", "cryptopanic"),
            "provider": "apify",
            "sentiment_hint": self._derive_sentiment(title),
        }

    def _normalize_gdelt_item(self, item: dict[str, Any]) -> dict[str, Any]:
        title = item.get("title")
        if not title:
            return {}
        return {
            "title": title,
            "published": item.get("seendate", item.get("socialimage", "unknown")),
            "coins": self._extract_coins(title + " " + (item.get("domain", "") or "")),
            "votes": [],
            "source": item.get("domain", "gdelt"),
            "provider": "gdelt",
            "sentiment_hint": self._derive_sentiment(title),
        }

    def _normalize_news_api_item(self, item: dict[str, Any]) -> dict[str, Any]:
        title = item.get("title")
        if not title:
            return {}
        return {
            "title": title,
            "published": item.get("publishedAt", "unknown"),
            "coins": self._extract_coins(title + " " + (item.get("description") or "")),
            "votes": [],
            "source": (item.get("source") or {}).get("name", "newsapi"),
            "provider": "newsapi",
            "sentiment_hint": self._derive_sentiment(title),
        }

    def _extract_coins(self, text: str) -> list[str]:
        upper = text.upper()
        coins = []
        for symbol in ["BTC", "ETH", "SOL", "USDC", "LINK", "AAVE", "UNI", "ZK"]:
            if symbol in upper:
                coins.append(symbol)
        return coins

    def _derive_sentiment(self, title: str) -> str:
        lower = title.lower()
        if any(word in lower for word in ["surge", "gain", "bull", "rally", "up"]):
            return "bullish"
        if any(word in lower for word in ["hack", "drop", "liquidation", "retreat", "down"]):
            return "bearish"
        return "neutral"

    def _sentiment_to_score(self, sentiment: str) -> float:
        if sentiment == "bullish":
            return 0.72
        if sentiment == "bearish":
            return -0.72
        return 0.05

    def _infer_event(self, title: str) -> str:
        lower = title.lower()
        if "regulation" in lower and any(word in lower for word in ["ease", "easing", "approve", "greenlight"]):
            return "regulation easing"
        if any(word in lower for word in ["hack", "exploit", "breach"]):
            return "security incident"
        if any(word in lower for word in ["etf", "institutional", "flows"]):
            return "institutional flows"
        if any(word in lower for word in ["liquidation", "leverage"]):
            return "liquidation stress"
        return "market narrative"

    def _infer_confidence(self, item: dict[str, Any]) -> float:
        provider = item.get("provider", "")
        if provider == "gdelt":
            return 0.85
        if provider == "apify":
            return 0.8
        if provider == "newsapi":
            return 0.7
        return 0.55

    def _fallback_items(self) -> list[dict[str, Any]]:
        return [
            {
                "title": "Bitcoin liquidity clusters tighten as macro volatility rises",
                "published": "just now",
                "coins": ["BTC", "ETH"],
                "votes": [],
                "source": "fallback",
                "provider": "fallback",
                "sentiment_hint": "neutral",
            },
            {
                "title": "Solana and zkSync flows accelerate as traders rotate into faster rails",
                "published": "just now",
                "coins": ["SOL", "ZK"],
                "votes": [],
                "source": "fallback",
                "provider": "fallback",
                "sentiment_hint": "bullish",
            },
        ]

crypto_news_service = CryptoNewsService()
