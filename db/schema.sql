CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

<<<<<<< HEAD
CREATE TABLE IF NOT EXISTS investors (
=======
CREATE TABLE investors (
>>>>>>> D!
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    address VARCHAR(42) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

<<<<<<< HEAD
CREATE TABLE IF NOT EXISTS pools (
=======
CREATE TABLE pools (
>>>>>>> D!
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    volatility_cap_bps INTEGER NOT NULL,
    tvl NUMERIC(20, 6) DEFAULT 0,
    apy NUMERIC(8, 4) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

<<<<<<< HEAD
INSERT INTO pools (id, name, volatility_cap_bps, tvl, apy, created_at) VALUES
    ('conservative', 'Conservative', 800, 4200000, 12.4, NOW()),
    ('balanced', 'Balanced', 1800, 8700000, 24.7, NOW()),
    ('aggressive', 'Aggressive', 3500, 12400000, 47.2, NOW())
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS deposits (
=======
INSERT INTO pools VALUES
    ('conservative', 'Conservative', 800, 4200000, 12.4, NOW()),
    ('balanced', 'Balanced', 1800, 8700000, 24.7, NOW()),
    ('aggressive', 'Aggressive', 3500, 12400000, 47.2, NOW());

CREATE TABLE deposits (
>>>>>>> D!
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investor_id UUID REFERENCES investors(id),
    pool_id VARCHAR(20) REFERENCES pools(id),
    amount NUMERIC(20, 6) NOT NULL,
    tx_hash VARCHAR(66),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

<<<<<<< HEAD
CREATE TABLE IF NOT EXISTS agents (
=======
CREATE TABLE agents (
>>>>>>> D!
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    owner_address VARCHAR(42) NOT NULL,
    strategy_hash VARCHAR(66),
    strategy_description TEXT,
    risk_pool VARCHAR(20) REFERENCES pools(id),
    stake_amount NUMERIC(20, 6) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'probation',
    registered_at TIMESTAMPTZ DEFAULT NOW()
);

<<<<<<< HEAD
CREATE TABLE IF NOT EXISTS agent_performance (
=======
CREATE TABLE agent_performance (
>>>>>>> D!
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(20) REFERENCES agents(id),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    pnl NUMERIC(10, 6),
    sharpe_ratio NUMERIC(8, 4),
    max_drawdown NUMERIC(8, 4),
    volatility NUMERIC(8, 4),
    allocation_weight NUMERIC(8, 6),
    reputation_score NUMERIC(8, 4)
);

<<<<<<< HEAD
CREATE TABLE IF NOT EXISTS allocation_history (
=======
CREATE TABLE allocation_history (
>>>>>>> D!
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(20) REFERENCES agents(id),
    weight NUMERIC(10, 8) NOT NULL,
    eta NUMERIC(10, 6) NOT NULL,
    update_step INTEGER NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

<<<<<<< HEAD
CREATE TABLE IF NOT EXISTS slash_events (
=======
CREATE TABLE slash_events (
>>>>>>> D!
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(20) REFERENCES agents(id),
    drawdown_bps INTEGER NOT NULL,
    slash_bps INTEGER NOT NULL,
    tx_hash VARCHAR(66),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

<<<<<<< HEAD
CREATE TABLE IF NOT EXISTS proposals (
=======
CREATE TABLE proposals (
>>>>>>> D!
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    param_name VARCHAR(50),
    current_value NUMERIC,
    proposed_value NUMERIC,
    votes_for INTEGER DEFAULT 0,
    votes_against INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

<<<<<<< HEAD
CREATE TABLE IF NOT EXISTS votes (
=======
CREATE TABLE votes (
>>>>>>> D!
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id INTEGER REFERENCES proposals(id),
    voter_address VARCHAR(42) NOT NULL,
    support BOOLEAN NOT NULL,
    weight NUMERIC(20, 6) DEFAULT 1,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(proposal_id, voter_address)
);

<<<<<<< HEAD
CREATE TABLE IF NOT EXISTS contracts (
=======
CREATE TABLE contracts (
>>>>>>> D!
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    address VARCHAR(42) UNIQUE NOT NULL,
    abi JSONB,
    deployed_at TIMESTAMPTZ,
    audited BOOLEAN DEFAULT FALSE,
    version VARCHAR(20)
);

<<<<<<< HEAD
CREATE INDEX IF NOT EXISTS idx_agent_perf_agent ON agent_performance(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_perf_time ON agent_performance(timestamp);
CREATE INDEX IF NOT EXISTS idx_alloc_agent ON allocation_history(agent_id);
CREATE INDEX IF NOT EXISTS idx_deposits_investor ON deposits(investor_id);
=======
CREATE INDEX idx_agent_perf_agent ON agent_performance(agent_id);
CREATE INDEX idx_agent_perf_time ON agent_performance(timestamp);
CREATE INDEX idx_alloc_agent ON allocation_history(agent_id);
CREATE INDEX idx_deposits_investor ON deposits(investor_id);
>>>>>>> D!
