import asyncio

import pytest

from agents.market_stream import NormalizedMarketStream

def test_market_stream_normalize_shape():
    stream = NormalizedMarketStream()
    normalized = stream._normalize(
        {
            "symbol": "WBTC",
            "price": 30001.25,
            "change_pct": 0.12,
            "timestamp": 123456.0,
        }
    )

    assert normalized["type"] == "normalized_market_event"
    assert normalized["symbol"] == "WBTC"
    assert normalized["price"] == 30001.25
    assert normalized["change_pct"] == 0.12
    assert normalized["agent_ready"] is True
    assert normalized["langgraph_ready"] is True

@pytest.mark.asyncio
async def test_market_stream_broadcast_drops_full_queues():
    stream = NormalizedMarketStream()
    full_q = asyncio.Queue(maxsize=1)
    full_q.put_nowait({"already": "full"})
    live_q = asyncio.Queue(maxsize=2)

    stream._subscribers = [full_q, live_q]
    await stream._broadcast({"symbol": "UNI"})

    assert full_q not in stream._subscribers
    assert live_q in stream._subscribers
    assert (await live_q.get())["symbol"] == "UNI"
