from fastapi import APIRouter, Query

from agents.crypto_news import crypto_news_service
from core.settings import settings

router = APIRouter()


@router.get("/crypto")
async def get_crypto_news(limit: int = Query(default=20, ge=1, le=100), refresh: bool = False):
    items = await crypto_news_service.get_latest_news(force_refresh=refresh, limit=limit)
    return {
        "items": items,
        "count": len(items),
        "providers": {
            "apify_configured": bool(settings.apify_api_token),
            "news_api_configured": bool(settings.news_api_key),
            "apify_actor": settings.apify_cryptopanic_actor_id,
        },
    }


@router.get("/signals")
async def get_news_signals(limit: int = Query(default=10, ge=1, le=50), refresh: bool = False):
    signals = await crypto_news_service.get_agent_signals(force_refresh=refresh, limit=limit)
    return {
        "signals": signals,
        "count": len(signals),
    }


@router.get("/status")
async def get_news_status():
    return {
        "apify_configured": bool(settings.apify_api_token),
        "news_api_configured": bool(settings.news_api_key),
        "actor_id": settings.apify_cryptopanic_actor_id,
    }
