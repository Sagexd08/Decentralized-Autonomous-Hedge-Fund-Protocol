<<<<<<< HEAD
"""
Trading REST API endpoints.
POST /{agent_id}/start-trading  → start agent trading loop
POST /{agent_id}/stop-trading   → stop agent trading loop
GET  /{agent_id}/portfolio      → token balances, PnL, trading status
"""
import logging
from fastapi import APIRouter, HTTPException, Request

from agents.trading_engine import AgentTradingEngine, TOKEN_ADDRESSES

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
    vault = getattr(request.app.state, "vault_contract", None)

    token_balances: dict[str, str] = {}
    pnl_wei: str = "0"

    if vault is not None:
        try:
            account_addr = engine._account_for(agent_id).address
            for sym, addr in TOKEN_ADDRESSES.items():
                if addr:
                    balance = vault.functions.agentTokenBalances(account_addr, addr).call()
                    token_balances[sym] = str(balance)
            pnl_raw = vault.functions.agentPnL(account_addr).call()
            pnl_wei = str(pnl_raw)
        except Exception as e:
            logger.warning(f"Failed to read portfolio for {agent_id}: {e}")

    return {
        "token_balances": token_balances,
        "pnl_wei": pnl_wei,
        "trading_active": engine.is_trading(agent_id),
    }
=======
"""
Trading REST API endpoints.
POST /{agent_id}/start-trading  → start agent trading loop
POST /{agent_id}/stop-trading   → stop agent trading loop
GET  /{agent_id}/portfolio      → token balances, PnL, trading status
"""
import logging
from fastapi import APIRouter, HTTPException, Request

from agents.trading_engine import AgentTradingEngine, TOKEN_ADDRESSES

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
    vault = getattr(request.app.state, "vault_contract", None)

    token_balances: dict[str, str] = {}
    pnl_wei: str = "0"

    if vault is not None:
        try:
            account_addr = engine._account_for(agent_id).address
            for sym, addr in TOKEN_ADDRESSES.items():
                if addr:
                    balance = vault.functions.agentTokenBalances(account_addr, addr).call()
                    token_balances[sym] = str(balance)
            pnl_raw = vault.functions.agentPnL(account_addr).call()
            pnl_wei = str(pnl_raw)
        except Exception as e:
            logger.warning(f"Failed to read portfolio for {agent_id}: {e}")

    return {
        "token_balances": token_balances,
        "pnl_wei": pnl_wei,
        "trading_active": engine.is_trading(agent_id),
    }
>>>>>>> D!
