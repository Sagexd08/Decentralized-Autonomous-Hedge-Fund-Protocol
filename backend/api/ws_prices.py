"""
WebSocket endpoint for live price feed and agent predictions.
Streams price ticks every 3 seconds and agent predictions every 10 seconds.
"""
import asyncio
import json
import logging
from dataclasses import asdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.price_engine import price_engine, compute_agent_prediction, INITIAL_PRICES
from agents.market_stream import market_stream
from core.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Agent IDs that are currently in "agent mode"
_agent_mode: dict[str, bool] = {}


def set_agent_mode(agent_id: str, enabled: bool) -> None:
    _agent_mode[agent_id] = enabled


def is_agent_mode(agent_id: str) -> bool:
    return _agent_mode.get(agent_id, False)


@router.websocket("/ws/prices")
async def ws_prices(websocket: WebSocket):
    await websocket.accept()
    q = price_engine.subscribe()
    try:
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=5.0)
                await websocket.send_json(item)
            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"ws_prices client disconnected: {e}")
    finally:
        price_engine.unsubscribe(q)


@router.websocket("/ws/market")
async def ws_market(websocket: WebSocket):
    await websocket.accept()
    q = market_stream.subscribe()
    try:
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=5.0)
                await websocket.send_json(item)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping", "source": settings.ws_market_source})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"ws_market client disconnected: {e}")
    finally:
        market_stream.unsubscribe(q)


@router.get("/api/prices/current")
async def get_current_prices():
    """REST endpoint for current prices."""
    prices = price_engine.get_current_prices()
    return {
        sym: {
            "price": round(p, 4),
            "initial": INITIAL_PRICES.get(sym, p),
            "change_pct": round((p - INITIAL_PRICES.get(sym, p)) / INITIAL_PRICES.get(sym, p) * 100, 3),
        }
        for sym, p in prices.items()
    }


@router.get("/api/stream/config")
async def get_stream_config():
    return {
        "market_source": settings.ws_market_source,
        "normalized_stream_enabled": settings.ws_normalized_stream_enabled,
        "alchemy": {
            "eth_mainnet_configured": bool(settings.alchemy_eth_mainnet_url),
            "solana_mainnet_configured": bool(settings.alchemy_solana_mainnet_url),
            "zksync_mainnet_configured": bool(settings.alchemy_zksync_mainnet_url),
        },
        "supabase_configured": bool(settings.supabase_url),
        "graph_configured": bool(settings.graph_api_key),
    }


@router.get("/api/prices/predictions/{agent_id}")
async def get_predictions(agent_id: str):
    """Get agent's current predictions for all tokens."""
    prices = price_engine.get_current_prices()
    predictions = []
    for sym in prices:
        history = price_engine.get_history(sym, 20)
        pred = compute_agent_prediction(agent_id, sym, history, prices[sym])
        predictions.append(asdict(pred))
    return {"agent_id": agent_id, "predictions": predictions}


@router.post("/api/agent-mode/{agent_id}")
async def set_mode(agent_id: str, body: dict):
    """Enable or disable agent mode for an agent."""
    enabled = body.get("enabled", True)
    set_agent_mode(agent_id, enabled)
    return {"agent_id": agent_id, "agent_mode": enabled}


@router.get("/api/agent-mode/{agent_id}")
async def get_mode(agent_id: str):
    return {"agent_id": agent_id, "agent_mode": is_agent_mode(agent_id)}
