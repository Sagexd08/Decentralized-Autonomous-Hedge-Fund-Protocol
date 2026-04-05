"""
WebSocket trading feed.
Broadcasts TradeExecuted events from CapitalVault to all connected clients.
"""
import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.trading_engine import TOKEN_SYMBOL

logger = logging.getLogger(__name__)

router = APIRouter()

class TradingBroadcaster:
    def __init__(self):
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        self._clients -= dead

broadcaster = TradingBroadcaster()

@router.websocket("/ws/trading")
async def ws_trading(websocket: WebSocket):
    await broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
    except Exception:
        broadcaster.disconnect(websocket)

async def event_listener(app) -> None:
    """Background task: poll TradeExecuted events and broadcast to WebSocket clients."""
    vault = getattr(app.state, "vault_contract", None)
    if vault is None:
        logger.warning("event_listener: no vault contract, exiting.")
        return

    while True:
        try:
            event_filter = vault.events.TradeExecuted.create_filter(fromBlock="latest")
            while True:
                try:
                    for event in event_filter.get_new_entries():
                        args = event["args"]
                        token_addr = args.get("tokenOut", "")
                        token_sym = TOKEN_SYMBOL.get(token_addr, token_addr[:6] if token_addr else "?")
                        await broadcaster.broadcast({
                            "agent":     args.get("agent", ""),
                            "token":     token_sym,
                            "amountIn":  str(args.get("amountIn", 0)),
                            "amountOut": str(args.get("amountOut", 0)),
                            "timestamp": args.get("timestamp", 0),
                            "type":      args.get("tradeType", "swap"),
                        })
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"event_listener poll error: {e}")
                    break
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"event_listener filter lost: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)
