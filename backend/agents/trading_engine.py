"""
AgentTradingEngine: manages one asyncio Task per active agent.

Each cycle:
  1. Fetch live prices from the O-U price engine.
  2. Run CNN-LSTM inference (falls back to momentum signal if model absent).
  3. Decide BUY / SELL / HOLD per token.
  4. On BUY/SELL — attempt to submit a Stellar Soroban update (allocation +
     performance report); broadcast simulated trade to WebSocket clients.

The engine runs in simulation mode when Stellar contracts are not reachable
(no STELLAR_SECRET_KEY, or RPC unreachable).
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.stellar_client import StellarContracts

logger = logging.getLogger(__name__)

# Simulated token symbols (matching the O-U price engine)
TOKEN_SYMBOLS = ["WBTC", "USDC", "LINK", "UNI"]

# Pool label → Stellar pool ID
POOL_IDS = {"conservative": 0, "balanced": 1, "aggressive": 2}


def _compute_decision(price_history: list[float]) -> str:
    """
    Momentum trading signal from a short price history.
    Returns 'BUY', 'SELL', or 'HOLD'.
    """
    if len(price_history) < 4:
        return "HOLD"
    price_now = price_history[-1]
    price_old = price_history[0]
    if price_old == 0:
        return "HOLD"
    momentum = (price_now - price_old) / price_old
    if momentum > 0.005:
        return "BUY"
    elif momentum < -0.005:
        return "SELL"
    return "HOLD"


class AgentTradingEngine:
    """
    Manages one asyncio Task per active agent.

    Parameters
    ----------
    stellar : StellarContracts | None
        Live Soroban client (read-only or read-write depending on STELLAR_SECRET_KEY).
        Pass None to run in pure simulation mode.
    ml_model, ml_scaler
        Optional CNN-LSTM model artifacts. Falls back to momentum if None.
    """

    def __init__(
        self,
        stellar: Optional["StellarContracts"] = None,
        ml_model=None,
        ml_scaler=None,
    ):
        self.stellar = stellar
        self.ml_model = ml_model
        self.ml_scaler = ml_scaler
        self._tasks: dict[str, asyncio.Task] = {}

    # ── public control ────────────────────────────────────────────────────────

    async def start(self, agent_id: str) -> None:
        """Launch trading loop for agent_id. Raises ValueError if already running."""
        if self.is_trading(agent_id):
            raise ValueError(f"Agent {agent_id} is already trading")
        task = asyncio.create_task(self._trading_loop(agent_id))
        self._tasks[agent_id] = task
        logger.info("Trading started for agent %s", agent_id)

    async def stop(self, agent_id: str) -> None:
        """Cancel trading loop for agent_id. Raises ValueError if not running."""
        if not self.is_trading(agent_id):
            raise ValueError(f"Agent {agent_id} is not trading")
        task = self._tasks.pop(agent_id)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info("Trading stopped for agent %s", agent_id)

    def is_trading(self, agent_id: str) -> bool:
        task = self._tasks.get(agent_id)
        return task is not None and not task.done()

    # ── loop ──────────────────────────────────────────────────────────────────

    async def _trading_loop(self, agent_id: str) -> None:
        history: deque[dict[str, float]] = deque(maxlen=4)
        while True:
            try:
                await self._cycle(agent_id, history)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Agent %s cycle error: %s", agent_id, exc)
            await asyncio.sleep(10)

    async def _cycle(self, agent_id: str, history: deque) -> None:
        # 1. Fetch live prices
        try:
            from agents.price_engine import price_engine
            current_prices: dict[str, float] = price_engine.get_current_prices()
        except Exception:
            current_prices = {}

        if not current_prices:
            return

        history.append(dict(current_prices))

        if len(history) < 4:
            return

        # 2. Decide per token
        for sym in TOKEN_SYMBOLS:
            price_series = [tick.get(sym, 0.0) for tick in history]

            # CNN-LSTM inference (falls back to momentum)
            try:
                from agents.price_engine import price_engine as pe
                from ml.live_inference import ml_decision
                hist100 = pe.get_history(sym, 100)
                pred = ml_decision(sym, hist100, self.ml_model, self.ml_scaler)
                decision = pred.decision.upper()
                return_bps = int(pred.predicted_log_return * 10_000)
                logger.debug(
                    "Agent %s | %s | %s | pred=%.5f | conf=%.3f | src=%s",
                    agent_id, sym, decision,
                    pred.predicted_log_return, pred.confidence, pred.source,
                )
            except Exception as exc:
                logger.debug("ML inference skipped for %s/%s: %s — using momentum", agent_id, sym, exc)
                decision = _compute_decision(price_series)
                price_now = price_series[-1]
                price_old = price_series[0]
                return_bps = int(((price_now - price_old) / max(price_old, 1e-9)) * 10_000)

            if decision in ("BUY", "SELL"):
                await self._execute_trade(agent_id, sym, decision, return_bps, current_prices)

    async def _execute_trade(
        self,
        agent_id: str,
        sym: str,
        decision: str,
        return_bps: int,
        prices: dict[str, float],
    ) -> None:
        """
        1. Submit performance update to Stellar AllocationEngine (async off-thread).
        2. Report performance to SlashingModule.
        3. Broadcast simulated trade over WebSocket.
        """
        # Stellar contract calls (blocking I/O — run in thread pool)
        if self.stellar is not None:
            # Map agent_id to a Stellar address (use public_key as default)
            stellar_addr = self.stellar.public_key or ""
            if stellar_addr:
                try:
                    await asyncio.to_thread(
                        self.stellar.allocation_submit_update,
                        stellar_addr,
                        return_bps,
                    )
                    logger.debug("AllocationEngine.submit_update → agent=%s bps=%d", stellar_addr[:8], return_bps)
                except Exception as exc:
                    logger.debug("submit_update skipped: %s", exc)

                # Also report a simulated current portfolio value to slashing module
                try:
                    simulated_value = int(1_000_000 + return_bps * 100)  # in stroops
                    await asyncio.to_thread(
                        self.stellar.slashing_report_performance,
                        stellar_addr,
                        simulated_value,
                    )
                except Exception as exc:
                    logger.debug("report_performance skipped: %s", exc)

        # WebSocket broadcast
        amount_eth = int(0.01e18)  # 0.01 unit per trade
        price = prices.get(sym, 1.0)
        amount_out = int(amount_eth * price / 1e18 * 1e8)

        try:
            from api.ws_trading import broadcaster
            await broadcaster.broadcast({
                "agent":     agent_id,
                "token":     sym,
                "amountIn":  str(amount_eth),
                "amountOut": str(amount_out),
                "timestamp": int(time.time()),
                "type":      "swap",
                "decision":  decision,
                "returnBps": return_bps,
            })
            logger.info(
                "Agent %s | %s | %s | %.4f ETH -> %s | bps=%d",
                agent_id, sym, decision, amount_eth / 1e18, sym, return_bps,
            )
        except Exception as exc:
            logger.warning("broadcast failed: %s", exc)

    # ── read helpers (used by REST /portfolio endpoint) ────────────────────────

    def get_agent_allocation_weight(self, agent_id: str) -> float:
        """Return allocation weight as a fraction 0–1. Reads from Stellar if available."""
        if self.stellar and self.stellar.public_key:
            try:
                raw = self.stellar.vault_agent_weight(self.stellar.public_key)
                return raw / 1e18
            except Exception:
                pass
        return 0.0

    def get_pool_tvl_summary(self) -> dict[str, int]:
        """Returns {conservative, balanced, aggressive} TVLs from Stellar."""
        if self.stellar:
            try:
                return self.stellar.all_pool_tvls()
            except Exception:
                pass
        return {"conservative": 0, "balanced": 0, "aggressive": 0}
