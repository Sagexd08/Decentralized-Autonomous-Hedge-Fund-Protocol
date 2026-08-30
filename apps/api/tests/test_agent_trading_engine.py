"""
Legacy trading engine tests.

Rewritten against the engine that exists. The previous version constructed
`AgentTradingEngine(w3=..., vault_contract=..., accounts=[...])` and
monkeypatched `_apply_momentum`, `_remaining_allocation`, `_try_on_chain_swap`
and `_broadcast_simulated_trade` — every one of those is an Ethereum-era name
that the Solana migration removed. The tests were asserting the behaviour of
code that is not in the repository, and `monkeypatch.setattr` was failing on
the missing attributes rather than on anything the engine did.

Note what this file is *not*: this engine is the pre-v2 runtime. The v2 agent
runtime is the LangGraph graph in `agents/`, tested in
`tests/integration/test_agent_graph.py`. These tests keep the legacy path
honest while it is still mounted, and no more.
"""

import asyncio

import pytest

from services.trading_engine import AgentTradingEngine, _compute_decision


def engine() -> AgentTradingEngine:
    """No chain client and no model: the strategies are pure functions of price."""
    return AgentTradingEngine(solana=None, ml_model=None, ml_scaler=None)


def rising(n: int = 24, step: float = 0.5) -> list[float]:
    return [100.0 + i * step for i in range(n)]


def falling(n: int = 24, step: float = 0.5) -> list[float]:
    return [100.0 - i * step for i in range(n)]


def flat(n: int = 24) -> list[float]:
    return [100.0] * n


# ── _compute_decision ───────────────────────────────────────────────────────

def test_compute_decision_thresholds():
    """
    Directions are upper-case. The v2 schema's CHECK constraint only admits
    'BUY' / 'SELL' / 'HOLD', so a lower-case decision would be rejected at the
    insert — which is what the old assertions were expecting.
    """
    assert _compute_decision([100, 100.2, 100.4, 100.8]) == "BUY"
    assert _compute_decision([100, 99.8, 99.6, 99.0]) == "SELL"
    assert _compute_decision([100, 100.05, 100.0, 100.02]) == "HOLD"


def test_compute_decision_needs_enough_history():
    assert _compute_decision([100, 101, 102]) == "HOLD"


def test_compute_decision_survives_a_zero_price():
    """A zero opening price would divide by zero and take the loop down."""
    assert _compute_decision([0.0, 100.0, 101.0, 102.0]) == "HOLD"


# ── strategies ──────────────────────────────────────────────────────────────

def test_momentum_follows_the_trend():
    e = engine()
    assert e._momentum_strategy(rising(), 0.001, "balanced", 1.0)[0] == "BUY"
    assert e._momentum_strategy(falling(), 0.001, "balanced", 1.0)[0] == "SELL"
    assert e._momentum_strategy(flat(), 0.001, "balanced", 1.0)[0] == "HOLD"


def test_momentum_needs_a_window():
    assert engine()._momentum_strategy([100.0, 100.1], 0.001, "balanced", 1.0) == ("HOLD", 0)


def test_an_aggressive_agent_trades_on_a_smaller_move():
    """
    The confidence boost lowers the threshold. If it did not, the three agent
    risk profiles in AGENT_CONFIGS would be decorative.
    """
    e = engine()
    prices = [100.0, 100.0, 100.0, 100.05]   # +0.05%: over 0.001/5, under 0.001
    balanced = e._momentum_strategy(prices, 0.001, "balanced", 1.0)[0]
    aggressive = e._momentum_strategy(prices, 0.001, "aggressive", 5.0)[0]
    assert balanced == "HOLD" and aggressive == "BUY"


def test_mean_reversion_trades_against_the_move():
    """It must be the opposite sign of momentum, or the name is wrong."""
    e = engine()
    assert e._mean_reversion_strategy(rising(), 0.001, "balanced")[0] == "SELL"
    assert e._mean_reversion_strategy(falling(), 0.001, "balanced")[0] == "BUY"


def test_mean_reversion_needs_twenty_bars():
    assert engine()._mean_reversion_strategy(rising(10), 0.001, "balanced") == ("HOLD", 0)


def test_mean_reversion_holds_on_a_flat_tape():
    assert engine()._mean_reversion_strategy(flat(), 0.001, "balanced")[0] == "HOLD"


def test_breakout_reads_the_range():
    e = engine()
    assert e._breakout_strategy(rising(), 0.001, "conservative")[0] == "BUY"
    assert e._breakout_strategy(falling(), 0.001, "conservative")[0] == "SELL"


def test_breakout_needs_twenty_bars():
    assert engine()._breakout_strategy(rising(10), 0.001, "conservative") == ("HOLD", 0)


@pytest.mark.parametrize(
    "strategy", ["_momentum_strategy", "_mean_reversion_strategy", "_breakout_strategy"]
)
def test_every_strategy_returns_a_valid_direction(strategy):
    """The direction goes into a CHECK-constrained column; nothing else is legal."""
    e = engine()
    args = (rising(), 0.001, "balanced", 1.0) if strategy == "_momentum_strategy" \
        else (rising(), 0.001, "balanced")
    direction, size = getattr(e, strategy)(*args)
    assert direction in ("BUY", "SELL", "HOLD")
    assert isinstance(size, int)


# ── configuration ───────────────────────────────────────────────────────────

def test_an_unknown_agent_gets_the_default_config():
    config = engine()._get_agent_config("AGT-DOES-NOT-EXIST")
    assert config == AgentTradingEngine.AGENT_CONFIGS["default"]


def test_agent_config_is_a_copy_not_the_shared_dict():
    """
    Mutating one agent's config must not reach into the class-level table and
    change every other agent's risk profile.
    """
    e = engine()
    config = e._get_agent_config("AGT-001")
    config["threshold"] = 999.0
    assert AgentTradingEngine.AGENT_CONFIGS["AGT-001"]["threshold"] != 999.0


# ── task lifecycle ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_and_stop_trading_task(monkeypatch):
    e = engine()

    async def fake_loop(_agent_id):
        await asyncio.sleep(3600)

    monkeypatch.setattr(e, "_trading_loop", fake_loop)

    await e.start("AGT-LOOP")
    assert e.is_trading("AGT-LOOP") is True
    assert "AGT-LOOP" in e.active_agents()

    await e.stop("AGT-LOOP")
    assert e.is_trading("AGT-LOOP") is False
    assert e.active_agents() == []


@pytest.mark.asyncio
async def test_starting_twice_is_rejected(monkeypatch):
    e = engine()

    async def fake_loop(_agent_id):
        await asyncio.sleep(3600)

    monkeypatch.setattr(e, "_trading_loop", fake_loop)
    await e.start("AGT-DUP")
    try:
        with pytest.raises(ValueError):
            await e.start("AGT-DUP")
    finally:
        await e.stop("AGT-DUP")


@pytest.mark.asyncio
async def test_stopping_an_idle_agent_is_rejected():
    with pytest.raises(ValueError):
        await engine().stop("AGT-NEVER-STARTED")
