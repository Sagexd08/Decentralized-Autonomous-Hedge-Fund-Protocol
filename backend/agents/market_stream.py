import asyncio
import logging
import time
from typing import Optional

from core.settings import settings
from agents.price_engine import price_engine

logger = logging.getLogger(__name__)


class NormalizedMarketStream:
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def start(self) -> None:
        if self._running or not settings.ws_normalized_stream_enabled:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        source_queue = price_engine.subscribe()
        try:
            while self._running:
                item = await source_queue.get()
                normalized = self._normalize(item)
                await self._broadcast(normalized)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"NormalizedMarketStream error: {exc}")
        finally:
            price_engine.unsubscribe(source_queue)

    def _normalize(self, item: dict) -> dict:
        return {
            "type": "normalized_market_event",
            "source": settings.ws_market_source,
            "network": "ethereum",
            "symbol": item.get("symbol"),
            "price": item.get("price"),
            "change_pct": item.get("change_pct"),
            "timestamp": item.get("timestamp", time.time()),
            "agent_ready": True,
            "langgraph_ready": True,
        }

    async def _broadcast(self, message: dict) -> None:
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)


market_stream = NormalizedMarketStream()
