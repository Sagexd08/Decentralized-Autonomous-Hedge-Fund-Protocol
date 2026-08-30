"""
WebSocket trading feed.
Broadcasts live trade events to all connected clients.

The `chain_event_listener` background task polls the Solana CapitalVault
for TVL changes and forwards them to connected WebSocket clients.
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


async def chain_event_listener(app) -> None:
    """
    Background task: poll the Solana CapitalVault TVL every 5 seconds and
    broadcast a `tvl_change` event to WebSocket clients whenever it moves.
    """
    solana = getattr(app.state, "solana", None)

    if solana is None:
        logger.info("chain_event_listener: no chain client, exiting.")
        return

    last_solana_tvl: int = -1

    while True:
        try:
            solana_tvl = 0
            try:
                solana_tvl = await asyncio.to_thread(solana.vault_total_tvl)
            except Exception:
                pass

            if solana_tvl != last_solana_tvl and last_solana_tvl != -1:
                await broadcaster.broadcast({
                    "type":         "tvl_change",
                    "solana_tvl":   solana_tvl,
                    "total_tvl":    solana_tvl,
                    "solana_delta": solana_tvl - last_solana_tvl,
                    "contracts": {
                        "solana_capital_vault":     solana.capital_vault_id,
                        "solana_allocation_engine": solana.allocation_engine_id,
                    },
                })
                logger.info("TVL change → solana: %d→%d", last_solana_tvl, solana_tvl)

            last_solana_tvl = solana_tvl

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("chain_event_listener poll error: %s", exc)

        await asyncio.sleep(5)
