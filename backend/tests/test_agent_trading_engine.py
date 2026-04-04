import asyncio

import pytest

from agents.trading_engine import AgentTradingEngine, _compute_decision


class DummyAccount:
    def __init__(self, address: str): 
        self.address = address

    def sign_transaction(self, tx):
        class Signed:
            raw_transaction = b"raw"

        return Signed()


def _engine_with_one_account() -> AgentTradingEngine:
    return AgentTradingEngine(
        w3=None,
        vault_contract=None,
        price_feed_contract=None,
        accounts=[DummyAccount("0x1111111111111111111111111111111111111111")],
    )


def test_compute_decision_thresholds():
    assert _compute_decision([100, 100.2, 100.4, 100.8]) == "buy"
    assert _compute_decision([100, 99.8, 99.6, 99.0]) == "sell"
    assert _compute_decision([100, 100.05, 100.0, 100.02]) == "hold"


def test_remaining_allocation_fallback_without_vault():
    engine = _engine_with_one_account()
    remaining = engine._remaining_allocation("AGT-XYZ")
    assert remaining == int(1e18)


@pytest.mark.asyncio
async def test_apply_momentum_buy_falls_back_to_simulated(monkeypatch):
    engine = _engine_with_one_account()
    calls = {"broadcast": 0}

    async def fake_try_on_chain(*args, **kwargs):
        return False

    async def fake_broadcast(*args, **kwargs):
        calls["broadcast"] += 1

    monkeypatch.setattr(engine, "_remaining_allocation", lambda _agent: int(1e18))
    monkeypatch.setattr(engine, "_try_on_chain_swap", fake_try_on_chain)
    monkeypatch.setattr(engine, "_broadcast_simulated_trade", fake_broadcast)

    await engine._apply_momentum("AGT-1", "WBTC", "0xToken", "BUY")
    assert calls["broadcast"] == 1


@pytest.mark.asyncio
async def test_apply_momentum_sell_broadcasts(monkeypatch):
    engine = _engine_with_one_account()
    calls = {"broadcast": 0}

    async def fake_broadcast(*args, **kwargs):
        calls["broadcast"] += 1

    monkeypatch.setattr(engine, "_broadcast_simulated_trade", fake_broadcast)

    await engine._apply_momentum("AGT-1", "LINK", "0xToken", "SELL")
    assert calls["broadcast"] == 1


@pytest.mark.asyncio
async def test_start_and_stop_trading_task(monkeypatch):
    engine = _engine_with_one_account()

    async def fake_loop(_agent_id):
        await asyncio.sleep(3600)

    monkeypatch.setattr(engine, "_trading_loop", fake_loop)

    await engine.start("AGT-LOOP")
    assert engine.is_trading("AGT-LOOP") is True

    await engine.stop("AGT-LOOP")
    assert engine.is_trading("AGT-LOOP") is False
