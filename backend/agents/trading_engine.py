"""
AgentTradingEngine: manages one asyncio Task per active agent.
Each task: updatePrices → fetch prices → compute momentum → execute trade → sleep 10s.
"""
import asyncio
import json
import logging
import os
from collections import deque
from pathlib import Path
from typing import Any, Optional

try:
    from web3 import Web3
    from eth_account import Account
    from eth_account.signers.local import LocalAccount
except Exception:
    Web3 = Any
    Account = None
    LocalAccount = Any

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "contracts" / "config.json"

def _load_token_addresses() -> dict[str, str]:
    """Load token addresses from deployed config.json."""
    try:
        with open(_CONFIG_PATH) as f:
            cfg = json.load(f)
        return {
            "WBTC": cfg.get("WBTC", ""),
            "USDC": cfg.get("USDC", ""),
            "LINK": cfg.get("LINK", ""),
            "UNI":  cfg.get("UNI", ""),
        }
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("config.json not found or invalid; TOKEN_ADDRESSES will be empty")
        return {}

TOKEN_ADDRESSES: dict[str, str] = _load_token_addresses()

TOKEN_SYMBOL: dict[str, str] = {v: k for k, v in TOKEN_ADDRESSES.items() if v}

def _compute_decision(price_history: list[float]) -> str:
    """
    Compute momentum trading decision from a 4-element price history.
    Returns 'buy', 'sell', or 'hold'.
    """
    if len(price_history) < 4:
        return "hold"
    price_now = price_history[-1]
    price_3_ago = price_history[0]
    if price_3_ago == 0:
        return "hold"
    momentum = (price_now - price_3_ago) / price_3_ago
    if momentum > 0.005:
        return "buy"
    elif momentum < -0.005:
        return "sell"
    return "hold"

class AgentTradingEngine:
    """
    Manages one asyncio Task per active agent.
    Each task: fetch prices → CNN-LSTM inference → execute trade → sleep 10s.

    If ml_model / ml_scaler are None the engine falls back to the pure-math
    momentum signal so the system degrades gracefully when the model is absent.
    """

    def __init__(
        self,
        w3: Web3,
        vault_contract,
        price_feed_contract,
        accounts: list[LocalAccount],
        ml_model=None,
        ml_scaler=None,
    ):
        self.w3 = w3
        self.vault = vault_contract
        self.price_feed = price_feed_contract
        self.accounts = accounts
        self.ml_model = ml_model
        self.ml_scaler = ml_scaler
        self._tasks: dict[str, asyncio.Task] = {}

    async def start(self, agent_id: str) -> None:
        """Launch trading loop for agent_id. Raises ValueError if already running."""
        if self.is_trading(agent_id):
            raise ValueError(f"Agent {agent_id} is already trading")
        task = asyncio.create_task(self._trading_loop(agent_id))
        self._tasks[agent_id] = task

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

    def is_trading(self, agent_id: str) -> bool:
        task = self._tasks.get(agent_id)
        return task is not None and not task.done()

    async def _trading_loop(self, agent_id: str) -> None:
        history: deque[dict[str, int]] = deque(maxlen=4)
        while True:
            try:
                await self._cycle(agent_id, history)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Agent {agent_id} cycle error: {e}")
            await asyncio.sleep(10)

    async def _cycle(self, agent_id: str, history: deque) -> None:

        if self.price_feed is not None:
            await self._send_tx(agent_id, self.price_feed.functions.updatePrices())

        try:
            from agents.price_engine import price_engine
            current_prices = price_engine.get_current_prices()
        except Exception:
            current_prices = {}

        if not current_prices and self.price_feed is not None:
            for sym, addr in TOKEN_ADDRESSES.items():
                if addr:
                    try:
                        raw = self.price_feed.functions.getPrice(addr).call()
                        current_prices[sym] = raw / 1e8
                    except Exception:
                        pass

        if not current_prices:
            return

        prices_int = {sym: int(p * 1e8) for sym, p in current_prices.items()}
        history.append(prices_int)

        if len(history) >= 4:
            for sym, addr in TOKEN_ADDRESSES.items():
                if not addr:
                    continue

                # --- CNN-LSTM inference (falls back to momentum if unavailable) ---
                try:
                    from agents.price_engine import price_engine
                    from ml.live_inference import ml_decision
                    price_hist = price_engine.get_history(sym, 100)
                    live_pred = ml_decision(sym, price_hist, self.ml_model, self.ml_scaler)
                    decision = live_pred.decision
                    logger.debug(
                        "Agent %s | %s | %s | pred=%.5f | conf=%.3f | src=%s",
                        agent_id, sym, decision,
                        live_pred.predicted_log_return,
                        live_pred.confidence,
                        live_pred.source,
                    )
                except Exception as e:
                    logger.warning("ML inference error for %s/%s: %s — using momentum", agent_id, sym, e)
                    price_series = [tick.get(sym, 0) for tick in history]
                    decision = _compute_decision(price_series).upper()

                await self._apply_momentum(agent_id, sym, addr, decision)

    async def _apply_momentum(
        self, agent_id: str, sym: str, token_addr: str, decision: str
    ) -> None:
        account = self._account_for(agent_id)
        allocation = self._remaining_allocation(agent_id)
        slice_wei = allocation // 10

        if decision in ("buy", "BUY") and slice_wei > 0:

            success = await self._try_on_chain_swap(agent_id, token_addr, slice_wei)
            if not success:

                await self._broadcast_simulated_trade(agent_id, sym, slice_wei, "swap")

        elif decision in ("sell", "SELL"):

            sell_amount = int(0.05e18)
            await self._broadcast_simulated_trade(agent_id, sym, sell_amount, "swap")

    async def _try_on_chain_swap(self, agent_id: str, token_addr: str, amount_wei: int) -> bool:
        """Attempt on-chain swap. Returns True if successful."""
        if self.vault is None:
            return False
        account = self._account_for(agent_id)
        try:
            tx = self.vault.functions.executeSwap(token_addr, amount_wei, 0).build_transaction({
                "from": account.address,
                "value": amount_wei,
                "nonce": self.w3.eth.get_transaction_count(account.address),
                "gas": 300_000,
            })
            signed = account.sign_transaction(tx)
            self.w3.eth.send_raw_transaction(signed.raw_transaction)
            logger.info(f"Agent {agent_id} on-chain swap: {amount_wei} wei → {token_addr}")
            return True
        except Exception as e:
            logger.debug(f"On-chain swap failed (will simulate): {e}")
            return False

    async def _broadcast_simulated_trade(
        self, agent_id: str, sym: str, amount_wei: int, trade_type: str
    ) -> None:
        """Broadcast a simulated trade event directly to WebSocket clients."""
        try:
            from api.ws_trading import broadcaster
            from agents.price_engine import price_engine
            prices = price_engine.get_current_prices()
            price = prices.get(sym, 1.0)

            amount_out = int(amount_wei * price / 1e18 * 1e8)
            import time
            await broadcaster.broadcast({
                "agent":     self._account_for(agent_id).address,
                "token":     sym,
                "amountIn":  str(amount_wei),
                "amountOut": str(amount_out),
                "timestamp": int(time.time()),
                "type":      trade_type,
            })
            logger.info(f"Agent {agent_id} simulated {trade_type}: {amount_wei/1e18:.4f} ETH → {sym}")
        except Exception as e:
            logger.warning(f"Failed to broadcast simulated trade: {e}")

    async def _send_tx(self, agent_id: str, fn, value: int = 0) -> None:
        account = self._account_for(agent_id)
        try:
            tx = fn.build_transaction({
                "from": account.address,
                "value": value,
                "nonce": self.w3.eth.get_transaction_count(account.address),
                "gas": 300_000,
            })
            signed = account.sign_transaction(tx)
            self.w3.eth.send_raw_transaction(signed.raw_transaction)
        except Exception as e:
            logger.warning(f"Agent {agent_id} tx reverted or failed: {e}")

    def _account_for(self, agent_id: str) -> LocalAccount:
        """Derive account slot from agent_id hex string."""
        try:
            slot = int(agent_id, 16) % len(self.accounts)
        except (ValueError, TypeError):
            slot = hash(agent_id) % len(self.accounts)
        return self.accounts[slot]

    def _remaining_allocation(self, agent_id: str) -> int:
        """Read remaining allocation from chain using delegation params."""
        account = self._account_for(agent_id)
        try:
            deployed = self.vault.functions.agentDeployedWei(account.address).call()

            max_alloc = int(10e18)
            return max(0, max_alloc - deployed)
        except Exception as e:
            logger.warning(f"Failed to read allocation for {agent_id}: {e}")
            return int(1e18)
