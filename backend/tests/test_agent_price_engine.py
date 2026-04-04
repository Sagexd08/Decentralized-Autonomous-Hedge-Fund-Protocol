import pytest

from agents.price_engine import (
    PRICE_BOUNDS,
    PriceEngine,
    compute_agent_prediction,
)

def test_price_engine_tick_stays_within_bounds():
    engine = PriceEngine(tick_interval=3.0)

    for _ in range(20):
        tick = engine._tick()
        assert len(tick) == 4
        for item in tick:
            symbol = item["symbol"]
            lo, hi = PRICE_BOUNDS[symbol]
            assert lo <= item["price"] <= hi

def test_price_engine_subscribe_and_unsubscribe():
    engine = PriceEngine(tick_interval=3.0)
    q = engine.subscribe()
    assert q in engine._subscribers

    engine.unsubscribe(q)
    assert q not in engine._subscribers

def test_compute_agent_prediction_buy_signal():
    history = [100.0, 101.0, 102.5, 104.0, 106.0, 108.0]
    pred = compute_agent_prediction("AGT-001", "TEST", history, 108.0)
    assert pred.decision == "BUY"
    assert pred.predicted_change_pct > 0

def test_compute_agent_prediction_sell_signal():
    history = [120.0, 118.0, 116.0, 114.0, 112.0, 110.0]
    pred = compute_agent_prediction("AGT-001", "TEST", history, 110.0)
    assert pred.decision == "SELL"
    assert pred.predicted_change_pct < 0

def test_compute_agent_prediction_hold_with_flat_history():
    history = [100.0, 100.0, 100.0, 100.0, 100.0]
    pred = compute_agent_prediction("AGT-001", "TEST", history, 100.0)
    assert pred.decision == "HOLD"
    assert abs(pred.predicted_change_pct) < 0.01
