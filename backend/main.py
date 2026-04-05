from dotenv import load_dotenv
load_dotenv()

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

if TYPE_CHECKING:
    from agents.trading_engine import AgentTradingEngine

# Configure logging before anything else
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from api import agents, pools, analytics, contracts, governance, intelligence, integrations, news
from api import trading as trading_api
from api import ws_trading
from api import ws_prices
from api import ws_social

_MODEL_BUCKET = "models"
_MODEL_OBJECT_PATH = "model.pkl"
_LOCAL_MODEL_PATH = Path(__file__).parent / "ml" / "model.pkl"


def _sync_ml_model_from_supabase() -> bool:
    """Best-effort startup sync so the API boots with the latest deployed model."""
    try:
        from core.supabase import download_storage_file
        download_storage_file(_MODEL_BUCKET, _MODEL_OBJECT_PATH, _LOCAL_MODEL_PATH)
        logger.info("ML model synced from Supabase storage: %s/%s", _MODEL_BUCKET, _MODEL_OBJECT_PATH)
        return True
    except Exception as exc:
        logger.warning("ML model sync from Supabase skipped: %s", exc)
        return False


def _load_ml_artifacts():
    """Load the local model artifact into app state when available."""
    try:
        from ml.train_hybrid import load_model
        model, scaler = load_model(_LOCAL_MODEL_PATH)
        logger.info("ML model loaded from %s", _LOCAL_MODEL_PATH)
        return model, scaler
    except Exception as exc:
        logger.warning("ML model load skipped: %s", exc)
        return None, None


def _init_stellar():
    """Build the Stellar Soroban client from environment variables."""
    try:
        from core.stellar_client import build_stellar_client
        return build_stellar_client()
    except Exception as exc:
        logger.warning("Stellar client init failed: %s", exc)
        return None


def _init_solana():
    """Build the Solana programs client from environment variables."""
    try:
        from core.solana_client import build_solana_client
        return build_solana_client()
    except Exception as exc:
        logger.warning("Solana client init failed: %s", exc)
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ML model
    app.state.ml_model_synced = _sync_ml_model_from_supabase()
    app.state.ml_model, app.state.ml_scaler = _load_ml_artifacts()

    # Price engine + market stream
    from agents.price_engine import price_engine
    from agents.market_stream import market_stream
    price_engine.start()
    market_stream.start()
    logger.info("Price engine started.")

    # Stellar Soroban contracts
    stellar = _init_stellar()
    app.state.stellar = stellar
    if stellar:
        mode = "read-write" if stellar.secret_key else "read-only"
        logger.info("Stellar Soroban client initialized (%s mode).", mode)
        logger.info(
            "  capital_vault=%s  allocation_engine=%s",
            stellar.capital_vault_id,
            stellar.allocation_engine_id,
        )
    else:
        logger.warning("Stellar Soroban client not available — check .env STELLAR_* vars.")

    # Solana programs
    solana = _init_solana()
    app.state.solana = solana
    if solana:
        logger.info(
            "Solana client initialized → wallet=%s vault=%s",
            solana.wallet_address[:12],
            solana.capital_vault_id[:12],
        )
    else:
        logger.warning("Solana client not available — check .env SOLANA_* vars.")

    # Trading engine
    from agents.trading_engine import AgentTradingEngine
    ml_model = app.state.ml_model
    ml_scaler = app.state.ml_scaler
    if ml_model is not None:
        logger.info("CNN-LSTM model attached to trading engine.")
    else:
        logger.warning("No ML model available — trading engine will use momentum fallback.")

    engine = AgentTradingEngine(
        stellar=stellar,
        solana=solana,
        ml_model=ml_model,
        ml_scaler=ml_scaler,
    )
    app.state.trading_engine = engine

    # Auto-start trading for all active agents from the registry
    _auto_start_agents = []
    try:
        from api.agents import AGENTS
        _auto_start_agents = [a["id"] for a in AGENTS if a.get("status") == "active"]
    except Exception:
        pass
    if stellar:
        try:
            stellar_agents = stellar.registry_get_active_agents()
            _auto_start_agents = list(set(_auto_start_agents + stellar_agents))
        except Exception:
            pass
    for aid in _auto_start_agents:
        try:
            await engine.start(aid)
            logger.info("Auto-started trading for agent %s", aid)
        except Exception as exc:
            logger.debug("Auto-start skipped for %s: %s", aid, exc)

    # WebSocket event listener for on-chain events
    listener_task = None
    if stellar is not None or solana is not None:
        listener_task = asyncio.create_task(ws_trading.stellar_event_listener(app))
        logger.info("Chain event listener task started (stellar=%s, solana=%s).", stellar is not None, solana is not None)

    yield

    # Shutdown
    market_stream.stop()
    price_engine.stop()
    if listener_task is not None:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="DACAP API", version="2.2.0", lifespan=lifespan)

allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(pools.router, prefix="/api/pools", tags=["pools"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["intelligence"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(contracts.router, prefix="/api/contracts", tags=["contracts"])
app.include_router(governance.router, prefix="/api/governance", tags=["governance"])
app.include_router(trading_api.router, prefix="/api/agents", tags=["trading"])
app.include_router(ws_trading.router, tags=["websocket"])
app.include_router(ws_prices.router, tags=["prices"])
app.include_router(ws_social.router, tags=["social"])


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "http://localhost:3000"),
            "Access-Control-Allow-Credentials": "true",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "http://localhost:3000"),
            "Access-Control-Allow-Credentials": "true",
        },
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.2.0"}


@app.get("/api/trading/status")
async def trading_status(request: Request):
    """Return all active agents and live chain health."""
    engine = request.app.state.trading_engine
    stellar = getattr(request.app.state, "stellar", None)
    solana  = getattr(request.app.state, "solana", None)

    stellar_health: dict = {}
    solana_health:  dict = {}

    if stellar:
        try:
            tvl = await asyncio.to_thread(stellar.vault_total_tvl)
            stellar_health = {
                "connected":         True,
                "total_tvl_stroops": tvl,
                "capital_vault":     stellar.capital_vault_id,
                "allocation_engine": stellar.allocation_engine_id,
                "agent_registry":    stellar.agent_registry_id,
                "slashing_module":   stellar.slashing_module_id,
                "network":           "testnet",
            }
        except Exception as exc:
            stellar_health = {"connected": False, "error": str(exc)}

    if solana:
        try:
            h = await asyncio.to_thread(solana.health)
            solana_health = {"connected": True, **h}
        except Exception as exc:
            solana_health = {"connected": False, "error": str(exc)}

    return {
        "active_agents": engine.active_agents(),
        "stellar":       stellar_health,
        "solana":        solana_health,
    }


@app.get("/health/chains")
async def health_chains(request: Request):
    """Return live health status for both Stellar and Solana chains."""
    stellar = getattr(request.app.state, "stellar", None)
    solana  = getattr(request.app.state, "solana", None)

    stellar_status: dict = {"connected": False}
    solana_status: dict  = {"connected": False}

    if stellar:
        try:
            tvl = await asyncio.to_thread(stellar.vault_total_tvl)
            stellar_status = {
                "connected":         True,
                "total_tvl_stroops": tvl,
                "capital_vault":     stellar.capital_vault_id,
                "allocation_engine": stellar.allocation_engine_id,
                "agent_registry":    stellar.agent_registry_id,
                "slashing_module":   stellar.slashing_module_id,
                "network":           "testnet",
                "rpc_url":           stellar.rpc_url,
            }
        except Exception as exc:
            stellar_status = {"connected": False, "error": str(exc)}

    if solana:
        try:
            h = await asyncio.to_thread(solana.health)
            solana_status = {"connected": True, **h}
        except Exception as exc:
            solana_status = {"connected": False, "error": str(exc)}

    return {"stellar": stellar_status, "solana": solana_status}



