"""
Trading REST API endpoints.

POST /api/agents/{agent_id}/start-trading
POST /api/agents/{agent_id}/stop-trading
GET  /api/agents/{agent_id}/portfolio
GET  /api/trading/status
"""
import asyncio
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
    solana  = getattr(request.app.state, "solana", None)

    allocation_weight: float = 0.0
    pool_tvls: dict = {}
    agent_score: int = 0
    solana_score: int = 0

    if stellar:
        try:
            stellar_addr = stellar.public_key or ""
            if stellar_addr:
                raw = await asyncio.to_thread(stellar.vault_agent_weight, stellar_addr)
                allocation_weight = raw / 1e18
            pool_tvls = await asyncio.to_thread(stellar.all_pool_tvls)
            if stellar_addr:
                agent_score = await asyncio.to_thread(
                    stellar.allocation_get_reputation_score, stellar_addr
                )
        except Exception as exc:
            logger.warning("Portfolio Stellar read failed: %s", exc)

    if solana:
        try:
            solana_score = await asyncio.to_thread(
                solana.allocation_get_agent_score, solana.wallet_address
            )
            solana_tvls = await asyncio.to_thread(solana.all_pool_tvls)
            for k, v in solana_tvls.items():
                pool_tvls[k] = pool_tvls.get(k, 0) + v
        except Exception as exc:
            logger.warning("Portfolio Solana read failed: %s", exc)

    return {
        "agent_id":          agent_id,
        "allocation_weight": allocation_weight,
        "pool_tvls":         pool_tvls,
        "agent_score":       agent_score,
        "solana_score":      solana_score,
        "trading_active":    engine.is_trading(agent_id),
        "stellar_contracts": {
            "capital_vault":     stellar.capital_vault_id if stellar else None,
            "allocation_engine": stellar.allocation_engine_id if stellar else None,
            "agent_registry":    stellar.agent_registry_id if stellar else None,
            "slashing_module":   stellar.slashing_module_id if stellar else None,
            "network":           "testnet",
        },
        "solana_programs": {
            "capital_vault":     solana.capital_vault_id if solana else None,
            "allocation_engine": solana.allocation_engine_id if solana else None,
            "agent_registry":    solana.agent_registry_id if solana else None,
            "slashing_module":   solana.slashing_module_id if solana else None,
            "wallet":            solana.wallet_address if solana else None,
            "network":           "testnet",
        },
    }
