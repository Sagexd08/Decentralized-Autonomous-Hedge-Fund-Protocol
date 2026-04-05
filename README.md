# IRIS Protocol — Decentralized Autonomous Capital Allocation Protocol

IRIS Protocol is a full-stack, research-grade protocol for autonomous on-chain capital allocation. It combines cryptoeconomic enforcement on Stellar Soroban and Solana with off-chain ML-driven agent intelligence, a real-time FastAPI backend, and a Next.js operator dashboard.

---

## What it does

Capital sits in on-chain vaults. Autonomous agents compete for allocation by generating trading signals. A Multiplicative Weights Update (MWU) algorithm continuously reweights capital toward better-performing agents. Agents that breach drawdown limits are automatically slashed. Governance proposals can tune every protocol parameter in real time.

No agent ever directly controls investor funds. All enforcement is on-chain.

---

## Deployed Contracts

### Stellar Soroban — Testnet

| Contract | Address |
|---|---|
| AgentRegistry | `CDJD33R7ZVT7YZD2T6ROK2MPK2XRYJCKSM4AQOXPKCGMIQCAN7R6RTVJ` |
| AllocationEngine | `CBBXJBG5Y74XBO7NSWUXNOZVEBWTBCEL6ZAPEXULASBIM3FSEZBRPPUV` |
| CapitalVault | `CB263OPPTMRE7R37CMIPSYWLDVVAR4UYWXQS7C6FY3AS6VBUEPHYX3H6` |
| SlashingModule | `CAHJFZI7IZSPAZK35LZLYNG564F3LPQZFDRRFXFUENVWGY7Q6OHE3U5I` |

Deployer: `GCLZ64XJEQJO6JXYVXULSRUDHSBM3WWGKO2AILWJSED5G4FSBIJEZMBL`

### Solana — Testnet

| Program | ID |
|---|---|
| AgentRegistry | `F4s8zTom7KLNLXAhRpbgwJ2dYSNg2hi4M1Rn4m9t71NN` |
| AllocationEngine | `2MKzNfzPkEvsj6BKSrEEc9d4hdXmZnkyYQgTEtFZqbvR` |
| CapitalVault | `4AdNiFej3xrBh5t5NziiMMTMs1YK7qMUxgTNBwo4tcf2` |
| SlashingModule | `AC6xZSbeD6fMRafNVGbnuN4vt94py7heNKyepp7KqBUv` |

Deployer wallet: `9cNCsgFCoutgvftQTdV9YigxSrFXWqd5v7Zjnmw8beqB`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        INVESTOR / OPERATOR                       │
│                    Next.js Dashboard (port 3000)                 │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST + WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                    FastAPI Backend (port 8000)                    │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ AgentTrading │  │  PriceEngine │  │   ML Inference       │   │
│  │   Engine     │  │  (O-U sim)   │  │  CNN-LSTM + fallback  │   │
│  └──────┬───────┘  └──────────────┘  └──────────────────────┘   │
│         │                                                         │
│  ┌──────▼──────────────────────────────────────────────────┐    │
│  │              MWU Allocation Engine (Python)              │    │
│  │   w_i(t+1) = w_i(t) · exp(η · R_i(t))  / Σ w_j(t+1)   │    │
│  └──────┬──────────────────────────────────────────────────┘    │
└─────────┼───────────────────────────────────────────────────────┘
          │  submit_update / report_performance / slash
    ┌─────┴──────────────────────────────────────────┐
    │                                                  │
┌───▼──────────────┐                    ┌─────────────▼──────────┐
│  Stellar Soroban │                    │   Solana (Anchor)       │
│  (Testnet)       │                    │   (Testnet)             │
│                  │                    │                         │
│  AgentRegistry   │                    │  AgentRegistry          │
│  AllocationEngine│                    │  AllocationEngine       │
│  CapitalVault    │                    │  CapitalVault           │
│  SlashingModule  │                    │  SlashingModule         │
└──────────────────┘                    └─────────────────────────┘
```

---

## Repository Layout

```
.
├── backend/
│   ├── main.py                  # FastAPI app, lifespan, chain init
│   ├── api/
│   │   ├── agents.py            # Agent CRUD, register, stake, chain/active
│   │   ├── pools.py             # Pool list, deposit (Stellar + Solana)
│   │   ├── trading.py           # start/stop trading, portfolio
│   │   ├── analytics.py         # Monte Carlo, regime, MWU weights
│   │   ├── governance.py        # Proposals, voting, veto, params
│   │   ├── intelligence.py      # Loop state, leaderboard, demo
│   │   ├── contracts.py         # Contract metadata + addresses
│   │   ├── news.py              # Crypto news + signals
│   │   ├── integrations.py      # Supabase status + table rows
│   │   ├── ws_trading.py        # WebSocket /ws/trading + chain event listener
│   │   ├── ws_prices.py         # WebSocket /ws/prices + /ws/market
│   │   └── ws_social.py         # WebSocket /ws/social (Gemini AI feed)
│   ├── agents/
│   │   ├── trading_engine.py    # Per-agent async trading loops, MWU push, auto-slash
│   │   ├── price_engine.py      # Ornstein-Uhlenbeck price simulation
│   │   ├── market_stream.py     # Normalized market event stream
│   │   ├── crypto_news.py       # CryptoPanic / GDELT news fetcher
│   │   └── gemini_social.py     # Gemini-powered AI social feed
│   ├── core/
│   │   ├── stellar_client.py    # Stellar Soroban read/write client
│   │   ├── solana_client.py     # Solana JSON-RPC client (all 4 programs)
│   │   ├── allocation.py        # MWU algorithm, risk-adjusted returns
│   │   ├── protocol_params.py   # Live governance parameter singleton
│   │   ├── settings.py          # Pydantic settings from .env
│   │   └── supabase.py          # Storage upload/download helpers
│   ├── db/
│   │   └── connection.py        # SQLAlchemy engine with graceful fallback
│   ├── ml/
│   │   ├── hybrid_model.py      # CNN-LSTM architecture
│   │   ├── train_hybrid.py      # Full training pipeline
│   │   ├── live_inference.py    # Real-time inference from price history
│   │   ├── regime_classifier.py # HMM volatility regime detection
│   │   └── monte_carlo.py       # GBM paths, VaR/CVaR
│   └── tests/                   # pytest test suite
├── contracts/
│   └── src/                     # Solidity contracts (EVM reference)
├── db/
│   └── schema.sql               # PostgreSQL schema
└── frontend/
    ├── app/                     # Next.js app directory
    ├── components/              # Radix UI + custom components
    ├── hooks/                   # useLivePrices, useAgents, useTradingFeed
    └── lib/
        └── api.ts               # Typed API client for all backend endpoints
```

---

## How the Protocol Works

### 1. Capital custody

Investors deposit into one of three risk pools via `POST /api/pools/deposit`. The backend calls `vault_deposit` on both the Stellar Soroban CapitalVault and the Solana CapitalVault simultaneously. Funds are tracked on-chain; the backend never holds capital.

### 2. Agent registration and staking

Agents register via `POST /api/agents/register`. The backend calls `activate_agent` on the Stellar AgentRegistry. Agents must stake tokens (`POST /api/agents/stake`) before receiving allocation. Minimum stake is enforced by `protocol_params.min_stake`.

### 3. Trading loops

Each active agent runs an independent asyncio task (10-second cycles). Every cycle:

1. Fetches live prices from the Ornstein-Uhlenbeck price engine
2. Runs CNN-LSTM inference (falls back to momentum if model unavailable)
3. Submits `submit_update(agent_address, return_bps)` to both Stellar AllocationEngine and Solana AllocationEngine
4. Reports current portfolio value to both SlashingModules
5. Broadcasts the trade event over `/ws/trading`

### 4. MWU reallocation

Every 6 cycles (~60 seconds), the engine runs a full MWU step across all active agents:

```
w_i(t+1) = w_i(t) · exp(η · R_i(t))
```

where `R_i(t)` is the risk-adjusted return: `Return / (Volatility + λ · |Drawdown|)`. Normalized weights are pushed to both chains. The learning rate η is live-tunable via governance.

### 5. Automatic slashing

If any agent's drawdown exceeds 20% (configurable via `slashing_threshold_bps`), the engine automatically calls `slash_agent` on both chains and broadcasts a `slash_event` over WebSocket.

### 6. Governance

Protocol parameters (η, slashing threshold, vol caps, min stake, quorum) are controlled by on-chain governance proposals. Proposals pass after reaching quorum within the proposal window. Passed proposals call `protocol_params.apply(key, value)` which takes effect immediately in the running process.

---

## API Reference

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Basic health check |
| GET | `/health/chains` | Live Stellar + Solana connection status |
| GET | `/api/contracts/addresses` | All deployed contract addresses |
| GET | `/api/trading/status` | Active agents + chain TVL |

### Agents

| Method | Path | Description |
|---|---|---|
| GET | `/api/agents/` | List all agents (optional `?risk=`) |
| GET | `/api/agents/{id}` | Get single agent |
| POST | `/api/agents/register` | Register new agent (calls chain registry) |
| POST | `/api/agents/stake` | Stake tokens for an agent |
| GET | `/api/agents/chain/active` | Active agents from both chain registries |
| POST | `/api/agents/{id}/start-trading` | Start agent trading loop |
| POST | `/api/agents/{id}/stop-trading` | Stop agent trading loop |
| GET | `/api/agents/{id}/portfolio` | Allocation weight, TVL, scores |

### Pools

| Method | Path | Description |
|---|---|---|
| GET | `/api/pools/` | List all pools with live TVL |
| GET | `/api/pools/{id}` | Get single pool |
| POST | `/api/pools/deposit` | Deposit into pool (calls both chains) |

### Analytics

| Method | Path | Description |
|---|---|---|
| GET | `/api/analytics/monte-carlo` | GBM paths + VaR/CVaR |
| GET | `/api/analytics/rolling-volatility` | Rolling vol series |
| GET | `/api/analytics/regime` | HMM regime classification |
| GET | `/api/analytics/allocation-weights` | MWU weight history |

### WebSockets

| Path | Description |
|---|---|
| `/ws/prices` | Live price ticks (3s interval) |
| `/ws/market` | Normalized market events |
| `/ws/trading` | Live trade events + slash events + MWU updates |
| `/ws/social` | AI agent social feed |

---

## Local Development

### Prerequisites

- Python 3.10+ (3.10 recommended — project uses `.venv310`)
- Node.js 18+
- PostgreSQL or SQLite (SQLite used automatically as fallback)

### Backend

```bash
cd backend
python -m venv .venv310
.venv310\Scripts\activate          # Windows
# source .venv310/bin/activate     # macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The backend starts with:
- Price engine running (O-U simulation, 3s ticks)
- ML model downloaded from Supabase (or loaded from `ml/model.pkl`)
- Stellar Soroban client connected to testnet
- Solana client connected to testnet
- All active agents auto-started in trading loops
- Chain event listener polling both chains every 5s

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend connects to the backend at `http://localhost:8000` (configured in `frontend/.env.local`).

### Environment Variables

Copy `.env` to `backend/.env` and fill in your values. Key variables:

```env
# Stellar Soroban (testnet)
STELLAR_RPC_URL=https://soroban-testnet.stellar.org
STELLAR_HORIZON_URL=https://horizon-testnet.stellar.org
STELLAR_NETWORK_PASSPHRASE=Test SDF Network ; September 2015
STELLAR_PUBLIC_KEY=<your G-address>
STELLAR_SECRET_KEY=<your S-address secret>
STELLAR_AGENT_REGISTRY=CDJD33R7ZVT7YZD2T6ROK2MPK2XRYJCKSM4AQOXPKCGMIQCAN7R6RTVJ
STELLAR_ALLOCATION_ENGINE=CBBXJBG5Y74XBO7NSWUXNOZVEBWTBCEL6ZAPEXULASBIM3FSEZBRPPUV
STELLAR_CAPITAL_VAULT=CB263OPPTMRE7R37CMIPSYWLDVVAR4UYWXQS7C6FY3AS6VBUEPHYX3H6
STELLAR_SLASHING_MODULE=CAHJFZI7IZSPAZK35LZLYNG564F3LPQZFDRRFXFUENVWGY7Q6OHE3U5I

# Solana (testnet)
SOLANA_RPC_URL=https://api.testnet.solana.com
SOLANA_WALLET_ADDRESS=9cNCsgFCoutgvftQTdV9YigxSrFXWqd5v7Zjnmw8beqB
SOLANA_AGENT_REGISTRY=F4s8zTom7KLNLXAhRpbgwJ2dYSNg2hi4M1Rn4m9t71NN
SOLANA_ALLOCATION_ENGINE=2MKzNfzPkEvsj6BKSrEEc9d4hdXmZnkyYQgTEtFZqbvR
SOLANA_CAPITAL_VAULT=4AdNiFej3xrBh5t5NziiMMTMs1YK7qMUxgTNBwo4tcf2
SOLANA_SLASHING_MODULE=AC6xZSbeD6fMRafNVGbnuN4vt94py7heNKyepp7KqBUv

# Database (SQLite fallback if not set)
DATABASE_URL=postgresql://user:pass@host/iris

# Supabase (for ML model storage)
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SECRET_KEY=<service_role_key>
SUPABASE_PUBLISHABLE_KEY=<anon_key>
```

### Running Tests

```bash
cd backend
pytest tests/ -v --tb=short
```

---

## ML Pipeline

The hybrid CNN-LSTM model in `backend/ml/train_hybrid.py`:

1. Loads Bitcoin OHLCV data from Kaggle (synthetic fallback if unavailable)
2. Engineers 20 features: returns, rolling stats, momentum, HL spread, volume norm
3. Trains a CNN-LSTM regression model (50-bar windows, 30 epochs, early stopping)
4. Runs 200 steps of online learning on the most recent data
5. Evaluates with MSE, MAE, RMSE, and a direction-level confusion matrix (SELL/HOLD/BUY)
6. Runs HMM regime classification (3 volatility states)
7. Runs Monte Carlo risk analysis (2000 paths, 30-day horizon, VaR/CVaR at 95%)
8. Saves `model.pkl` locally and uploads to Supabase Storage

At inference time (`backend/ml/live_inference.py`), the model synthesizes OHLCV features from the live price history and returns a `(predicted_log_return, decision, confidence)` tuple. Falls back to 3-bar momentum if the model is unavailable or history is too short.

To retrain:

```bash
cd backend
python -m ml.train_hybrid
```

---

## Solana Contract Exports

The deployed Anchor programs export the following instructions:

**AgentRegistry** — `activate_agent`, `get_active_agents`, `get_agent`, `get_config`, `init`, `register_agent`, `slash_agent`

**AllocationEngine** — `alpha`, `get_agent_score`, `get_config`, `get_reputation_score`, `init`, `set_eta`, `submit_update`

**CapitalVault** — `aggressive`, `balanced`, `conservative`, `deposit`, `enforce_drawdown_limit`, `get_agent_current_value`, `get_agent_peak_value`, `get_agent_weight`, `get_config`, `get_investor_balance`, `get_pool_tvl`, `get_volatility_cap`, `init`, `max_drawdown_bps`, `performance_fee_bps`, `set_agent_values`, `set_allocation_engine`, `set_slashing_module`, `total_tvl`, `update_weights`, `withdraw`

**SlashingModule** — `get_config`, `get_current_value`, `get_peak_value`, `get_slash_history`, `init`, `report_performance`, `set_threshold`

---

## Stellar Contract Exports

The deployed Soroban contracts expose the same logical interface as the Solana programs, compiled from Rust to WASM:

- `agent_registry.wasm` — 11,263 bytes, 7 exported functions
- `allocation_engine.wasm` — 7,009 bytes, 7 exported functions
- `capital_vault.wasm` — 11,504 bytes, 21 exported functions
- `slashing_module.wasm` — 7,945 bytes, 7 exported functions

---

## Design Principles

**Capital separation** — agents receive allocation weights, never direct custody. The vault enforces this at the contract level.

**Cryptoeconomic enforcement** — slashing is automatic and on-chain. No human needs to approve a slash when a drawdown limit is breached.

**Dual-chain redundancy** — every capital operation (deposit, performance update, slash) is submitted to both Stellar and Solana. Either chain can serve as the source of truth.

**Online adaptation** — MWU weights update every ~60 seconds based on live risk-adjusted returns. The regret bound is O(√T · ln N) vs the best fixed agent in hindsight.

**Measurable ML** — the model is evaluated on direction accuracy (SELL/HOLD/BUY confusion matrix), not just regression loss. Inference falls back gracefully to momentum when the model is unavailable.

**Governance-tunable** — every protocol parameter (learning rate, slashing threshold, vol caps, min stake, quorum) is controlled by on-chain governance proposals that take effect immediately when passed.
