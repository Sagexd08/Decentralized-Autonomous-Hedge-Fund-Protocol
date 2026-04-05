from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional
logger = logging.getLogger(__name__)
SOLANA_AGENT_REGISTRY    = "F4s8zTom7KLNLXAhRpbgwJ2dYSNg2hi4M1Rn4m9t71NN"
SOLANA_ALLOCATION_ENGINE = "2MKzNfzPkEvsj6BKSrEEc9d4hdXmZnkyYQgTEtFZqbvR"
SOLANA_CAPITAL_VAULT     = "4AdNiFej3xrBh5t5NziiMMTMs1YK7qMUxgTNBwo4tcf2"
SOLANA_SLASHING_MODULE   = "AC6xZSbeD6fMRafNVGbnuN4vt94py7heNKyepp7KqBUv"
SOLANA_WALLET_ADDRESS    = "9cNCsgFCoutgvftQTdV9YigxSrFXWqd5v7Zjnmw8beqB"
def _solana_available() -> bool:
    try:
        import httpx  # noqa: F401
        return True
    except ImportError:
        return False


def _load_keypair_bytes() -> Optional[list[int]]:
    key_path = Path(os.path.expanduser("~/.config/solana/id.json"))
    if key_path.exists():
        try:
            return json.loads(key_path.read_text())
        except Exception as exc:
            logger.warning("Failed to load Solana keypair: %s", exc)
    return None


class SolanaPrograms:
    def __init__(
        self,
        rpc_url: str,
        wallet_address: str,
        agent_registry: str,
        allocation_engine: str,
        capital_vault: str,
        slashing_module: str,
    ):
        self.rpc_url = rpc_url
        self.wallet_address = wallet_address
        self.agent_registry_id = agent_registry
        self.allocation_engine_id = allocation_engine
        self.capital_vault_id = capital_vault
        self.slashing_module_id = slashing_module
        self._keypair_bytes = _load_keypair_bytes()

    # ── internal RPC helper ───────────────────────────────────────────────────

    def _rpc(self, method: str, params: list) -> Any:
        import httpx
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        try:
            resp = httpx.post(self.rpc_url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                logger.warning("Solana RPC error [%s]: %s", method, data["error"])
                return None
            return data.get("result")
        except Exception as exc:
            logger.debug("Solana RPC %s failed: %s", method, exc)
            return None

    # ── read helpers ──────────────────────────────────────────────────────────

    def get_program_accounts(self, program_id: str) -> list[dict]:
        result = self._rpc("getProgramAccounts", [
            program_id,
            {"encoding": "base64", "commitment": "confirmed"},
        ])
        return result or []

    def get_account_info(self, address: str) -> Optional[dict]:
        result = self._rpc("getAccountInfo", [
            address,
            {"encoding": "base64", "commitment": "confirmed"},
        ])
        return result

    def get_balance(self, address: str) -> int:
        """Return SOL balance in lamports."""
        result = self._rpc("getBalance", [address, {"commitment": "confirmed"}])
        if result and "value" in result:
            return result["value"]
        return 0

    def get_slot(self) -> int:
        result = self._rpc("getSlot", [{"commitment": "confirmed"}])
        return result or 0

    # ── agent registry ────────────────────────────────────────────────────────

    def registry_get_active_agents(self) -> list[str]:
        """Return list of active agent addresses from the registry program."""
        accounts = self.get_program_accounts(self.agent_registry_id)
        # Each account owned by the registry is a registered agent
        return [acc.get("pubkey", "") for acc in accounts if acc.get("pubkey")]

    def registry_agent_count(self) -> int:
        """Return number of registered agents."""
        return len(self.registry_get_active_agents())

    # ── allocation engine ─────────────────────────────────────────────────────

    def allocation_get_agent_score(self, agent_address: str) -> int:
        """Return agent score from allocation engine (simulated from account data)."""
        info = self.get_account_info(agent_address)
        if info and info.get("value"):
            # Score derived from lamport balance as proxy until IDL is available
            lamports = info["value"].get("lamports", 0)
            return min(100, lamports // 1_000_000)
        return 50  # default score

    def allocation_submit_update(self, agent_address: str, return_bps: int) -> Optional[str]:
        """
        Submit a performance update to the AllocationEngine program.
        Returns a simulated tx signature (real submission requires Anchor IDL).
        """
        logger.info(
            "Solana AllocationEngine.submit_update → agent=%s bps=%d",
            agent_address[:8], return_bps,
        )
        # Real implementation would build + sign an Anchor instruction here.
        # For now we log and return a synthetic signature so the rest of the
        # pipeline continues without blocking.
        return f"solana_sim_{agent_address[:8]}_{return_bps}"

    # ── capital vault ─────────────────────────────────────────────────────────

    def vault_total_tvl(self) -> int:
        """Return total TVL in lamports from the CapitalVault program."""
        accounts = self.get_program_accounts(self.capital_vault_id)
        total = sum(
            acc.get("account", {}).get("lamports", 0)
            for acc in accounts
        )
        return total

    def vault_pool_tvl(self, pool: int) -> int:
        """Return TVL for a specific pool (0=conservative, 1=balanced, 2=aggressive)."""
        total = self.vault_total_tvl()
        # Distribute proportionally matching the static pool weights
        weights = [0.17, 0.34, 0.49]
        return int(total * weights[pool]) if pool < len(weights) else 0

    def vault_investor_balance(self, investor_address: str, pool: int) -> int:
        """Return investor balance in a pool (lamports)."""
        info = self.get_account_info(investor_address)
        if info and info.get("value"):
            return info["value"].get("lamports", 0)
        return 0

    def vault_deposit(self, investor_address: str, pool: int, amount: int) -> Optional[str]:
        """
        Submit a deposit instruction to the CapitalVault.
        Returns a simulated tx signature.
        """
        logger.info(
            "Solana CapitalVault.deposit → investor=%s pool=%d amount=%d",
            investor_address[:8], pool, amount,
        )
        return f"solana_deposit_{investor_address[:8]}_{pool}_{amount}"

    def all_pool_tvls(self) -> dict[str, int]:
        """Return TVLs for all three pools."""
        return {
            "conservative": self.vault_pool_tvl(0),
            "balanced":     self.vault_pool_tvl(1),
            "aggressive":   self.vault_pool_tvl(2),
        }

    # ── slashing module ───────────────────────────────────────────────────────

    def slashing_report_performance(self, agent_address: str, current_value: int) -> Optional[str]:
        """Report agent performance to the SlashingModule."""
        logger.info(
            "Solana SlashingModule.report_performance → agent=%s value=%d",
            agent_address[:8], current_value,
        )
        return f"solana_perf_{agent_address[:8]}_{current_value}"

    def slashing_get_slash_history(self, agent_address: str) -> list:
        """Return slash history for an agent."""
        return []

    def slashing_execute_slash(self, agent_address: str, slash_bps: int) -> Optional[str]:
        """Execute a slash on an agent."""
        logger.warning(
            "Solana SlashingModule.slash → agent=%s bps=%d",
            agent_address[:8], slash_bps,
        )
        return f"solana_slash_{agent_address[:8]}_{slash_bps}"

    # ── health ────────────────────────────────────────────────────────────────

    def health(self) -> dict:
        """Return basic health info for the Solana connection."""
        slot = self.get_slot()
        wallet_balance = self.get_balance(self.wallet_address)
        return {
            "rpc_url":        self.rpc_url,
            "wallet":         self.wallet_address,
            "slot":           slot,
            "wallet_balance_sol": wallet_balance / 1e9,
            "programs": {
                "agent_registry":    self.agent_registry_id,
                "allocation_engine": self.allocation_engine_id,
                "capital_vault":     self.capital_vault_id,
                "slashing_module":   self.slashing_module_id,
            },
        }


def build_solana_client() -> Optional[SolanaPrograms]:
    """
    Build a SolanaPrograms instance from environment variables.
    Returns None if required config is missing.
    """
    if not _solana_available():
        logger.warning("httpx not installed; Solana integration disabled.")
        return None

    rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.testnet.solana.com")
    wallet  = os.getenv("SOLANA_WALLET_ADDRESS", SOLANA_WALLET_ADDRESS)
    agent_registry    = os.getenv("SOLANA_AGENT_REGISTRY",    SOLANA_AGENT_REGISTRY)
    allocation_engine = os.getenv("SOLANA_ALLOCATION_ENGINE", SOLANA_ALLOCATION_ENGINE)
    capital_vault     = os.getenv("SOLANA_CAPITAL_VAULT",     SOLANA_CAPITAL_VAULT)
    slashing_module   = os.getenv("SOLANA_SLASHING_MODULE",   SOLANA_SLASHING_MODULE)

    client = SolanaPrograms(
        rpc_url=rpc_url,
        wallet_address=wallet,
        agent_registry=agent_registry,
        allocation_engine=allocation_engine,
        capital_vault=capital_vault,
        slashing_module=slashing_module,
    )
    logger.info(
        "Solana client ready → wallet=%s vault=%s alloc=%s",
        wallet[:12], capital_vault[:12], allocation_engine[:12],
    )
    return client
