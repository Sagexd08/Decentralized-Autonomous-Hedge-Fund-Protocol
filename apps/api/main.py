from pathlib import Path
from dotenv import load_dotenv

# Load from project root .env (works regardless of working directory)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)
# Also try local .env as fallback
load_dotenv(override=False)

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

if TYPE_CHECKING:
    from services.trading_engine import AgentTradingEngine

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
from api import ws_events
from api import protocol as protocol_api
from services import event_stream

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
        from ml.training.train_hybrid import load_model
        model, scaler = load_model(_LOCAL_MODEL_PATH)
        logger.info("ML model loaded from %s", _LOCAL_MODEL_PATH)
        return model, scaler
    except Exception as exc:
        logger.warning("ML model load skipped: %s", exc)
        return None, None


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
    from services.price_engine import price_engine
    from services.market_stream import market_stream
    price_engine.start()
    market_stream.start()
    logger.info("Price engine started.")

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

    # Algorand
    try:
        from core.algorand import AlgorandClient
        algorand = AlgorandClient.from_settings()
        app.state.algorand = algorand
        if algorand.is_connected():
            logger.info("Algorand algod connected.")
        else:
            logger.warning("Algorand algod not reachable — staking will record txid only.")
    except Exception as exc:
        app.state.algorand = None
        logger.warning("Algorand client init failed: %s", exc)

    # Trading engine
    from services.trading_engine import AgentTradingEngine
    ml_model = app.state.ml_model
    ml_scaler = app.state.ml_scaler
    if ml_model is not None:
        logger.info("CNN-LSTM model attached to trading engine.")
    else:
        logger.warning("No ML model available — trading engine will use momentum fallback.")

    engine = AgentTradingEngine(
        solana=solana,
        ml_model=ml_model,
        ml_scaler=ml_scaler,
    )
    app.state.trading_engine = engine

    # The protocol event stream (Phase 9). Started before the chain listener
    # because it is the one that carries phases 3-8: it tails `protocol_events`,
    # which triggers append to whenever an agent runs, a prediction settles, a
    # score is computed, capital is reallocated or an agent is frozen.
    #
    # Failing to start it must not take the API down. The events are already
    # durable in the table — the stream only decides whether anyone is
    # watching, and a dashboard that has to be refreshed is better than an API
    # that will not boot.
    try:
        await event_stream.stream.start()
        logger.info("Protocol event stream started at seq %s.",
                    event_stream.stream.watermark)
    except Exception as exc:
        logger.warning("Protocol event stream did not start: %s", exc)

    # WebSocket event listener for on-chain events
    listener_task = None
    if solana is not None:
        listener_task = asyncio.create_task(ws_trading.chain_event_listener(app))
        logger.info("Chain event listener task started (solana=True).")

    yield

    # Shutdown
    await event_stream.stream.stop()
    market_stream.stop()
    price_engine.stop()
    if listener_task is not None:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="IRIS Protocol API", version="2.2.0", lifespan=lifespan)

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
app.include_router(ws_events.router, tags=["events"])
app.include_router(protocol_api.router, prefix="/api/protocol", tags=["protocol"])


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
    return {"status": "ok", "service": "iris-api", "version": "2.2.0"}


@app.get("/health/db")
def health_db():
    """
    Liveness probe for the Postgres connection.

    Returns 200 with status "ok" only when a round trip to the database
    succeeds; 503 otherwise, so `docker compose` and any orchestrator can gate
    on it rather than on the process merely being up.
    """
    from db.connection import engine
    from sqlalchemy import text as _text

    if engine is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "error": "no database engine"},
        )

    try:
        with engine.connect() as conn:
            conn.execute(_text("select 1"))
        return {"status": "ok", "dialect": engine.dialect.name}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "error": str(exc)},
        )


@app.get("/api/trading/status")
async def trading_status(request: Request):
    """Return all active agents and live chain health."""
    engine = request.app.state.trading_engine
    solana = getattr(request.app.state, "solana", None)

    solana_health: dict = {}

    if solana:
        try:
            h = await asyncio.to_thread(solana.health)
            solana_health = {"connected": True, **h}
        except Exception as exc:
            solana_health = {"connected": False, "error": str(exc)}

    return {
        "active_agents": engine.active_agents(),
        "solana":        solana_health,
    }


@app.get("/health/chains")
async def health_chains(request: Request):
    """Return live health status for the Solana chain."""
    solana = getattr(request.app.state, "solana", None)

    solana_status: dict = {"connected": False}

    if solana:
        try:
            h = await asyncio.to_thread(solana.health)
            solana_status = {"connected": True, **h}
        except Exception as exc:
            solana_status = {"connected": False, "error": str(exc)}

    return {"solana": solana_status}



