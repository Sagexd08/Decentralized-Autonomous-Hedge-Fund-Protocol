"""
WebSocket trading feed.
Broadcasts live trade events to all connected clients.

The `stellar_event_listener` background task polls the Stellar Soroban
CapitalVault for ledger events and forwards them to connected WebSocket clients.
When no chain is connected the trading engine broadcasts simulated trades
directly via `broadcaster.broadcast(...)`.
"""
import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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


async def stellar_event_listener(app) -> None:
    """
    Background task: poll Stellar Soroban CapitalVault events and broadcast
    to WebSocket clients every 5 seconds.

    Stellar Soroban does not support push subscriptions; we poll the latest
    ledger events via simulate calls and detect changes in TVL / agent weights.
    """
    stellar = getattr(app.state, "stellar", None)
    if stellar is None:
        logger.info("stellar_event_listener: no Stellar client, exiting.")
        return

    last_tvl: int = -1

    while True:
        try:
            # Run blocking Stellar call in a thread
            tvl = await asyncio.to_thread(stellar.vault_total_tvl)

            if tvl != last_tvl and last_tvl != -1:
                # TVL changed — broadcast a synthetic event
                await broadcaster.broadcast({
                    "type":      "tvl_change",
                    "total_tvl": tvl,
                    "delta":     tvl - last_tvl,
                    "contracts": {
                        "capital_vault":     stellar.capital_vault_id,
                        "allocation_engine": stellar.allocation_engine_id,
                    },
                })
                logger.info("Stellar TVL changed: %d -> %d", last_tvl, tvl)

            last_tvl = tvl

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("stellar_event_listener poll error: %s", exc)

        await asyncio.sleep(5)
