from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.stellar_client import StellarContracts
    from core.solana_client import SolanaPrograms

logger = logging.getLogger(__name__)

TOKEN_SYMBOLS = ["WBTC", "USDC", "LINK", "UNI"]
POOL_IDS = {"conservative": 0, "balanced": 1, "aggressive": 2}
MAX_DRAWDOWN_BPS = 2000  # 20% auto-slash threshold


def _compute_decision(price_history: list[float]) -> str:
    if len(price_history) < 4:
        return "HOLD"
    price_now = price_history[-1]
    price_old = price_history[0]
    if price_old == 0:
        return "HOLD"
    momentum = (price_now - price_old) / price_old
    if momentum > 0.0005:
        return "BUY"
    elif momentum < -0.0005:
        return "SELL"
    return "HOLD"


class AgentTradingEngine:
    def __init__(
        self,
        stellar: Optional["StellarContracts"] = None,
        solana: Optional["SolanaPrograms"] = None,
        ml_model=None,
        ml_scaler=None,
    ):
        self.stellar = stellar
        self.solana = solana
        self.ml_model = ml_model
        self.ml_scaler = ml_scaler
        self._tasks: dict[str, asyncio.Task] = {}
        self._peak_values: dict[str, float] = {}
        self._agent_returns: dict[str, list[int]] = {}

    async def start(self, agent_id: str) -> None:
        if self.is_trading(agent_id):
            raise ValueError(f"Agent {agent_id} is already trading")
        task = asyncio.create_task(self._trading_loop(agent_id))
        self._tasks[agent_id] = task
        logger.info("Trading started for agent %s", agent_id)

    async def stop(self, agent_id: str) -> None:
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

    def active_agents(self) -> list[str]:
        return [aid for aid in self._tasks if self.is_trading(aid)]

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

        total_return_bps = 0
        for sym in TOKEN_SYMBOLS:
            price_series = [tick.get(sym, 0.0) for tick in history]
            try:
                from agents.price_engine import price_engine as pe
                from ml.live_inference import ml_decision
                # Use longer history from price engine for better signal
                hist100 = pe.get_history(sym, 100)
                pred = ml_decision(sym, hist100, self.ml_model, self.ml_scaler)
                decision = pred.decision.upper()
                return_bps = int(pred.predicted_log_return * 10_000)
            except Exception as exc:
                logger.debug("ML inference skipped for %s/%s: %s", agent_id, sym, exc)
                # Use price engine history for momentum (more data = better signal)
                try:
                    from agents.price_engine import price_engine as pe
                    long_hist = pe.get_history(sym, 20)
                    decision = _compute_decision(long_hist[-4:] if len(long_hist) >= 4 else long_hist)
                    price_now = long_hist[-1] if long_hist else price_series[-1]
                    price_old = long_hist[0]  if long_hist else price_series[0]
                    return_bps = int(((price_now - price_old) / max(price_old, 1e-9)) * 10_000)
                except Exception:
                    decision = _compute_decision(price_series)
                    price_now = price_series[-1]
                    price_old = price_series[0]
                    return_bps = int(((price_now - price_old) / max(price_old, 1e-9)) * 10_000)

            total_return_bps += return_bps
            logger.debug("Agent %s | %s | decision=%s bps=%d", agent_id, sym, decision, return_bps)
            if decision in ("BUY", "SELL"):
                await self._execute_trade(agent_id, sym, decision, return_bps, current_prices)

        if agent_id not in self._agent_returns:
            self._agent_returns[agent_id] = []
        self._agent_returns[agent_id].append(total_return_bps)

        await self._check_drawdown(agent_id, total_return_bps)

        if len(self._agent_returns[agent_id]) % 6 == 0:
            await self._push_mwu_weights()

    async def _execute_trade(
        self,
        agent_id: str,
        sym: str,
        decision: str,
        return_bps: int,
        prices: dict[str, float],
    ) -> None:
        stellar_addr = (self.stellar.public_key or "") if self.stellar else ""
        solana_addr  = (self.solana.wallet_address or "") if self.solana else ""
        simulated_value = int(1_000_000 + return_bps * 100)

        # Stellar
        if self.stellar and stellar_addr:
            try:
                await asyncio.to_thread(self.stellar.allocation_submit_update, stellar_addr, return_bps)
            except Exception as exc:
                logger.debug("Stellar submit_update skipped: %s", exc)
            try:
                await asyncio.to_thread(self.stellar.slashing_report_performance, stellar_addr, simulated_value)
            except Exception as exc:
                logger.debug("Stellar report_performance skipped: %s", exc)

        # Solana
        if self.solana and solana_addr:
            try:
                await asyncio.to_thread(self.solana.allocation_submit_update, solana_addr, return_bps)
            except Exception as exc:
                logger.debug("Solana submit_update skipped: %s", exc)
            try:
                await asyncio.to_thread(self.solana.slashing_report_performance, solana_addr, simulated_value)
            except Exception as exc:
                logger.debug("Solana report_performance skipped: %s", exc)

        # WebSocket broadcast
        amount_eth = int(0.01e18)
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
                "chains": {
                    "stellar": stellar_addr[:12] if stellar_addr else None,
                    "solana":  solana_addr[:12] if solana_addr else None,
                },
            })
            logger.info("Agent %s | %s | %s | bps=%d", agent_id, sym, decision, return_bps)
        except Exception as exc:
            logger.warning("broadcast failed: %s", exc)

    async def _check_drawdown(self, agent_id: str, return_bps: int) -> None:
        base_value = 1_000_000.0
        current_value = base_value + return_bps * 100
        peak = self._peak_values.get(agent_id, base_value)
        if current_value > peak:
            self._peak_values[agent_id] = current_value
            peak = current_value
        if peak > 0:
            drawdown_bps = int((peak - current_value) / peak * 10_000)
            if drawdown_bps >= MAX_DRAWDOWN_BPS:
                logger.warning("Agent %s drawdown %d bps — auto-slashing", agent_id, drawdown_bps)
                await self._auto_slash(agent_id, drawdown_bps)

    async def _auto_slash(self, agent_id: str, drawdown_bps: int) -> None:
        stellar_addr = (self.stellar.public_key or "") if self.stellar else ""
        solana_addr  = (self.solana.wallet_address or "") if self.solana else ""
        slash_bps = min(drawdown_bps // 2, 1000)

        if self.stellar and stellar_addr:
            try:
                await asyncio.to_thread(self.stellar.registry_slash_agent, stellar_addr, slash_bps)
                logger.warning("Stellar slash → agent=%s bps=%d", stellar_addr[:8], slash_bps)
            except Exception as exc:
                logger.debug("Stellar slash skipped: %s", exc)

        if self.solana and solana_addr:
            try:
                await asyncio.to_thread(self.solana.slashing_execute_slash, solana_addr, slash_bps)
                logger.warning("Solana slash → agent=%s bps=%d", solana_addr[:8], slash_bps)
            except Exception as exc:
                logger.debug("Solana slash skipped: %s", exc)

        try:
            from api.ws_trading import broadcaster
            await broadcaster.broadcast({
                "type":         "slash_event",
                "agent_id":     agent_id,
                "drawdown_bps": drawdown_bps,
                "slash_bps":    slash_bps,
                "timestamp":    int(time.time()),
            })
        except Exception:
            pass

    async def _push_mwu_weights(self) -> None:
        active = self.active_agents()
        if not active:
            return
        try:
            import numpy as np
            from core.allocation import AllocationEngine

            n = len(active)
            engine = AllocationEngine(n_agents=n)
            raw_returns = np.zeros(n)
            volatilities = np.ones(n) * 0.1
            drawdowns = np.zeros(n)

            for i, aid in enumerate(active):
                returns = self._agent_returns.get(aid, [0])[-20:]
                if returns:
                    raw_returns[i] = float(np.mean(returns)) / 10_000
                    volatilities[i] = max(float(np.std(returns)) / 10_000, 0.001)
                    min_r = min(returns)
                    max_r = max(returns) if max(returns) != 0 else 1
                    drawdowns[i] = abs(min_r / max_r) if max_r != 0 else 0

            weights = engine.step(raw_returns, volatilities, drawdowns)
            logger.info("MWU weights: %s", dict(zip(active, [round(w, 4) for w in weights.tolist()])))

            stellar_addr = (self.stellar.public_key or "") if self.stellar else ""
            solana_addr  = (self.solana.wallet_address or "") if self.solana else ""

            for i, aid in enumerate(active):
                bps = int(raw_returns[i] * 10_000)
                if self.stellar and stellar_addr:
                    try:
                        await asyncio.to_thread(self.stellar.allocation_submit_update, stellar_addr, bps)
                    except Exception:
                        pass
                if self.solana and solana_addr:
                    try:
                        await asyncio.to_thread(self.solana.allocation_submit_update, solana_addr, bps)
                    except Exception:
                        pass

            try:
                from api.ws_trading import broadcaster
                await broadcaster.broadcast({
                    "type":      "mwu_update",
                    "weights":   dict(zip(active, weights.tolist())),
                    "timestamp": int(time.time()),
                })
            except Exception:
                pass

        except Exception as exc:
            logger.error("MWU weight push failed: %s", exc)

    def get_agent_allocation_weight(self, agent_id: str) -> float:
        if self.stellar and self.stellar.public_key:
            try:
                raw = self.stellar.vault_agent_weight(self.stellar.public_key)
                return raw / 1e18
            except Exception:
                pass
        if self.solana and self.solana.wallet_address:
            try:
                score = self.solana.allocation_get_agent_score(self.solana.wallet_address)
                return score / 100.0
            except Exception:
                pass
        return 0.0

    def get_pool_tvl_summary(self) -> dict[str, int]:
        stellar_tvls: dict[str, int] = {}
        solana_tvls: dict[str, int] = {}
        if self.stellar:
            try:
                stellar_tvls = self.stellar.all_pool_tvls()
            except Exception:
                pass
        if self.solana:
            try:
                solana_tvls = self.solana.all_pool_tvls()
            except Exception:
                pass
        pools = ["conservative", "balanced", "aggressive"]
        return {p: stellar_tvls.get(p, 0) + solana_tvls.get(p, 0) for p in pools}
