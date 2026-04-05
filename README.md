# DACAP

Decentralized Autonomous Capital Allocation Protocol for on-chain capital custody, off-chain agent intelligence, and research-grade ML-assisted risk management.

## Overview

DACAP is a full-stack prototype for a decentralized autonomous hedge-fund-style system that separates:

- capital custody and enforcement on-chain
- strategy generation and market intelligence off-chain
- allocation and risk feedback through measurable performance signals

The project combines:

- FastAPI backend services for agents, analytics, governance, and integrations
- a React/Vite frontend for protocol dashboards and operator workflows
- Solidity contracts for vaulting, agent registration, slashing, and allocation
- an ML pipeline for hybrid forecasting, regime analysis, Monte Carlo risk, and model artifact distribution through Supabase Storage

## System Architecture

### 1. On-chain layer

The contracts enforce the hard guarantees:

- investor capital remains in protocol-controlled vaults
- agent registration requires stake and supports anti-sybil controls
- drawdown and governance constraints are codified
- allocation weights are applied on-chain rather than trusted to off-chain execution

Core contracts live under [contracts/src](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/contracts/src):

- [CapitalVault.sol](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/contracts/src/CapitalVault.sol)
- [AllocationEngine.sol](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/contracts/src/AllocationEngine.sol)
- [AgentRegistry.sol](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/contracts/src/AgentRegistry.sol)
- [SlashingModule.sol](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/contracts/src/SlashingModule.sol)

## Deployed Contract Addresses

### Stellar (Soroban) — Testnet

| Contract | Address |
|---|---|
| AgentRegistry | `CDJD33R7ZVT7YZD2T6ROK2MPK2XRYJCKSM4AQOXPKCGMIQCAN7R6RTVJ` |
| AllocationEngine | `CBBXJBG5Y74XBO7NSWUXNOZVEBWTBCEL6ZAPEXULASBIM3FSEZBRPPUV` |
| CapitalVault | `CB263OPPTMRE7R37CMIPSYWLDVVAR4UYWXQS7C6FY3AS6VBUEPHYX3H6` |
| SlashingModule | `CAHJFZI7IZSPAZK35LZLYNG564F3LPQZFDRRFXFUENVWGY7Q6OHE3U5I` |

Deployer key address: `GCLZ64XJEQJO6JXYVXULSRUDHSBM3WWGKO2AILWJSED5G4FSBIJEZMBL`

### Solana — Testnet

| Contract | Program ID |
|---|---|
| AgentRegistry | `F4s8zTom7KLNLXAhRpbgwJ2dYSNg2hi4M1Rn4m9t71NN` |
| AllocationEngine | `2MKzNfzPkEvsj6BKSrEEc9d4hdXmZnkyYQgTEtFZqbvR` |
| CapitalVault | `4AdNiFej3xrBh5t5NziiMMTMs1YK7qMUxgTNBwo4tcf2` |
| SlashingModule | `AC6xZSbeD6fMRafNVGbnuN4vt94py7heNKyepp7KqBUv` |

Deployer wallet address: `9cNCsgFCoutgvftQTdV9YigxSrFXWqd5v7Zjnmw8beqB`

### 2. Backend intelligence layer

The backend coordinates:

- protocol APIs for agents, pools, analytics, governance, contracts, and news
- market data streaming and trading engine orchestration
- Supabase integration for storage and operational status
- ML model bootstrap on application startup

The application entrypoint is [backend/main.py](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/backend/main.py), which now automatically downloads the latest model artifact from Supabase Storage on startup and loads it into app state.

### 3. Frontend control surface

The frontend provides:

- analytics and portfolio monitoring
- agent views and intelligence panels
- governance and contract interaction surfaces
- protocol health visibility, including Supabase status

The frontend codebase lives in [frontend/src](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/frontend/src).

## Machine Learning Pipeline

The hybrid ML workflow in [backend/ml/train_hybrid.py](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/backend/ml/train_hybrid.py):

- builds engineered OHLCV-based features
- trains a CNN-LSTM regression model for next-bar return prediction
- performs an online-learning refinement phase
- evaluates the model with regression metrics and a direction-level confusion matrix
- runs regime classification and Monte Carlo risk analysis
- persists the model locally and uploads it to Supabase Storage

### Evaluation outputs

The current evaluation path reports:

- MSE
- MAE
- RMSE
- directional accuracy
- confusion matrix across `SELL`, `HOLD`, and `BUY`

This confusion matrix is derived from the same thresholded trading decisions used at inference time, so the evaluation now reflects both regression quality and actionable signal quality.

### Model storage workflow

The canonical model artifact is:

- local path: [backend/ml/model.pkl](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/backend/ml/model.pkl)
- Supabase object: `models/model.pkl`

Supporting files:

- [backend/core/supabase.py](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/backend/core/supabase.py) for storage helpers
- [backend/ml/upload_model_to_supabase.py](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/backend/ml/upload_model_to_supabase.py) for manual uploads

## Repository Layout

```text
.
├── backend/
│   ├── api/
│   ├── agents/
│   ├── core/
│   ├── db/
│   ├── ml/
│   └── tests/
├── contracts/
│   ├── src/
│   ├── scripts/
│   └── test/
├── db/
└── frontend/
    ├── src/
    └── public-facing app config
```

## Local Development

### Backend

Install backend dependencies from [backend/requirements.txt](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/backend/requirements.txt), then run the API from the `backend` directory or project root depending on your workflow.

Typical environment values include:

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_PUBLISHABLE_KEY`
- chain RPC and Alchemy credentials
- optional Kaggle credentials for dataset access

### Frontend

The frontend uses Vite and TypeScript. Path aliases are configured for `@/` imports in:

- [frontend/tsconfig.json](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/frontend/tsconfig.json)
- [frontend/vite.config.ts](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/frontend/vite.config.ts)

### Contracts

Contracts are compiled with Hardhat from [contracts/hardhat.config.js](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/contracts/hardhat.config.js). Solidity editor settings are aligned in [.vscode/settings.json](/mnt/c/Users/sohom/OneDrive/Desktop/hacktropica/.vscode/settings.json) so OpenZeppelin imports resolve correctly from `contracts/node_modules`.

## Current Product Themes

This repository is oriented around:

- autonomous capital allocation instead of direct agent fund custody
- cryptoeconomic enforcement instead of trust-based operator discretion
- online adaptation instead of static portfolio selection
- measurable ML evaluation instead of vague AI marketing
- protocol observability across analytics, contracts, and storage integrations

## Validation Notes

Recent work in this repo includes:

- automatic model download from Supabase on backend startup
- reusable Supabase upload/download helpers
- frontend alias resolution fixes
- Solidity workspace import resolution fixes
- direction-level confusion-matrix evaluation for the hybrid model

## Positioning

DACAP is best understood not as a generic "AI trading bot" project, but as a capital-allocation protocol with:

- on-chain guardrails
- off-chain intelligence
- measurable model evaluation
- explicit storage and deployment workflows

That framing is where the architecture is strongest: autonomous capital routing under transparent risk controls, with enough infrastructure around it to evolve from prototype into a more rigorous research and product platform.
