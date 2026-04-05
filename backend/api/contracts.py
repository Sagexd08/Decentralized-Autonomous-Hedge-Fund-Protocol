"""
Contracts API — serves real Solidity source, explanations, and user-submitted contracts.
"""
import json
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_CONTRACTS_DIR = Path(__file__).parent.parent.parent / "contracts"
_SUBMISSIONS_PATH = Path(__file__).parent.parent / "contract_submissions.json"

# Stellar (Soroban) deployed contract addresses
_STELLAR_ADDRESSES = {
    "agent-registry":    "CDJD33R7ZVT7YZD2T6ROK2MPK2XRYJCKSM4AQOXPKCGMIQCAN7R6RTVJ",
    "allocation-engine": "CBBXJBG5Y74XBO7NSWUXNOZVEBWTBCEL6ZAPEXULASBIM3FSEZBRPPUV",
    "capital-vault":     "CB263OPPTMRE7R37CMIPSYWLDVVAR4UYWXQS7C6FY3AS6VBUEPHYX3H6",
    "slashing-module":   "CAHJFZI7IZSPAZK35LZLYNG564F3LPQZFDRRFXFUENVWGY7Q6OHE3U5I",
}

# Solana (testnet) deployed program IDs
_SOLANA_PROGRAM_IDS = {
    "agent-registry":    "F4s8zTom7KLNLXAhRpbgwJ2dYSNg2hi4M1Rn4m9t71NN",
    "allocation-engine": "2MKzNfzPkEvsj6BKSrEEc9d4hdXmZnkyYQgTEtFZqbvR",
    "capital-vault":     "4AdNiFej3xrBh5t5NziiMMTMs1YK7qMUxgTNBwo4tcf2",
    "slashing-module":   "AC6xZSbeD6fMRafNVGbnuN4vt94py7heNKyepp7KqBUv",
}

_BUILTIN = [
    {
        "id": "capital-vault",
        "name": "CapitalVault",
        "version": "v2.1",
        "address": "0xCAfEBAbECAFEBABEcafebabeCAfEBAbEcafebabe",
        "stellar_address": _STELLAR_ADDRESSES["capital-vault"],
        "solana_program_id": _SOLANA_PROGRAM_IDS["capital-vault"],
        "status": "deployed",
        "audited": True,
        "tvl": 25300000,
        "source_file": "src/CapitalVault.sol",
        "explanation": (
            "The CapitalVault is the core custody layer of IRIS Protocol. It holds all investor funds across three risk pools "
            "(Conservative 8% vol cap, Balanced 18%, Aggressive 35%). Agents never directly control capital — they only "
            "receive normalized weight allocations. The vault enforces a 20% max drawdown ceiling per agent and a 10% "
            "performance fee. Deposits and withdrawals are protected by OpenZeppelin's ReentrancyGuard. Weight updates "
            "can only be submitted by the authorized AllocationEngine address, and slashing can only be triggered by "
            "the SlashingModule, creating a strict separation of concerns."
        ),
        "key_functions": [
            {"name": "deposit(uint8 pool, uint256 amount)", "desc": "Investor deposits into a risk pool"},
            {"name": "withdraw(uint8 pool, uint256 amount)", "desc": "Investor withdraws from a risk pool"},
            {"name": "updateWeights(address[], uint256[])", "desc": "Allocation engine submits MWU weights"},
            {"name": "enforceDrawdownLimit(address agent)", "desc": "Slashing module zeroes out breaching agent"},
        ],
        "events": ["Deposited", "Withdrawn", "WeightsUpdated", "DrawdownBreached", "RiskLimitEnforced"],
        "submitted_by": None,
    },
    {
        "id": "allocation-engine",
        "name": "AllocationEngine",
        "version": "v1.4",
        "address": "0xDeAdBeEFdeadbeefDeadBeefDeAdBeEFDeAdbEEf",
        "stellar_address": _STELLAR_ADDRESSES["allocation-engine"],
        "solana_program_id": _SOLANA_PROGRAM_IDS["allocation-engine"],
        "status": "deployed",
        "audited": True,
        "tvl": 0,
        "source_file": "src/AllocationEngine.sol",
        "explanation": (
            "The AllocationEngine stores on-chain weight state for the Multiplicative Weights Update (MWU) algorithm. "
            "The actual MWU computation — w_i(t+1) = w_i(t) * exp(η * R_i(t)) — runs off-chain in Python for gas "
            "efficiency, then the normalized results are submitted here and forwarded to the CapitalVault. "
            "The learning rate η (default 0.01, range 0.001–0.05) controls how fast the engine adapts to agent "
            "performance. Reputation scores use exponential decay: score = 0.3 * recent + 0.7 * historical, "
            "preventing short-term manipulation. The regret bound is O(√T · ln N) vs the best fixed agent."
        ),
        "key_functions": [
            {"name": "submitUpdate(address[], int256[], uint256[])", "desc": "Submit MWU scores and weights"},
            {"name": "setEta(uint256 _eta)", "desc": "Update learning rate (governance controlled)"},
            {"name": "_updateReputation(address, int256)", "desc": "Exponential decay reputation update"},
        ],
        "events": ["EtaUpdated", "ScoresSubmitted", "ReputationUpdated"],
        "submitted_by": None,
    },
    {
        "id": "agent-registry",
        "name": "AgentRegistry",
        "version": "v1.0",
        "address": "0xBEEFBEEFbeefbeefBEEFBEEFbeefbeefBEEFBEEF",
        "stellar_address": _STELLAR_ADDRESSES["agent-registry"],
        "solana_program_id": _SOLANA_PROGRAM_IDS["agent-registry"],
        "status": "deployed",
        "audited": True,
        "tvl": 0,
        "source_file": "src/AgentRegistry.sol",
        "explanation": (
            "The AgentRegistry manages the full agent lifecycle: registration, probation, activation, slashing, and "
            "deregistration. Anti-sybil protection requires a minimum stake of 10,000 tokens before any agent can "
            "receive capital allocation. New agents enter a 7-day simulation probation period where they must "
            "demonstrate strategy viability before going live. The strategyHash (keccak256 of strategy description) "
            "creates an immutable on-chain record of the agent's declared approach. Slashed tokens are transferred "
            "to the protocol treasury (owner address)."
        ),
        "key_functions": [
            {"name": "registerAgent(address, bytes32, uint8, uint256)", "desc": "Register with stake and strategy hash"},
            {"name": "activateAgent(address)", "desc": "Activate after passing 7-day simulation"},
            {"name": "slashAgent(address, uint256 slashBps)", "desc": "Slash stake on drawdown breach"},
            {"name": "getActiveAgents()", "desc": "Returns all currently active agent addresses"},
        ],
        "events": ["AgentRegistered", "AgentActivated", "AgentSlashed", "AgentDeregistered"],
        "submitted_by": None,
    },
    {
        "id": "slashing-module",
        "name": "SlashingModule",
        "version": "v1.2",
        "address": "0xFACEFACEfacefaceFACEFACEfacefaceFACEFACE",
        "stellar_address": _STELLAR_ADDRESSES["slashing-module"],
        "solana_program_id": _SOLANA_PROGRAM_IDS["slashing-module"],
        "status": "deployed",
        "audited": True,
        "tvl": 0,
        "source_file": "src/SlashingModule.sol",
        "explanation": (
            "The SlashingModule is the risk enforcement layer. It receives performance reports from an oracle and "
            "calculates drawdown: (peak - current) / peak * 10000 bps. When drawdown exceeds the threshold (default "
            "20%), it executes proportional slashing: slashBps = min(excessDrawdown, maxSlash=50%). This prevents "
            "binary elimination — agents are penalized proportionally, not wiped out on first breach. All slash "
            "events are recorded in a per-agent history for audit purposes. The threshold is governance-controlled "
            "via setThreshold()."
        ),
        "key_functions": [
            {"name": "reportPerformance(address, uint256)", "desc": "Oracle reports current portfolio value"},
            {"name": "_executeSlash(address, uint256)", "desc": "Proportional slash on threshold breach"},
            {"name": "setThreshold(uint256 bps)", "desc": "Update drawdown threshold (500–5000 bps)"},
            {"name": "getSlashHistory(address)", "desc": "Returns full slash history for an agent"},
        ],
        "events": ["DrawdownReported", "SlashExecuted", "ThresholdUpdated"],
        "submitted_by": None,
    },
    {
        "id": "mock-aave-pool",
        "name": "MockAavePool",
        "version": "v1.0",
        "address": "0xAA1EBAbECAFEBABEcafebabeCAfEBAbEcafe0001",
        "status": "deployed",
        "audited": True,
        "tvl": 0,
        "source_file": "src/MockAavePool.sol",
        "explanation": (
            "A simulation-only Aave lending pool used in the IRIS Protocol testnet environment. Supports supply (5% APY) "
            "and borrow (8% APR) positions per token per user. Interest accrues on every 10-second trading cycle "
            "via accrueInterest(). Supply positions earn yield by incrementing the stored balance; debt positions "
            "grow with borrow interest. This contract lets agents simulate DeFi yield strategies without real "
            "Aave integration, making the simulation environment self-contained and deterministic."
        ),
        "key_functions": [
            {"name": "supply(address token, uint256 amount, address onBehalfOf)", "desc": "Deposit tokens to earn 5% APY"},
            {"name": "borrow(address token, uint256 amount, address onBehalfOf)", "desc": "Borrow tokens at 8% APR"},
            {"name": "withdraw(address token, uint256 amount, address to)", "desc": "Withdraw supplied tokens"},
            {"name": "accrueInterest()", "desc": "Accrue interest on all positions (called each 10s cycle)"},
        ],
        "events": ["Supplied", "Borrowed", "Withdrawn", "InterestAccrued"],
        "submitted_by": None,
    },
    {
        "id": "mock-uniswap-router",
        "name": "MockUniswapRouter",
        "version": "v1.0",
        "address": "0xAA1EBAbECAFEBABEcafebabeCAfEBAbEcafe0002",
        "status": "deployed",
        "audited": True,
        "tvl": 0,
        "source_file": "src/MockUniswapRouter.sol",
        "explanation": (
            "A simulation-only Uniswap V2-style router that swaps ETH for ERC20 tokens using MockPriceFeed prices. "
            "Applies a 0.3% swap fee and ±2% pseudo-random slippage derived from block entropy, making each swap "
            "realistically imperfect. The slippage guard (minAmountOut) protects against excessive price impact. "
            "Token output is minted directly to the recipient, simulating liquidity without requiring actual "
            "liquidity pools. Used by agent trading loops to simulate DEX execution."
        ),
        "key_functions": [
            {"name": "swapExactETHForTokens(uint256 minOut, address token, address to)", "desc": "Swap ETH for tokens with 0.3% fee + ±2% slippage"},
        ],
        "events": ["Swap"],
        "submitted_by": None,
    },
    {
        "id": "mock-price-feed",
        "name": "MockPriceFeed",
        "version": "v1.0",
        "address": "0xAA1EBAbECAFEBABEcafebabeCAfEBAbEcafe0003",
        "status": "deployed",
        "audited": True,
        "tvl": 0,
        "source_file": "src/MockPriceFeed.sol",
        "explanation": (
            "An on-chain price oracle for the IRIS Protocol simulation environment. Stores prices for WBTC, WETH, USDC, "
            "LINK, and UNI scaled to 1e8 (Chainlink-compatible format). Prices update via a ±1% pseudo-random walk "
            "per 10-second cycle, derived from block.timestamp and block.prevrandao for entropy. Prices are bounded "
            "between 50% and 200% of their initial values to prevent runaway simulation drift. Used by "
            "MockUniswapRouter and the Python price engine for consistent cross-layer pricing."
        ),
        "key_functions": [
            {"name": "updatePrices()", "desc": "Apply ±1% random walk to all token prices"},
            {"name": "getPrice(address token)", "desc": "Read current price for a token (1e8 scale)"},
            {"name": "tokenCount()", "desc": "Returns number of tracked tokens"},
        ],
        "events": ["PricesUpdated"],
        "submitted_by": None,
    },
    {
        "id": "mock-erc20",
        "name": "MockERC20",
        "version": "v1.0",
        "address": "0xAA1EBAbECAFEBABEcafebabeCAfEBAbEcafe0004",
        "status": "deployed",
        "audited": True,
        "tvl": 0,
        "source_file": "src/MockERC20.sol",
        "explanation": (
            "A mintable ERC20 token with configurable decimals, used to simulate WBTC (8 decimals), USDC (6 decimals), "
            "LINK (18 decimals), and UNI (18 decimals) in the IRIS Protocol testnet. Extends OpenZeppelin's ERC20 and Ownable. "
            "Only the owner (deployer/MockUniswapRouter) can mint tokens, preventing unauthorized supply inflation. "
            "The configurable decimals constructor parameter makes this a single reusable contract for all simulated "
            "assets rather than requiring separate implementations per token."
        ),
        "key_functions": [
            {"name": "mint(address to, uint256 amount)", "desc": "Mint tokens to address — owner only"},
            {"name": "decimals()", "desc": "Returns configured decimal places"},
        ],
        "events": ["Transfer", "Approval"],
        "submitted_by": None,
    },
    {
        "id": "mock-stake-token",
        "name": "MockStakeToken",
        "version": "v1.0",
        "address": "0xAA1EBAbECAFEBABEcafebabeCAfEBAbEcafe0005",
        "status": "deployed",
        "audited": True,
        "tvl": 0,
        "source_file": "src/MockStakeToken.sol",
        "explanation": (
            "A minimal ERC20 token (symbol: DST — IRIS Protocol Stake Token) used as the staking currency for AgentRegistry "
            "in local development and testing. Mints 1,000,000 DST to the deployer on construction, providing "
            "sufficient supply for testing agent registration flows that require a minimum 10,000 token stake. "
            "No mint function beyond the constructor — fixed supply for predictable test environments."
        ),
        "key_functions": [
            {"name": "constructor()", "desc": "Mints 1,000,000 DST to deployer"},
        ],
        "events": ["Transfer", "Approval"],
        "submitted_by": None,
    },
]

def _load_submissions() -> list:
    if _SUBMISSIONS_PATH.exists():
        try:
            with open(_SUBMISSIONS_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_submissions(subs: list):
    _SUBMISSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SUBMISSIONS_PATH, "w") as f:
        json.dump(subs, f, indent=2)

def _read_source(filename: str) -> str:
    for base in [_CONTRACTS_DIR, _CONTRACTS_DIR / "src"]:
        p = base / filename
        if p.exists():
            return p.read_text()
    return f"// Source not found: {filename}"

@router.get("/")
def list_contracts():
    subs = _load_submissions()
    all_contracts = []
    for c in _BUILTIN:
        all_contracts.append({k: v for k, v in c.items() if k != "source_file"})
    for s in subs:
        all_contracts.append({k: v for k, v in s.items() if k != "source_code"})
    return all_contracts

@router.get("/stellar")
def list_stellar_contracts():
    """Returns only the protocol contracts that have Stellar (Soroban) deployments."""
    return [
        {
            "id": c["id"],
            "name": c["name"],
            "version": c["version"],
            "stellar_address": c["stellar_address"],
            "status": c["status"],
            "audited": c["audited"],
        }
        for c in _BUILTIN
        if "stellar_address" in c
    ]

@router.get("/solana")
def list_solana_contracts():
    """Returns only the protocol contracts that have Solana (testnet) deployments."""
    return [
        {
            "id": c["id"],
            "name": c["name"],
            "version": c["version"],
            "solana_program_id": c["solana_program_id"],
            "status": c["status"],
            "audited": c["audited"],
        }
        for c in _BUILTIN
        if "solana_program_id" in c
    ]


@router.get("/addresses")
def get_contract_addresses():
    """Return all deployed contract addresses for both chains."""
    import os
    return {
        "stellar": {
            "agent_registry":    os.getenv("STELLAR_AGENT_REGISTRY",    _STELLAR_ADDRESSES["agent-registry"]),
            "allocation_engine": os.getenv("STELLAR_ALLOCATION_ENGINE", _STELLAR_ADDRESSES["allocation-engine"]),
            "capital_vault":     os.getenv("STELLAR_CAPITAL_VAULT",     _STELLAR_ADDRESSES["capital-vault"]),
            "slashing_module":   os.getenv("STELLAR_SLASHING_MODULE",   _STELLAR_ADDRESSES["slashing-module"]),
            "network":           "testnet",
            "rpc_url":           os.getenv("STELLAR_RPC_URL", "https://soroban-testnet.stellar.org"),
            "horizon_url":       os.getenv("STELLAR_HORIZON_URL", "https://horizon-testnet.stellar.org"),
        },
        "solana": {
            "agent_registry":    os.getenv("SOLANA_AGENT_REGISTRY",    _SOLANA_PROGRAM_IDS["agent-registry"]),
            "allocation_engine": os.getenv("SOLANA_ALLOCATION_ENGINE", _SOLANA_PROGRAM_IDS["allocation-engine"]),
            "capital_vault":     os.getenv("SOLANA_CAPITAL_VAULT",     _SOLANA_PROGRAM_IDS["capital-vault"]),
            "slashing_module":   os.getenv("SOLANA_SLASHING_MODULE",   _SOLANA_PROGRAM_IDS["slashing-module"]),
            "wallet":            os.getenv("SOLANA_WALLET_ADDRESS",    "9cNCsgFCoutgvftQTdV9YigxSrFXWqd5v7Zjnmw8beqB"),
            "network":           "testnet",
            "rpc_url":           os.getenv("SOLANA_RPC_URL", "https://api.testnet.solana.com"),
        },
    }


@router.get("/{contract_id}")
def get_contract(contract_id: str):
    for c in _BUILTIN:
        if c["id"] == contract_id:
            source = _read_source(c["source_file"])
            return {**c, "source_code": source}

    subs = _load_submissions()
    s = next((x for x in subs if x["id"] == contract_id), None)
    if s:
        return s
    raise HTTPException(status_code=404, detail="Contract not found")

class ContractSubmission(BaseModel):
    name: str
    version: str = "v1.0"
    address: Optional[str] = ""
    source_code: str
    explanation: str
    submitted_by: str = "anonymous"

@router.post("/submit")
def submit_contract(data: ContractSubmission):
    if len(data.source_code) < 20:
        raise HTTPException(status_code=400, detail="Source code too short")
    if len(data.explanation) < 10:
        raise HTTPException(status_code=400, detail="Explanation required")

    subs = _load_submissions()
    entry = {
        "id": f"user-{uuid.uuid4().hex[:8]}",
        "name": data.name,
        "version": data.version,
        "address": data.address or "0x" + "0" * 40,
        "status": "pending_review",
        "audited": False,
        "tvl": 0,
        "source_code": data.source_code,
        "explanation": data.explanation,
        "submitted_by": data.submitted_by,
        "submitted_at": time.time(),
        "key_functions": [],
        "events": [],
    }
    subs.append(entry)
    _save_submissions(subs)
    return entry
