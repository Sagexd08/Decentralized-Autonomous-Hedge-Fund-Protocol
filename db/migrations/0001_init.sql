-- IRIS Protocol — initial schema
-- IRIS_BUILD_PROMPT v2.0 section 13.
--
-- This file is the source of truth for the schema. db/schema.sql documents how
-- to regenerate a flat dump from it; do not hand-edit that dump.
--
-- Conventions
--   * bps  = basis points, stored as integers, never floats
--   * money and returns use NUMERIC, never DOUBLE PRECISION
--   * every foreign key is declared; no application-level joins on bare ids
--   * timestamps are TIMESTAMPTZ and default to NOW()

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────────────────────────────
-- Identity
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_address  VARCHAR(64) UNIQUE NOT NULL,
    display_name    VARCHAR(80),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Capital
-- ─────────────────────────────────────────────────────────────────────────────

-- Risk profiles are constraints, never promised returns (v2 section 5).
CREATE TABLE IF NOT EXISTS vaults (
    id                  VARCHAR(20) PRIMARY KEY,
    name                VARCHAR(50)  NOT NULL,
    risk_profile        VARCHAR(20)  NOT NULL
                        CHECK (risk_profile IN ('CONSERVATIVE', 'BALANCED', 'AGGRESSIVE')),
    volatility_cap_bps  INTEGER      NOT NULL CHECK (volatility_cap_bps > 0),
    max_drawdown_bps    INTEGER      NOT NULL DEFAULT 2000,
    min_allocation_bps  INTEGER      NOT NULL DEFAULT 0,
    max_allocation_bps  INTEGER      NOT NULL DEFAULT 3500,
    solana_pubkey       VARCHAR(64),
    tvl                 NUMERIC(24, 6) NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CHECK (min_allocation_bps <= max_allocation_bps)
);

CREATE TABLE IF NOT EXISTS deposits (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vault_id     VARCHAR(20) NOT NULL REFERENCES vaults(id) ON DELETE RESTRICT,
    amount       NUMERIC(24, 6) NOT NULL CHECK (amount > 0),
    solana_sig   VARCHAR(128),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deposits_user  ON deposits(user_id);
CREATE INDEX IF NOT EXISTS idx_deposits_vault ON deposits(vault_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Agents and their models
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agents (
    id                 VARCHAR(24) PRIMARY KEY,
    owner_id           UUID        REFERENCES users(id) ON DELETE SET NULL,
    name               VARCHAR(80) NOT NULL,
    strategy           VARCHAR(40) NOT NULL,
    strategy_hash      CHAR(64),
    vault_id           VARCHAR(20) REFERENCES vaults(id) ON DELETE SET NULL,
    solana_pubkey      VARCHAR(64) UNIQUE,
    status             VARCHAR(20) NOT NULL DEFAULT 'PROBATION'
                       CHECK (status IN ('PROBATION', 'ACTIVE', 'FROZEN', 'SLASHED', 'RETIRED')),
    -- set when status becomes RETIRED; drives the Model Cemetery (v2 section 15)
    retired_at         TIMESTAMPTZ,
    retirement_reason  TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((status = 'RETIRED') = (retired_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_vault  ON agents(vault_id);

-- Model identity is persistent and versioned (v2 invariant 3).
CREATE TABLE IF NOT EXISTS model_versions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id      VARCHAR(24) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    version       INTEGER     NOT NULL CHECK (version > 0),
    model_family  VARCHAR(40) NOT NULL
                  CHECK (model_family IN ('baseline', 'gradient_boosting', 'cnn_lstm', 'transformer')),
    model_hash    CHAR(64)    NOT NULL,
    artifact_uri  TEXT,
    trained_at    TIMESTAMPTZ,
    is_active     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_id, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_model_versions_one_active
    ON model_versions(agent_id) WHERE is_active;

CREATE TABLE IF NOT EXISTS agent_stakes (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id      VARCHAR(24) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    amount        NUMERIC(24, 6) NOT NULL,
    is_unstake    BOOLEAN     NOT NULL DEFAULT FALSE,
    solana_sig    VARCHAR(128),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_stakes_agent ON agent_stakes(agent_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Predictions — the core Web3 x ML primitive (v2 section 5)
-- ─────────────────────────────────────────────────────────────────────────────

-- A prediction is immutable once COMMITTED. committed_at must precede
-- horizon_end, and settlement may only happen after it; both are enforced here
-- so no application bug can rewrite history.
CREATE TABLE IF NOT EXISTS predictions (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id          VARCHAR(24) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    model_version_id  UUID        NOT NULL REFERENCES model_versions(id) ON DELETE RESTRICT,
    asset             VARCHAR(16) NOT NULL,
    direction         VARCHAR(8)  NOT NULL CHECK (direction IN ('BUY', 'SELL', 'HOLD')),
    expected_return   NUMERIC(12, 8) NOT NULL,
    confidence        NUMERIC(6, 5)  NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    horizon_seconds   INTEGER     NOT NULL CHECK (horizon_seconds > 0),
    prediction_hash   CHAR(64)    NOT NULL UNIQUE,
    status            VARCHAR(24) NOT NULL DEFAULT 'PREDICTED'
                      CHECK (status IN ('PREDICTED', 'COMMITTED', 'WAITING_FOR_OUTCOME',
                                        'SETTLED', 'EVALUATED')),
    solana_sig        VARCHAR(128),
    predicted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    committed_at      TIMESTAMPTZ,
    horizon_end       TIMESTAMPTZ NOT NULL,
    CHECK (committed_at IS NULL OR committed_at <= horizon_end)
);

CREATE INDEX IF NOT EXISTS idx_predictions_agent  ON predictions(agent_id, predicted_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status);
CREATE INDEX IF NOT EXISTS idx_predictions_due    ON predictions(horizon_end)
    WHERE status IN ('COMMITTED', 'WAITING_FOR_OUTCOME');

-- Outcomes live in their own table so the prediction row never needs an UPDATE
-- that could rewrite a committed claim.
CREATE TABLE IF NOT EXISTS prediction_outcomes (
    prediction_id     UUID PRIMARY KEY REFERENCES predictions(id) ON DELETE CASCADE,
    actual_return     NUMERIC(12, 8) NOT NULL,
    error             NUMERIC(12, 8) NOT NULL,
    direction_correct BOOLEAN     NOT NULL,
    evaluation_score  NUMERIC(8, 5),
    settled_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    solana_sig        VARCHAR(128)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Performance, reputation, allocation
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_performance (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id       VARCHAR(24) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    window_start   TIMESTAMPTZ NOT NULL,
    window_end     TIMESTAMPTZ NOT NULL,
    pnl            NUMERIC(20, 8),
    sharpe         NUMERIC(10, 5),
    sortino        NUMERIC(10, 5),
    max_drawdown_bps INTEGER,
    volatility_bps   INTEGER,
    accuracy       NUMERIC(6, 5),
    calibration    NUMERIC(6, 5),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (window_end > window_start)
);

CREATE INDEX IF NOT EXISTS idx_agent_perf_agent ON agent_performance(agent_id, window_end DESC);

-- The IRIS Score and the dimensions it was computed from. Weights are stored
-- alongside the score so a historical score can always be re-derived.
CREATE TABLE IF NOT EXISTS reputation_scores (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id     VARCHAR(24) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    iris_score   NUMERIC(6, 3) NOT NULL CHECK (iris_score BETWEEN 0 AND 100),
    dimensions   JSONB       NOT NULL,
    weights      JSONB       NOT NULL,
    computed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reputation_agent ON reputation_scores(agent_id, computed_at DESC);

CREATE TABLE IF NOT EXISTS allocation_history (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id     VARCHAR(24) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    vault_id     VARCHAR(20) REFERENCES vaults(id) ON DELETE SET NULL,
    step         INTEGER     NOT NULL CHECK (step >= 0),
    weight       NUMERIC(12, 10) NOT NULL CHECK (weight >= 0 AND weight <= 1),
    score        NUMERIC(10, 5),
    eta          NUMERIC(10, 6) NOT NULL,
    solana_sig   VARCHAR(128),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_id, step)
);

CREATE INDEX IF NOT EXISTS idx_alloc_step ON allocation_history(step DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Execution
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS trades (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id       VARCHAR(24) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    prediction_id  UUID        REFERENCES predictions(id) ON DELETE SET NULL,
    asset          VARCHAR(16) NOT NULL,
    side           VARCHAR(8)  NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity       NUMERIC(24, 10) NOT NULL CHECK (quantity > 0),
    price          NUMERIC(24, 10) NOT NULL CHECK (price > 0),
    -- honest labelling is a hard rule (v2 section 0c)
    execution_mode VARCHAR(12) NOT NULL DEFAULT 'SIMULATION'
                   CHECK (execution_mode IN ('SIMULATION', 'TESTNET', 'LIVE')),
    solana_sig     VARCHAR(128),
    executed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_agent ON trades(agent_id, executed_at DESC);

CREATE TABLE IF NOT EXISTS positions (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id       VARCHAR(24) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    asset          VARCHAR(16) NOT NULL,
    quantity       NUMERIC(24, 10) NOT NULL,
    avg_entry      NUMERIC(24, 10) NOT NULL,
    unrealized_pnl NUMERIC(20, 8) NOT NULL DEFAULT 0,
    opened_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at      TIMESTAMPTZ,
    UNIQUE (agent_id, asset, opened_at)
);

CREATE INDEX IF NOT EXISTS idx_positions_open ON positions(agent_id) WHERE closed_at IS NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- Risk and consequence
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS risk_events (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id     VARCHAR(24) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    kind         VARCHAR(32) NOT NULL
                 CHECK (kind IN ('DRAWDOWN_BREACH', 'VOLATILITY_BREACH', 'VAR_BREACH',
                                 'CVAR_BREACH', 'EXPOSURE_BREACH', 'CONFIDENCE_FLOOR',
                                 'FREEZE', 'UNFREEZE')),
    severity     VARCHAR(12) NOT NULL CHECK (severity IN ('INFO', 'WARN', 'CRITICAL')),
    measured_bps INTEGER,
    limit_bps    INTEGER,
    detail       JSONB,
    solana_sig   VARCHAR(128),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_events_agent ON risk_events(agent_id, created_at DESC);

CREATE TABLE IF NOT EXISTS slash_events (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id       VARCHAR(24) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    risk_event_id  UUID        REFERENCES risk_events(id) ON DELETE SET NULL,
    drawdown_bps   INTEGER     NOT NULL,
    slash_bps      INTEGER     NOT NULL CHECK (slash_bps > 0),
    amount_slashed NUMERIC(24, 6),
    solana_sig     VARCHAR(128),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_slash_events_agent ON slash_events(agent_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Agent runtime observability (v2 section 19)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_runs (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id       VARCHAR(24) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    prediction_id  UUID        REFERENCES predictions(id) ON DELETE SET NULL,
    status         VARCHAR(16) NOT NULL DEFAULT 'RUNNING'
                   CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED', 'ABSTAINED')),
    started_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at    TIMESTAMPTZ,
    latency_ms     INTEGER,
    error          TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_id, started_at DESC);

-- One row per LangGraph node execution, so the AI Observatory renders real
-- state rather than a mock (v2 section 15).
CREATE TABLE IF NOT EXISTS graph_checkpoints (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_run_id UUID        NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    node         VARCHAR(40) NOT NULL,
    seq          INTEGER     NOT NULL CHECK (seq >= 0),
    state        JSONB       NOT NULL,
    input_hash   CHAR(64),
    output_hash  CHAR(64),
    latency_ms   INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_run_id, seq)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- World state and historical memory (v2 section 12)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS market_events (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset        VARCHAR(16) NOT NULL,
    kind         VARCHAR(32) NOT NULL,
    payload      JSONB       NOT NULL,
    source       VARCHAR(24) NOT NULL DEFAULT 'SIMULATION',
    embedding    vector(384),
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_events_asset ON market_events(asset, occurred_at DESC);

CREATE TABLE IF NOT EXISTS news_events (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    headline      TEXT        NOT NULL,
    url           TEXT,
    source        VARCHAR(64),
    assets        TEXT[]      NOT NULL DEFAULT '{}',
    sentiment     NUMERIC(6, 5),
    embedding     vector(384),
    published_at  TIMESTAMPTZ NOT NULL,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_published ON news_events(published_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Governance
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS governance_proposals (
    id              SERIAL PRIMARY KEY,
    title           TEXT        NOT NULL,
    param_name      VARCHAR(64) NOT NULL,
    current_value   NUMERIC     NOT NULL,
    proposed_value  NUMERIC     NOT NULL,
    proposer_id     UUID        REFERENCES users(id) ON DELETE SET NULL,
    status          VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'PASSED', 'REJECTED', 'VETOED', 'EXECUTED')),
    quorum_pct      INTEGER     NOT NULL DEFAULT 20,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ends_at         TIMESTAMPTZ NOT NULL,
    CHECK (ends_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_proposals_status ON governance_proposals(status, ends_at);

CREATE TABLE IF NOT EXISTS governance_votes (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id  INTEGER     NOT NULL REFERENCES governance_proposals(id) ON DELETE CASCADE,
    voter_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    support      BOOLEAN     NOT NULL,
    weight       NUMERIC(24, 6) NOT NULL DEFAULT 1 CHECK (weight > 0),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (proposal_id, voter_id)
);
