"""
Trading REST API endpoints.

POST /{agent_id}/start-trading  → start agent trading loop
POST /{agent_id}/stop-trading   → stop agent trading loop
GET  /{agent_id}/portfolio      → allocation weight, TVL, trading status
"""
import logging
from fastapi import APIRouter, HTTPException, Request

from agents.trading_engine import AgentTradingEngine

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{agent_id}/start-trading")
async def start_trading(agent_id: str, request: Request):
    engine: AgentTradingEngine = request.app.state.trading_engine
    try:
        await engine.start(agent_id)
        return {"status": "started", "agent_id": agent_id}
    except ValueError:
        raise HTTPException(status_code=409, detail="Agent is already trading")


@router.post("/{agent_id}/stop-trading")
async def stop_trading(agent_id: str, request: Request):
    engine: AgentTradingEngine = request.app.state.trading_engine
    try:
        await engine.stop(agent_id)
        return {"status": "stopped", "agent_id": agent_id}
    except ValueError:
        raise HTTPException(status_code=409, detail="Agent is not trading")


@router.get("/{agent_id}/portfolio")
async def get_portfolio(agent_id: str, request: Request):
    engine: AgentTradingEngine = request.app.state.trading_engine
    stellar = getattr(request.app.state, "stellar", None)

    allocation_weight: float = 0.0
    pool_tvls: dict = {}
    agent_score: int = 0

    if stellar is not None:
        try:
            # Read agent allocation weight from CapitalVault
            stellar_addr = stellar.public_key or ""
            if stellar_addr:
                raw_weight = await asyncio.to_thread(
                    stellar.vault_agent_weight, stellar_addr
                )
                allocation_weight = raw_weight / 1e18

            # Read pool TVLs
            pool_tvls = await asyncio.to_thread(stellar.all_pool_tvls)

            # Read reputation score from AllocationEngine
            if stellar_addr:
                agent_score = await asyncio.to_thread(
                    stellar.allocation_get_reputation_score, stellar_addr
                )
        except Exception as exc:
            logger.warning("Portfolio read from Stellar failed: %s", exc)

    return {
        "agent_id":         agent_id,
        "allocation_weight": allocation_weight,
        "pool_tvls":         pool_tvls,
        "agent_score":       agent_score,
        "trading_active":    engine.is_trading(agent_id),
        "stellar_contracts": {
            "capital_vault":     stellar.capital_vault_id if stellar else None,
            "allocation_engine": stellar.allocation_engine_id if stellar else None,
            "agent_registry":    stellar.agent_registry_id if stellar else None,
            "slashing_module":   stellar.slashing_module_id if stellar else None,
        },
    }


# asyncio is used in the portfolio endpoint
import asyncio  # noqa: E402  (placed here to avoid top-level import collision)
