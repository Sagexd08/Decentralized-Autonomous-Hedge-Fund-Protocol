from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import asyncio
import logging

from db.connection import execute_statement, fetch_all_dicts, fetch_one_dict

logger = logging.getLogger(__name__)
router = APIRouter()

_MODEL_FAMILY = {
    "AlphaWave": "LSTM Momentum Stack",
    "NeuralArb": "Transformer Arbitrage",
    "QuantSigma": "Z-Score Mean Reversion",
    "VoltexAI": "HMM Volatility Breakout",
    "DeltaHedge": "Greeks Hedger",
    "OmegaFlow": "Liquidation Cascade Detector",
    "StableYield": "Yield Optimizer",
    "FluxArb": "Cointegration Pairs Engine",
    "NovaSurge": "RL Scalping Policy",
}

AGENTS = [
    {
        "id": "AGT-001", "name": "AlphaWave", "strategy": "Momentum + ML", "risk": "Aggressive",
        "sharpe": 2.41, "drawdown": -8.2, "allocation": 28, "pnl": 34.7, "volatility": 18.4,
        "stake": 50000, "status": "active", "score": 91,
        "address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "description": (
            "AlphaWave uses a dual-layer momentum strategy combining exponential moving average (EMA) crossovers "
            "with a gradient-boosted ML classifier. Signal generation: EMA(12) and EMA(26) crossover triggers "
            "a candidate signal. The momentum score is computed as M(t) = (P(t) - P(t-n)) / P(t-n) where n=14 "
            "periods. A LightGBM classifier trained on 47 features (RSI, MACD histogram, volume delta, on-chain "
            "flow, funding rates) outputs a probability p ∈ [0,1]. Position sizing follows Kelly criterion: "
            "f* = (p·b - (1-p)) / b where b is the expected payoff ratio. Trades execute only when p > 0.62 "
            "and M(t) > 0.005. Stop-loss is set at 2× ATR(14). The ML model is retrained every 72 hours on "
            "rolling 90-day windows using walk-forward validation to prevent lookahead bias."
        ),
    },
    {
        "id": "AGT-002", "name": "NeuralArb", "strategy": "Cross-DEX Arbitrage", "risk": "Balanced",
        "sharpe": 1.87, "drawdown": -4.1, "allocation": 22, "pnl": 21.3, "volatility": 11.2,
        "stake": 40000, "status": "active", "score": 84,
        "address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        "description": (
            "NeuralArb exploits price inefficiencies across Uniswap V3, Curve, and Balancer using a "
            "transformer-based price prediction model. The arbitrage condition is: Profit = P_DEX2 - P_DEX1 - "
            "GasCost - SlippageCost > threshold. Slippage is modeled as S(x) = x / (2·k) where x is trade "
            "size and k is the pool's liquidity depth (from the constant product formula x·y = k). The neural "
            "network (4-layer transformer, 128 hidden dims) predicts price convergence probability within the "
            "next 3 blocks. Execution uses flash loans to eliminate capital requirements: borrow → swap DEX1 "
            "→ swap DEX2 → repay + profit, all atomically. The agent monitors 847 token pairs in real-time "
            "and filters by minimum spread of 0.15% after fees. Gas optimization uses EIP-1559 base fee "
            "prediction to time submissions."
        ),
    },
    {
        "id": "AGT-003", "name": "QuantSigma", "strategy": "Mean Reversion", "risk": "Conservative",
        "sharpe": 1.52, "drawdown": -2.8, "allocation": 18, "pnl": 14.6, "volatility": 7.8,
        "stake": 35000, "status": "active", "score": 78,
        "address": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
        "description": (
            "QuantSigma implements a statistical mean-reversion strategy using the Ornstein-Uhlenbeck (OU) "
            "process: dX(t) = θ(μ - X(t))dt + σdW(t), where θ is the mean-reversion speed, μ is the "
            "long-run mean, σ is volatility, and W(t) is Brownian motion. Parameters are estimated via "
            "maximum likelihood estimation on 60-day rolling windows. Entry signal: z-score = (X(t) - μ) / σ. "
            "Long when z < -1.5, short when z > 1.5, exit at |z| < 0.3. The half-life of mean reversion is "
            "τ = ln(2) / θ — positions are held for at most 2τ periods. Pairs are selected using the "
            "Engle-Granger cointegration test (p < 0.05) and Hurst exponent H < 0.5 (confirming "
            "mean-reverting behavior). Risk is capped at 1% portfolio VaR per trade."
        ),
    },
    {
        "id": "AGT-004", "name": "VoltexAI", "strategy": "Volatility Breakout", "risk": "Aggressive",
        "sharpe": 3.12, "drawdown": -14.5, "allocation": 15, "pnl": 52.1, "volatility": 28.9,
        "stake": 60000, "status": "active", "score": 88,
        "address": "0x90F79bf6EB2c4f870365E785982E1f101E93b906",
        "description": (
            "VoltexAI detects volatility regime breakouts using a Hidden Markov Model (HMM) with 3 states "
            "(low/medium/high volatility). State transition probabilities are estimated via Baum-Welch "
            "algorithm on realized volatility: RV(t) = sqrt(Σ r²_i) where r_i are intraday log-returns. "
            "Breakout confirmation uses Bollinger Band squeeze: BB_width = (BB_upper - BB_lower) / BB_mid. "
            "When BB_width drops below the 10th percentile (squeeze) then expands above the 60th percentile, "
            "a breakout is confirmed. Position size scales with the ATR ratio: size = base_size × "
            "ATR(5) / ATR(20). The agent also monitors implied volatility skew from on-chain options "
            "protocols (Lyra, Dopex) — a skew > 1.15 signals directional bias. Trailing stop at 1.5× ATR."
        ),
    },
    {
        "id": "AGT-005", "name": "DeltaHedge", "strategy": "Options Delta Neutral", "risk": "Balanced",
        "sharpe": 1.23, "drawdown": -5.9, "allocation": 10, "pnl": 9.8, "volatility": 9.1,
        "stake": 30000, "status": "probation", "score": 62,
        "address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
        "description": (
            "DeltaHedge maintains a delta-neutral portfolio using the Black-Scholes Greeks. Option delta: "
            "Δ = N(d1) where d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T). The portfolio is rebalanced when "
            "|Σ Δ_i| > 0.05 (delta threshold). Gamma scalping: when Γ = N'(d1) / (S·σ·√T) is high, "
            "the agent profits from realized vol exceeding implied vol by buying/selling the underlying. "
            "Vega exposure is managed by targeting Σ ν_i ≈ 0 across positions. The agent uses on-chain "
            "perpetual funding rates as a proxy for options premium — when funding > 0.01% per 8h, "
            "it sells synthetic calls via perp shorts. Currently in probation: the gamma hedging model "
            "is being calibrated against live on-chain vol surfaces."
        ),
    },
    {
        "id": "AGT-006", "name": "OmegaFlow", "strategy": "Liquidation Hunter", "risk": "Aggressive",
        "sharpe": 2.78, "drawdown": -11.2, "allocation": 7, "pnl": 41.3, "volatility": 22.6,
        "stake": 45000, "status": "active", "score": 85,
        "address": "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc",
        "description": (
            "OmegaFlow predicts and front-runs liquidation cascades using on-chain liquidation map data. "
            "The liquidation density function L(P) = Σ position_size_i · δ(P - liquidation_price_i) "
            "identifies price levels with concentrated liquidations. When price approaches a high-density "
            "zone (L(P) > 2σ above mean), the agent positions in the direction of the cascade. "
            "Cascade amplification is modeled as: ΔP_cascade = -λ · L(P) · ΔP_initial where λ is the "
            "market impact coefficient estimated from historical liquidation events. The agent also "
            "monitors funding rate divergence across perpetual DEXs — a spread > 0.03% signals "
            "over-leveraged positioning. Exit strategy: close 80% of position at the liquidation cluster "
            "center, hold 20% for secondary cascade. Max position duration: 4 hours."
        ),
    },
    {
        "id": "AGT-007", "name": "StableYield", "strategy": "Stablecoin Yield Optimization", "risk": "Conservative",
        "sharpe": 1.18, "drawdown": -1.4, "allocation": 12, "pnl": 8.9, "volatility": 4.2,
        "stake": 28000, "status": "active", "score": 72,
        "address": "0xBcd4042DE499D14e55001CcbB24a551F3b954096",
        "description": (
            "StableYield maximizes risk-adjusted stablecoin yield using a multi-protocol optimization model. "
            "The objective function: max Σ w_i · APY_i subject to: Σ w_i = 1, w_i ≥ 0, "
            "CVaR(portfolio) ≤ threshold. APY for each protocol is decomposed as: "
            "APY_total = APY_base + APY_incentive - depeg_risk_premium. Depeg risk is modeled using "
            "a Gaussian copula on historical USDC/USDT/DAI price deviations. The agent rebalances "
            "across Aave V3, Compound, Curve 3pool, and Convex using a mean-variance optimization "
            "(Markowitz) with a risk-aversion parameter γ = 3. Liquidity constraints are enforced: "
            "no more than 40% in any single protocol. Smart contract risk is priced using audit scores "
            "and TVL-weighted historical exploit rates as a risk premium deduction."
        ),
    },
    {
        "id": "AGT-008", "name": "FluxArb", "strategy": "Statistical Pairs Trading", "risk": "Balanced",
        "sharpe": 2.05, "drawdown": -6.3, "allocation": 14, "pnl": 27.4, "volatility": 13.7,
        "stake": 42000, "status": "active", "score": 80,
        "address": "0x71bE63f3384f5fb98995898A86B02Fb2426c5788",
        "description": (
            "FluxArb implements a Kalman filter-based pairs trading strategy for cointegrated DeFi token "
            "pairs. The spread is modeled as: S(t) = P_A(t) - β(t)·P_B(t) where β(t) is the time-varying "
            "hedge ratio estimated by the Kalman filter: β(t) = β(t-1) + K(t)·(S(t) - β(t-1)·P_B(t)), "
            "K(t) = P(t-1) / (P(t-1) + R) where P is the error covariance and R is measurement noise. "
            "This allows β to adapt to structural breaks unlike static OLS. Pairs are selected using "
            "the Johansen cointegration test (trace statistic > critical value at 5%). Entry: z-score "
            "of spread > 2σ. Exit: z-score < 0.5σ or stop-loss at z > 3.5σ. The agent trades 12 "
            "pairs simultaneously (WBTC/ETH, LINK/UNI, etc.) with equal risk allocation per pair "
            "using the Riskfolio-Lib CVaR optimization framework."
        ),
    },
    {
        "id": "AGT-009", "name": "NovaSurge", "strategy": "High-Frequency Momentum Scalping", "risk": "Aggressive",
        "sharpe": 3.44, "drawdown": -17.8, "allocation": 9, "pnl": 61.2, "volatility": 33.1,
        "stake": 70000, "status": "active", "score": 87,
        "address": "0xdD2FD4581271e230360230F9337D5c0430Bf44C0",
        "description": (
            "NovaSurge is a high-frequency scalping agent using order flow imbalance (OFI) as its primary "
            "signal. OFI(t) = Σ [V_bid(t) - V_ask(t)] / [V_bid(t) + V_ask(t)] over a 30-second window. "
            "Price impact is modeled via the Almgren-Chriss framework: dP = σ·dW + η·v·dt where η is "
            "the temporary market impact coefficient and v is trading rate. The agent uses a deep "
            "reinforcement learning policy (PPO algorithm) trained on 18 months of L2 DEX order book "
            "data. State space: [OFI, mid-price, spread, inventory, time-of-day, funding rate]. "
            "Action space: {buy, sell, hold} × {0.1%, 0.25%, 0.5%, 1%} of portfolio. Reward function: "
            "R(t) = PnL(t) - λ·inventory² - κ·turnover where λ=0.001 penalizes inventory risk and "
            "κ=0.0005 penalizes excessive trading. Average hold time: 47 seconds. Executes ~340 trades/day."
        ),
    },
]

class AgentRegister(BaseModel):
    name: str
    strategy: str
    risk: str
    stake: float
    address: str

_RISK_POOL_TO_LABEL = {
    "conservative": "Conservative",
    "balanced": "Balanced",
    "aggressive": "Aggressive",
}

_RISK_LABEL_TO_POOL = {value.lower(): key for key, value in _RISK_POOL_TO_LABEL.items()}

def _db_agent_to_api(agent: dict):
    risk = _RISK_POOL_TO_LABEL.get((agent.get("risk_pool") or "").lower(), "Balanced")
    return {
        "id": agent["id"],
        "name": agent["name"],
        "strategy": agent.get("strategy_description") or "Strategy pending",
        "risk": risk,
        "sharpe": float(agent.get("sharpe") or 0),
        "drawdown": float(agent.get("drawdown") or 0),
        "allocation": float(agent.get("allocation") or 0),
        "pnl": float(agent.get("pnl") or 0),
        "volatility": float(agent.get("volatility") or 0),
        "stake": float(agent.get("stake_amount") or 0),
        "status": agent.get("status") or "probation",
        "score": int(agent.get("score") or 50),
        "address": agent.get("owner_address"),
        "description": agent.get("strategy_description") or "No strategy description available.",
    }

def _fetch_agents_from_db(risk: Optional[str] = None):
    params = {"risk_pool": _RISK_LABEL_TO_POOL.get(risk.lower())} if risk else {}
    rows = fetch_all_dicts(
        f"""
        select
            a.id,
            a.name,
            a.owner_address,
            a.strategy_description,
            a.risk_pool,
            a.stake_amount,
            a.status,
            coalesce(perf.pnl, 0) as pnl,
            coalesce(perf.sharpe_ratio, 0) as sharpe,
            coalesce(perf.max_drawdown, 0) as drawdown,
            coalesce(perf.volatility, 0) as volatility,
            coalesce(perf.allocation_weight * 100, 0) as allocation,
            coalesce(perf.reputation_score, 50) as score
        from agents a
        left join lateral (
            select
                ap.pnl,
                ap.sharpe_ratio,
                ap.max_drawdown,
                ap.volatility,
                ap.allocation_weight,
                ap.reputation_score
            from agent_performance ap
            where ap.agent_id = a.id
            order by ap.timestamp desc
            limit 1
        ) perf on true
        {"where a.risk_pool = :risk_pool" if risk else ""}
        order by a.id
        """,
        params,
    )
    return [_db_agent_to_api(row) for row in rows]

def _augment_agent(agent: dict):
    trust_score = max(1, min(100, int(round(agent["score"] * 0.55 + agent["sharpe"] * 12 - abs(agent["drawdown"]) * 0.8))))
    confidence_score = round(max(0.35, min(0.97, 0.55 + agent["sharpe"] * 0.08 - abs(agent["drawdown"]) * 0.006)), 2)
    anomaly_score = round(max(0.01, min(0.94, (abs(agent["drawdown"]) / 20) + (agent["volatility"] / 60) - (agent["sharpe"] / 10))), 2)
    model = _MODEL_FAMILY.get(agent["name"], "Hybrid Strategy")
    return {
        **agent,
        "model": model,
        "trust_score": trust_score,
        "confidence_score": confidence_score,
        "anomaly_score": anomaly_score,
        "agent_dna": {
            "model_family": model,
            "primary_edge": "speed" if "Arb" in agent["name"] else "adaptation" if agent["risk"] == "Aggressive" else "risk discipline",
            "time_horizon": "intraday" if agent["risk"] == "Aggressive" else "swing" if agent["risk"] == "Balanced" else "defensive carry",
            "economic_posture": "capital seeking" if agent["allocation"] < 12 else "capital dominant",
        },
    }

@router.get("/")
def list_agents(risk: Optional[str] = None):
    try:
        agents = _fetch_agents_from_db(risk)
        if agents:
            return [_augment_agent(a) for a in agents]
    except Exception:
        pass
    # Fallback to static agent list when DB is unavailable
    if risk:
        return [_augment_agent(a) for a in AGENTS if a["risk"].lower() == risk.lower()]
    return [_augment_agent(a) for a in AGENTS]

@router.get("/{agent_id}")
def get_agent(agent_id: str):
    try:
        agent = fetch_one_dict(
            """
            select
                a.id,
                a.name,
                a.owner_address,
                a.strategy_description,
                a.risk_pool,
                a.stake_amount,
                a.status,
                coalesce(perf.pnl, 0) as pnl,
                coalesce(perf.sharpe_ratio, 0) as sharpe,
                coalesce(perf.max_drawdown, 0) as drawdown,
                coalesce(perf.volatility, 0) as volatility,
                coalesce(perf.allocation_weight * 100, 0) as allocation,
                coalesce(perf.reputation_score, 50) as score
            from agents a
            left join lateral (
                select
                    ap.pnl,
                    ap.sharpe_ratio,
                    ap.max_drawdown,
                    ap.volatility,
                    ap.allocation_weight,
                    ap.reputation_score
                from agent_performance ap
                where ap.agent_id = a.id
                order by ap.timestamp desc
                limit 1
            ) perf on true
            where a.id = :agent_id
            """,
            {"agent_id": agent_id},
        )
        if agent:
            return _augment_agent(_db_agent_to_api(agent))
    except Exception:
        pass

    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return _augment_agent(agent)

@router.post("/register")
async def register_agent(data: AgentRegister, request: Request):
    stellar = getattr(request.app.state, "stellar", None)
    solana  = getattr(request.app.state, "solana", None)

    stellar_tx: str | None = None
    solana_tx: str | None = None

    # Register on Stellar AgentRegistry
    if stellar and stellar.public_key:
        try:
            stellar_tx = await asyncio.to_thread(
                stellar.registry_activate_agent,
                data.address,
            )
            logger.info("Stellar AgentRegistry.activate_agent → tx=%s", stellar_tx)
        except Exception as exc:
            logger.warning("Stellar register_agent failed: %s", exc)

    # Register on Solana AgentRegistry (logged, real instruction pending IDL)
    if solana:
        try:
            solana_tx = await asyncio.to_thread(
                solana.allocation_submit_update,
                data.address,
                0,
            )
            logger.info("Solana AgentRegistry registration logged → %s", solana_tx)
        except Exception as exc:
            logger.warning("Solana register_agent failed: %s", exc)

    try:
        risk_pool = _RISK_LABEL_TO_POOL.get(data.risk.lower(), "balanced")
        existing = fetch_all_dicts("select id from agents order by id")
        new_id = f"AGT-{len(existing) + 1:03d}"
        execute_statement(
            """
            insert into agents (id, name, owner_address, strategy_hash, strategy_description, risk_pool, stake_amount, status)
            values (:id, :name, :owner_address, :strategy_hash, :strategy_description, :risk_pool, :stake_amount, :status)
            """,
            {
                "id": new_id,
                "name": data.name,
                "owner_address": data.address,
                "strategy_hash": None,
                "strategy_description": data.strategy,
                "risk_pool": risk_pool,
                "stake_amount": data.stake,
                "status": "probation",
            },
        )
        return {
            "id": new_id,
            "message": "Agent registered. Entering simulation arena.",
            "stellar_tx": stellar_tx,
            "solana_tx": solana_tx,
        }
    except Exception:
        pass

    new_id = f"AGT-{len(AGENTS) + 1:03d}"
    agent = {"id": new_id, "score": 50, "status": "probation", "allocation": 0,
             "pnl": 0, "drawdown": 0, "sharpe": 0, "volatility": 0, **data.model_dump()}
    AGENTS.append(agent)
    return {
        "id": new_id,
        "message": "Agent registered. Entering simulation arena.",
        "stellar_tx": stellar_tx,
        "solana_tx": solana_tx,
    }


class StakeRequest(BaseModel):
    agent_id: str
    amount: float
    address: str


@router.post("/stake")
async def stake_agent(data: StakeRequest, request: Request):
    """Stake tokens for an agent on both Stellar and Solana."""
    stellar = getattr(request.app.state, "stellar", None)
    solana  = getattr(request.app.state, "solana", None)

    stellar_tx: str | None = None
    solana_tx: str | None = None
    amount_stroops = int(data.amount * 1e7)
    amount_lamports = int(data.amount * 1e9)

    if stellar and stellar.public_key:
        try:
            stellar_tx = await asyncio.to_thread(
                stellar.vault_deposit,
                data.address,
                1,  # balanced pool for staking
                amount_stroops,
            )
            logger.info("Stellar stake → agent=%s amount=%d tx=%s", data.agent_id, amount_stroops, stellar_tx)
        except Exception as exc:
            logger.warning("Stellar stake failed: %s", exc)

    if solana:
        try:
            solana_tx = await asyncio.to_thread(
                solana.vault_deposit,
                data.address,
                1,
                amount_lamports,
            )
            logger.info("Solana stake → agent=%s amount=%d tx=%s", data.agent_id, amount_lamports, solana_tx)
        except Exception as exc:
            logger.warning("Solana stake failed: %s", exc)

    # Update DB stake amount
    try:
        execute_statement(
            "update agents set stake_amount = coalesce(stake_amount, 0) + :amount where id = :id",
            {"amount": data.amount, "id": data.agent_id},
        )
    except Exception:
        pass

    return {
        "agent_id":   data.agent_id,
        "amount":     data.amount,
        "stellar_tx": stellar_tx,
        "solana_tx":  solana_tx,
        "status":     "staked",
    }


@router.get("/chain/active")
async def get_chain_active_agents(request: Request):
    """Return active agents from both Stellar and Solana registries."""
    stellar = getattr(request.app.state, "stellar", None)
    solana  = getattr(request.app.state, "solana", None)

    stellar_agents: list[str] = []
    solana_agents: list[str] = []

    if stellar:
        try:
            stellar_agents = await asyncio.to_thread(stellar.registry_get_active_agents)
        except Exception as exc:
            logger.warning("Stellar get_active_agents failed: %s", exc)

    if solana:
        try:
            solana_agents = await asyncio.to_thread(solana.registry_get_active_agents)
        except Exception as exc:
            logger.warning("Solana get_active_agents failed: %s", exc)

    return {
        "stellar": stellar_agents,
        "solana":  solana_agents,
        "combined": list(set(stellar_agents + solana_agents)),
    }
