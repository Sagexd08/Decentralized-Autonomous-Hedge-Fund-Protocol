from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

from api import agents, pools, analytics, contracts, governance, intelligence, integrations, news
from api import trading as trading_api
from api import ws_trading
from api import ws_prices
from api import ws_social

_CONFIG_PATH = Path(__file__).parent.parent / "frontend" / "src" / "contracts" / "config.json"
_MODEL_BUCKET = "models"
_MODEL_OBJECT_PATH = "model.pkl"
_LOCAL_MODEL_PATH = Path(__file__).parent / "ml" / "model.pkl"


def _init_web3_and_contracts():
    """Initialize web3 connection and contract instances. Returns (w3, vault, price_feed, accounts) or None."""
    try:
        from web3 import Web3
        from eth_account import Account

        rpc_url = os.getenv("HARDHAT_RPC_URL", "http://127.0.0.1:8545")
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            logger.warning(f"Cannot connect to Hardhat node at {rpc_url}. Trading engine disabled.")
            return None

        with open(_CONFIG_PATH) as f:
            cfg = json.load(f)

        # Load ABIs from artifacts
        artifacts_base = Path(__file__).parent.parent / "contracts" / "artifacts" / "src"

        def load_abi(name: str):
            p = artifacts_base / f"{name}.sol" / f"{name}.json"
            with open(p) as f:
                return json.load(f)["abi"]

        vault_abi = load_abi("CapitalVault")
        price_feed_abi = load_abi("MockPriceFeed")

        vault = w3.eth.contract(address=cfg["CapitalVault"], abi=vault_abi)
        price_feed = w3.eth.contract(address=cfg["MockPriceFeed"], abi=price_feed_abi)

        # Load Hardhat accounts from private keys (env or default Hardhat keys)
        hardhat_keys = os.getenv("HARDHAT_PRIVATE_KEYS", "")
        if hardhat_keys:
            accounts = [Account.from_key(k.strip()) for k in hardhat_keys.split(",") if k.strip()]
        else:
            # Default Hardhat deterministic accounts (first 5)
            default_keys = [
                "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
                "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
                "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
                "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6",
                "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926b",
            ]
            accounts = [Account.from_key(k) for k in default_keys]

        return w3, vault, price_feed, accounts
    except Exception as e:
        logger.warning(f"Web3 init failed: {e}. Trading engine disabled.")
        return None


def _sync_ml_model_from_supabase() -> bool:
    """Best-effort startup sync so the API boots with the latest deployed model."""
    try:
        from core.supabase import download_storage_file

        download_storage_file(_MODEL_BUCKET, _MODEL_OBJECT_PATH, _LOCAL_MODEL_PATH)
        logger.info(
            "ML model synced from Supabase storage: %s/%s -> %s",
            _MODEL_BUCKET,
            _MODEL_OBJECT_PATH,
            _LOCAL_MODEL_PATH,
        )
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ml_model_synced = _sync_ml_model_from_supabase()
    app.state.ml_model, app.state.ml_scaler = _load_ml_artifacts()

    # Start price engine
    from agents.price_engine import price_engine
    from agents.market_stream import market_stream
    price_engine.start()
    market_stream.start()
    logger.info("Price engine started.")

    # Initialize trading engine
    from agents.trading_engine import AgentTradingEngine

    result = _init_web3_and_contracts()
    if result is not None:
        w3, vault, price_feed, accounts = result
        app.state.vault_contract = vault
        app.state.trading_engine = AgentTradingEngine(w3, vault, price_feed, accounts)
        # Start event listener background task
        listener_task = asyncio.create_task(ws_trading.event_listener(app))
        logger.info("Trading engine and WebSocket event listener started.")
    else:
        # Stub engine so endpoints don't crash
        app.state.vault_contract = None
        app.state.trading_engine = AgentTradingEngine(None, None, None, [])
        listener_task = None
        logger.warning("Trading engine running in stub mode (no chain connection).")

    yield

    # Cleanup
    market_stream.stop()
    price_engine.stop()
    if listener_task is not None:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="DACAP API", version="2.1.0", lifespan=lifespan)

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
    logger.exception(f"Unhandled error on {request.method} {request.url}: {exc}")
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
    return {"status": "ok", "version": "2.1.0"}
