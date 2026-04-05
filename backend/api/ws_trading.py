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
    Also polls Solana CapitalVault TVL for cross-chain comparison.
    """
    stellar = getattr(app.state, "stellar", None)
    solana  = getattr(app.state, "solana", None)

    if stellar is None and solana is None:
        logger.info("stellar_event_listener: no chain clients, exiting.")
        return

    last_stellar_tvl: int = -1
    last_solana_tvl: int  = -1

    while True:
        try:
            stellar_tvl = 0
            solana_tvl  = 0

            if stellar:
                try:
                    stellar_tvl = await asyncio.to_thread(stellar.vault_total_tvl)
                except Exception:
                    pass

            if solana:
                try:
                    solana_tvl = await asyncio.to_thread(solana.vault_total_tvl)
                except Exception:
                    pass

            stellar_changed = stellar_tvl != last_stellar_tvl and last_stellar_tvl != -1
            solana_changed  = solana_tvl  != last_solana_tvl  and last_solana_tvl  != -1

            if stellar_changed or solana_changed:
                await broadcaster.broadcast({
                    "type":         "tvl_change",
                    "stellar_tvl":  stellar_tvl,
                    "solana_tvl":   solana_tvl,
                    "total_tvl":    stellar_tvl + solana_tvl,
                    "stellar_delta": stellar_tvl - last_stellar_tvl if last_stellar_tvl != -1 else 0,
                    "solana_delta":  solana_tvl  - last_solana_tvl  if last_solana_tvl  != -1 else 0,
                    "contracts": {
                        "stellar_capital_vault":     stellar.capital_vault_id if stellar else None,
                        "stellar_allocation_engine": stellar.allocation_engine_id if stellar else None,
                        "solana_capital_vault":      solana.capital_vault_id if solana else None,
                        "solana_allocation_engine":  solana.allocation_engine_id if solana else None,
                    },
                })
                logger.info(
                    "TVL change → stellar: %d→%d  solana: %d→%d",
                    last_stellar_tvl, stellar_tvl, last_solana_tvl, solana_tvl,
                )

            last_stellar_tvl = stellar_tvl
            last_solana_tvl  = solana_tvl

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("stellar_event_listener poll error: %s", exc)

        await asyncio.sleep(5)
