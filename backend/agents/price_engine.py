"""
Price simulation engine: generates realistic asset prices using mean-reverting GBM.
Broadcasts live prices and agent predictions over WebSocket.
"""
import asyncio
import json
import logging
import math
import random
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Initial prices in USD (scaled 1e8 on-chain, but we work in float here)
INITIAL_PRICES: dict[str, float] = {
    "WBTC": 30000.0,
    "USDC": 1.0,
    "LINK": 15.0,
    "UNI":  8.0,
}

# Mean-reversion parameters per token
# theta = speed of mean reversion, sigma = volatility
PARAMS: dict[str, dict] = {
    "WBTC": {"theta": 0.05, "sigma": 0.018, "mu": 30000.0},
    "USDC": {"theta": 0.8,  "sigma": 0.001, "mu": 1.0},
    "LINK": {"theta": 0.08, "sigma": 0.025, "mu": 15.0},
    "UNI":  {"theta": 0.07, "sigma": 0.022, "mu": 8.0},
}

# Price bounds: [50%, 200%] of initial
PRICE_BOUNDS = {sym: (p * 0.5, p * 2.0) for sym, p in INITIAL_PRICES.items()}


@dataclass
class PricePoint:
    symbol: str
    price: float
    change_pct: float
    timestamp: float


@dataclass
class AgentPrediction:
    agent_id: str
    symbol: str
    current_price: float
    predicted_change_pct: float
    momentum: float
    decision: str  # "BUY" | "SELL" | "HOLD"
    confidence: float  # 0-1
    reasoning: str


class PriceEngine:
    """
    Simulates realistic asset prices using Ornstein-Uhlenbeck (mean-reverting) process.
    Runs independently of the blockchain — provides the "market data" layer.
    """

    def __init__(self, tick_interval: float = 3.0):
        self.tick_interval = tick_interval
        self._prices: dict[str, float] = dict(INITIAL_PRICES)
        self._history: dict[str, deque] = {
            sym: deque([p] * 20, maxlen=100)
            for sym, p in INITIAL_PRICES.items()
        }
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q) if hasattr(self._subscribers, 'discard') else None
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def get_current_prices(self) -> dict[str, float]:
        return dict(self._prices)

    def get_history(self, symbol: str, n: int = 20) -> list[float]:
        return list(self._history[symbol])[-n:]

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        while self._running:
            try:
                tick_data = self._tick()
                await self._broadcast(tick_data)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"PriceEngine tick error: {e}")
            await asyncio.sleep(self.tick_interval)

    def _tick(self) -> list[dict]:
        """Advance prices one step using Ornstein-Uhlenbeck process."""
        results = []
        dt = self.tick_interval / (365 * 24 * 3600)  # fraction of year

        for sym, price in self._prices.items():
            p = PARAMS[sym]
            theta = p["theta"]
            sigma = p["sigma"]
            mu = p["mu"]

            # OU process: dX = theta*(mu - X)*dt + sigma*sqrt(dt)*dW
            dW = random.gauss(0, 1)
            drift = theta * (mu - price) * dt
            diffusion = sigma * price * math.sqrt(dt) * dW
            new_price = price + drift + diffusion

            # Clamp to bounds
            lo, hi = PRICE_BOUNDS[sym]
            new_price = max(lo, min(hi, new_price))

            change_pct = (new_price - price) / price * 100
            self._prices[sym] = new_price
            self._history[sym].append(new_price)

            results.append({
                "type": "price",
                "symbol": sym,
                "price": round(new_price, 6),
                "change_pct": round(change_pct, 4),
                "timestamp": asyncio.get_event_loop().time(),
            })

        return results

    async def _broadcast(self, tick_data: list[dict]) -> None:
        dead = []
        for q in self._subscribers:
            try:
                for item in tick_data:
                    q.put_nowait(item)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass


def compute_agent_prediction(
    agent_id: str,
    symbol: str,
    price_history: list[float],
    current_price: float,
) -> AgentPrediction:
    """
    Compute agent's ML-based prediction for a token.
    Uses momentum + mean-reversion signals combined with MWU weighting.
    """
    if len(price_history) < 4:
        return AgentPrediction(
            agent_id=agent_id, symbol=symbol,
            current_price=current_price, predicted_change_pct=0.0,
            momentum=0.0, decision="HOLD", confidence=0.5,
            reasoning="Insufficient price history"
        )

    # 1. Short-term momentum (3-period)
    momentum_3 = (price_history[-1] - price_history[-4]) / price_history[-4]

    # 2. Medium-term momentum (10-period)
    n = min(10, len(price_history))
    momentum_10 = (price_history[-1] - price_history[-n]) / price_history[-n]

    # 3. Mean reversion signal
    mu = INITIAL_PRICES.get(symbol, current_price)
    reversion = (mu - current_price) / mu  # positive = below mean, expect rise

    # 4. Volatility (std of last 10 returns)
    returns = [
        (price_history[i] - price_history[i-1]) / price_history[i-1]
        for i in range(max(1, len(price_history)-10), len(price_history))
    ]
    volatility = (sum(r**2 for r in returns) / len(returns)) ** 0.5 if returns else 0.01

    # 5. Combined signal (MWU-style weighted combination)
    signal = 0.5 * momentum_3 + 0.3 * momentum_10 + 0.2 * reversion

    # 6. Confidence based on signal strength vs volatility
    confidence = min(0.95, abs(signal) / (volatility + 1e-6) * 0.1)
    confidence = max(0.1, confidence)

    # 7. Decision
    threshold = 0.003
    if signal > threshold:
        decision = "BUY"
        predicted_change = signal * 100
    elif signal < -threshold:
        decision = "SELL"
        predicted_change = signal * 100
    else:
        decision = "HOLD"
        predicted_change = signal * 100

    # 8. Human-readable reasoning
    parts = []
    if abs(momentum_3) > 0.002:
        direction = "upward" if momentum_3 > 0 else "downward"
        parts.append(f"short-term {direction} momentum ({momentum_3*100:+.2f}%)")
    if abs(reversion) > 0.01:
        direction = "below" if reversion > 0 else "above"
        parts.append(f"price {direction} mean by {abs(reversion)*100:.1f}%")
    if not parts:
        parts.append("neutral market conditions")
    reasoning = f"MWU signal: {', '.join(parts)}"

    return AgentPrediction(
        agent_id=agent_id,
        symbol=symbol,
        current_price=round(current_price, 4),
        predicted_change_pct=round(predicted_change, 3),
        momentum=round(momentum_3 * 100, 3),
        decision=decision,
        confidence=round(confidence, 3),
        reasoning=reasoning,
    )


# Global singleton
price_engine = PriceEngine(tick_interval=3.0)
