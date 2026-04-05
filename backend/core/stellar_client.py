"""
Stellar Soroban client for IRIS Protocol.

Provides thin wrappers around the four deployed Soroban contracts:
  - AgentRegistry    (CDJD33R7ZVT7YZD2T6ROK2MPK2XRYJCKSM4AQOXPKCGMIQCAN7R6RTVJ)
  - AllocationEngine (CBBXJBG5Y74XBO7NSWUXNOZVEBWTBCEL6ZAPEXULASBIM3FSEZBRPPUV)
  - CapitalVault     (CB263OPPTMRE7R37CMIPSYWLDVVAR4UYWXQS7C6FY3AS6VBUEPHYX3H6)
  - SlashingModule   (CAHJFZI7IZSPAZK35LZLYNG564F3LPQZFDRRFXFUENVWGY7Q6OHE3U5I)

All public read methods call `simulate_transaction` (no signing required).
Write methods sign with the configured keypair and submit; they return the
transaction hash on success and None on failure.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Pool IDs (mirror Rust constants)
POOL_CONSERVATIVE = 0
POOL_BALANCED = 1
POOL_AGGRESSIVE = 2

# ─── lazy imports so the backend starts even if stellar-sdk is absent ─────────

def _stellar_available() -> bool:
    try:
        import stellar_sdk  # noqa: F401
        return True
    except ImportError:
        return False


def _build_scval_address(address_str: str):
    from stellar_sdk import scval, Address
    return scval.to_address(Address(address_str))


def _build_scval_i128(value: int):
    from stellar_sdk import scval
    return scval.to_int128(value)


def _build_scval_u32(value: int):
    from stellar_sdk import scval
    return scval.to_uint32(value)


def _build_scval_vec(items: list):
    """Wrap a Python list of SCVal objects into a Soroban Vec SCVal."""
    from stellar_sdk import scval
    return scval.to_vec(items)


class StellarContracts:
    """
    Manages Soroban contract interactions for all four IRIS Protocol contracts.

    Read calls use simulate_transaction (no keypair required).
    Write calls require STELLAR_SECRET_KEY to be set in the environment.
    """

    def __init__(
        self,
        rpc_url: str,
        horizon_url: str,
        network_passphrase: str,
        agent_registry: str,
        allocation_engine: str,
        capital_vault: str,
        slashing_module: str,
        secret_key: Optional[str] = None,
        public_key: Optional[str] = None,
    ):
        self.rpc_url = rpc_url
        self.horizon_url = horizon_url
        self.network_passphrase = network_passphrase
        self.agent_registry_id = agent_registry
        self.allocation_engine_id = allocation_engine
        self.capital_vault_id = capital_vault
        self.slashing_module_id = slashing_module
        self.secret_key = secret_key
        self.public_key = public_key
        self._server = None
        self._keypair = None

    # ── internal helpers ──────────────────────────────────────────────────────

    def _get_server(self):
        if self._server is None:
            from stellar_sdk import SorobanServer
            self._server = SorobanServer(self.rpc_url)
        return self._server

    def _get_keypair(self):
        if self._keypair is None and self.secret_key:
            from stellar_sdk import Keypair
            self._keypair = Keypair.from_secret(self.secret_key)
        return self._keypair

    def _simulate_call(self, contract_id: str, function_name: str, args: list) -> Any:
        """
        Simulate a read-only contract call and return the parsed result.
        Returns None on any error.
        """
        try:
            from stellar_sdk import SorobanServer, Network
            from stellar_sdk.transaction_builder import TransactionBuilder
            from stellar_sdk import Keypair, Account

            server = self._get_server()

            # Use a dummy keypair for simulation if no secret configured
            if self.secret_key:
                kp = self._get_keypair()
                source_pub = kp.public_key
            else:
                source_pub = self.public_key or "GAAZI4TCR3TY5OJHCTJC2A4QSY6CJWJH5IAJTGKIN2ER7LBNVKOCCWN"

            account = server.load_account(source_pub)
            tx = (
                TransactionBuilder(
                    source_account=account,
                    network_passphrase=self.network_passphrase,
                    base_fee=100,
                )
                .append_invoke_contract_function_op(
                    contract_id=contract_id,
                    function_name=function_name,
                    parameters=args,
                )
                .build()
            )

            response = server.simulate_transaction(tx)
            if response.error:
                logger.warning("simulate error %s::%s → %s", contract_id[:8], function_name, response.error)
                return None

            if response.results:
                from stellar_sdk import scval
                raw = response.results[0].xdr
                from stellar_sdk.xdr import SCVal
                import base64
                xdr_bytes = base64.b64decode(raw)
                sc_val = SCVal.from_xdr(xdr_bytes)
                return sc_val
            return None
        except Exception as exc:
            logger.debug("simulate %s::%s failed: %s", contract_id[:8], function_name, exc)
            return None

    def _invoke(self, contract_id: str, function_name: str, args: list) -> Optional[str]:
        """
        Sign and submit a state-changing transaction.
        Returns the transaction hash on success, None on failure.
        """
        kp = self._get_keypair()
        if kp is None:
            logger.warning("No STELLAR_SECRET_KEY — cannot invoke %s::%s", contract_id[:8], function_name)
            return None
        try:
            from stellar_sdk import SorobanServer, Network
            from stellar_sdk.transaction_builder import TransactionBuilder

            server = self._get_server()
            account = server.load_account(kp.public_key)
            tx = (
                TransactionBuilder(
                    source_account=account,
                    network_passphrase=self.network_passphrase,
                    base_fee=300,
                )
                .set_timeout(30)
                .append_invoke_contract_function_op(
                    contract_id=contract_id,
                    function_name=function_name,
                    parameters=args,
                )
                .build()
            )

            # Simulate first to get the auth + fee
            sim = server.simulate_transaction(tx)
            if sim.error:
                logger.warning("pre-flight error %s::%s → %s", contract_id[:8], function_name, sim.error)
                return None

            # Assemble + sign
            tx = server.prepare_transaction(tx, sim)
            tx.sign(kp)
            response = server.submit_transaction(tx)
            tx_hash = response.get("hash", "unknown")
            logger.info("Soroban %s::%s submitted → %s", contract_id[:8], function_name, tx_hash)
            return tx_hash
        except Exception as exc:
            logger.error("invoke %s::%s failed: %s", contract_id[:8], function_name, exc)
            return None

    # ── CapitalVault ──────────────────────────────────────────────────────────

    def vault_total_tvl(self) -> int:
        """Returns total TVL across all pools (7-decimal fixed point in contract)."""
        result = self._simulate_call(self.capital_vault_id, "total_tvl", [])
        if result is None:
            return 0
        try:
            return int(result.i128.lo) + (int(result.i128.hi) << 64)
        except Exception:
            return 0

    def vault_pool_tvl(self, pool: int) -> int:
        """TVL for a specific pool (0=conservative, 1=balanced, 2=aggressive)."""
        args = [_build_scval_u32(pool)]
        result = self._simulate_call(self.capital_vault_id, "get_pool_tvl", args)
        if result is None:
            return 0
        try:
            return int(result.i128.lo) + (int(result.i128.hi) << 64)
        except Exception:
            return 0

    def vault_investor_balance(self, investor_address: str, pool: int) -> int:
        args = [_build_scval_address(investor_address), _build_scval_u32(pool)]
        result = self._simulate_call(self.capital_vault_id, "get_investor_balance", args)
        if result is None:
            return 0
        try:
            return int(result.i128.lo) + (int(result.i128.hi) << 64)
        except Exception:
            return 0

    def vault_agent_weight(self, agent_address: str) -> int:
        """Weight in 1e18 fixed point (1e18 = 100% allocation)."""
        args = [_build_scval_address(agent_address)]
        result = self._simulate_call(self.capital_vault_id, "get_agent_weight", args)
        if result is None:
            return 0
        try:
            return int(result.i128.lo) + (int(result.i128.hi) << 64)
        except Exception:
            return 0

    def vault_agent_current_value(self, agent_address: str) -> int:
        args = [_build_scval_address(agent_address)]
        result = self._simulate_call(self.capital_vault_id, "get_agent_current_value", args)
        if result is None:
            return 0
        try:
            return int(result.i128.lo) + (int(result.i128.hi) << 64)
        except Exception:
            return 0

    def vault_deposit(self, investor_address: str, pool: int, amount: int) -> Optional[str]:
        """Deposit `amount` stroops into pool. Signs with STELLAR_SECRET_KEY."""
        args = [
            _build_scval_address(investor_address),
            _build_scval_u32(pool),
            _build_scval_i128(amount),
        ]
        return self._invoke(self.capital_vault_id, "deposit", args)

    # ── AgentRegistry ─────────────────────────────────────────────────────────

    def registry_get_active_agents(self) -> list[str]:
        """Returns list of active agent Stellar addresses."""
        result = self._simulate_call(self.agent_registry_id, "get_active_agents", [])
        if result is None:
            return []
        try:
            addresses = []
            # Handle vec of addresses
            if hasattr(result, "vec") and result.vec:
                for item in result.vec.sc_val:
                    try:
                        addr = item.address.account_id.account_id.ed25519
                        addresses.append(addr)
                    except Exception:
                        pass
            return addresses
        except Exception:
            return []

    def registry_activate_agent(self, agent_address: str) -> Optional[str]:
        """Activate a registered agent (moves from probation to active)."""
        args = [_build_scval_address(agent_address)]
        return self._invoke(self.agent_registry_id, "activate_agent", args)

    def registry_slash_agent(self, agent_address: str, slash_bps: int) -> Optional[str]:
        """Slash agent by slash_bps basis points (1–10000). Admin only."""
        from stellar_sdk import scval
        args = [
            _build_scval_address(agent_address),
            scval.to_uint32(slash_bps),
        ]
        return self._invoke(self.agent_registry_id, "slash_agent", args)

    # ── AllocationEngine ──────────────────────────────────────────────────────

    def allocation_get_agent_score(self, agent_address: str) -> int:
        args = [_build_scval_address(agent_address)]
        result = self._simulate_call(self.allocation_engine_id, "get_agent_score", args)
        if result is None:
            return 0
        try:
            return int(result.i128.lo) + (int(result.i128.hi) << 64)
        except Exception:
            return 0

    def allocation_submit_update(
        self,
        agent_addresses: list[str],
        scores: list[int],
        weights: list[int],
    ) -> Optional[str]:
        """
        Submit a batch epoch performance update.

        Matches the Soroban contract signature:
          submit_update(agents: Vec<Address>, scores: Vec<i128>, weights: Vec<i128>)

        agent_addresses: list of Stellar account addresses
        scores:   signed performance scores in basis points per agent
        weights:  allocation weights (fixed-point i128) per agent
        """
        if not (len(agent_addresses) == len(scores) == len(weights)):
            raise ValueError("agent_addresses, scores, and weights must have equal length")

        args = [
            _build_scval_vec([_build_scval_address(a) for a in agent_addresses]),
            _build_scval_vec([_build_scval_i128(s) for s in scores]),
            _build_scval_vec([_build_scval_i128(w) for w in weights]),
        ]
        return self._invoke(self.allocation_engine_id, "submit_update", args)

    def allocation_submit_single_update(
        self, agent_address: str, return_bps: int, weight: int = 0
    ) -> Optional[str]:
        """Convenience wrapper for a single-agent epoch update."""
        return self.allocation_submit_update(
            [agent_address], [return_bps], [weight]
        )

    def allocation_get_reputation_score(self, agent_address: str) -> int:
        args = [_build_scval_address(agent_address)]
        result = self._simulate_call(self.allocation_engine_id, "get_reputation_score", args)
        if result is None:
            return 0
        try:
            return int(result.i128.lo) + (int(result.i128.hi) << 64)
        except Exception:
            return 0

    # ── SlashingModule ────────────────────────────────────────────────────────

    def slashing_report_performance(self, agent_address: str, current_value: int) -> Optional[str]:
        """Report current portfolio value for an agent (triggers drawdown check)."""
        args = [
            _build_scval_address(agent_address),
            _build_scval_i128(current_value),
        ]
        return self._invoke(self.slashing_module_id, "report_performance", args)

    def slashing_get_slash_history(self, agent_address: str) -> list:
        args = [_build_scval_address(agent_address)]
        result = self._simulate_call(self.slashing_module_id, "get_slash_history", args)
        return [] if result is None else result

    # ── convenience: pool TVL summary ────────────────────────────────────────

    def all_pool_tvls(self) -> dict[str, int]:
        return {
            "conservative": self.vault_pool_tvl(POOL_CONSERVATIVE),
            "balanced":     self.vault_pool_tvl(POOL_BALANCED),
            "aggressive":   self.vault_pool_tvl(POOL_AGGRESSIVE),
        }


# ── factory ───────────────────────────────────────────────────────────────────

def build_stellar_client() -> Optional[StellarContracts]:
    """
    Build a StellarContracts instance from environment variables.
    Returns None if the required contract addresses are not configured or
    stellar-sdk is not installed.
    """
    if not _stellar_available():
        logger.warning("stellar-sdk not installed; Soroban integration disabled. Run: pip install stellar-sdk>=11.0.0")
        return None

    rpc_url = os.getenv("STELLAR_RPC_URL", "")
    agent_registry = os.getenv("STELLAR_AGENT_REGISTRY", "")
    allocation_engine = os.getenv("STELLAR_ALLOCATION_ENGINE", "")
    capital_vault = os.getenv("STELLAR_CAPITAL_VAULT", "")
    slashing_module = os.getenv("STELLAR_SLASHING_MODULE", "")

    if not all([rpc_url, agent_registry, allocation_engine, capital_vault, slashing_module]):
        logger.warning("Stellar contract addresses not fully configured; Soroban integration disabled.")
        return None

    secret_key = os.getenv("STELLAR_SECRET_KEY", "").strip() or None
    public_key = os.getenv("STELLAR_PUBLIC_KEY", "").strip() or None
    horizon_url = os.getenv("STELLAR_HORIZON_URL", "https://horizon-testnet.stellar.org")
    network_passphrase = os.getenv(
        "STELLAR_NETWORK_PASSPHRASE", "Test SDF Network ; September 2015"
    )

    client = StellarContracts(
        rpc_url=rpc_url,
        horizon_url=horizon_url,
        network_passphrase=network_passphrase,
        agent_registry=agent_registry,
        allocation_engine=allocation_engine,
        capital_vault=capital_vault,
        slashing_module=slashing_module,
        secret_key=secret_key,
        public_key=public_key,
    )

    mode = "read-write" if secret_key else "read-only (no STELLAR_SECRET_KEY)"
    logger.info(
        "Stellar Soroban client ready (%s) → vault=%s alloc=%s",
        mode,
        capital_vault[:12],
        allocation_engine[:12],
    )
    return client
