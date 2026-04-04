-- DACAP Development Seed Data
-- Run after schema.sql

-- Sample agents (reference pools which are seeded in schema.sql)
INSERT INTO agents (id, name, owner_address, strategy_hash, strategy_description, risk_pool, stake_amount, status) VALUES
    ('AGT-001', 'Momentum Alpha',    '0x1111111111111111111111111111111111111111', '0xabc001', 'Trend-following momentum strategy using EMA crossovers',       'balanced',     15000.000000, 'active'),
    ('AGT-002', 'Mean Reversion X',  '0x2222222222222222222222222222222222222222', '0xabc002', 'Statistical arbitrage on correlated DeFi pairs',               'conservative', 12000.000000, 'active'),
    ('AGT-003', 'Volatility Arb',    '0x3333333333333333333333333333333333333333', '0xabc003', 'Options-style volatility harvesting via LP positions',         'aggressive',   20000.000000, 'active'),
    ('AGT-004', 'Yield Optimizer',   '0x4444444444444444444444444444444444444444', '0xabc004', 'Cross-protocol yield farming with auto-compounding',           'conservative', 10000.000000, 'active'),
    ('AGT-005', 'Delta Neutral',     '0x5555555555555555555555555555555555555555', '0xabc005', 'Market-neutral strategy using perpetual funding rates',        'balanced',     18000.000000, 'active'),
    ('AGT-006', 'Breakout Hunter',   '0x6666666666666666666666666666666666666666', '0xabc006', 'High-frequency breakout detection on L2 DEX order flow',      'aggressive',   25000.000000, 'probation');

-- Sample governance proposals
INSERT INTO proposals (title, param_name, current_value, proposed_value, votes_for, votes_against, status, ends_at) VALUES
    ('Increase learning rate η from 0.01 to 0.015',     'eta',                    0.01,  0.015, 68, 32, 'active',  NOW() + INTERVAL '3 days'),
    ('Reduce max drawdown threshold to 15%',             'max_drawdown_bps',       2000,  1500,  81, 19, 'passed',  NOW() - INTERVAL '1 day'),
    ('Add Aggressive pool volatility cap increase',      'aggressive_vol_cap_bps', 3500,  4000,  45, 55, 'rejected',NOW() - INTERVAL '2 days'),
    ('Increase minimum agent stake to 15,000 tokens',   'min_stake',              10000, 15000, 30, 10, 'active',  NOW() + INTERVAL '5 days');

-- Sample contracts registry
INSERT INTO contracts (id, name, address, deployed_at, audited, version) VALUES
    ('capital-vault',      'CapitalVault',      '0xCAfEBAbECAFEBABEcafebabeCAfEBAbEcafebabe', NOW() - INTERVAL '30 days', true,  'v2.1.0'),
    ('allocation-engine',  'AllocationEngine',  '0xDeAdBeEFdeadbeefDeadBeefDeAdBeEFDeAdbEEf', NOW() - INTERVAL '30 days', true,  'v2.1.0'),
    ('agent-registry',     'AgentRegistry',     '0xBEEFBEEFbeefbeefBEEFBEEFbeefbeefBEEFBEEF', NOW() - INTERVAL '30 days', false, 'v2.1.0'),
    ('slashing-module',    'SlashingModule',    '0xFACEFACEfacefaceFACEFACEfacefaceFACEFACE', NOW() - INTERVAL '30 days', false, 'v2.1.0');
