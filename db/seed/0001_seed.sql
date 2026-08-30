-- IRIS Protocol — development seed
-- IRIS_BUILD_PROMPT v2.0 section 23: 8 agents, 4 model families, 3 risk profiles.
-- Believable names only; no "AI Agent 1" placeholders.
--
-- Everything here is development fixture data. Nothing in this file should ever
-- be presented in the UI as live or verified without a SIMULATION label
-- (v2 section 0c).

-- ─── Vaults ──────────────────────────────────────────────────────────────────
-- Volatility caps are constraints, not promised returns.

INSERT INTO vaults (id, name, risk_profile, volatility_cap_bps, max_allocation_bps) VALUES
    ('conservative', 'Conservative', 'CONSERVATIVE',  800, 2000),
    ('balanced',     'Balanced',     'BALANCED',     1800, 3000),
    ('aggressive',   'Aggressive',   'AGGRESSIVE',   3500, 3500)
ON CONFLICT (id) DO NOTHING;

-- ─── Agents ──────────────────────────────────────────────────────────────────
-- Four strategy families across the three vaults. Every agent starts on
-- PROBATION; only the runtime promotes one to ACTIVE.

INSERT INTO agents (id, name, strategy, vault_id, status) VALUES
    ('AGT-AXIOM',    'Axiom',    'momentum',        'aggressive',   'PROBATION'),
    ('AGT-VECTOR',   'Vector',   'mean_reversion',  'balanced',     'PROBATION'),
    ('AGT-HELIX',    'Helix',    'breakout',        'aggressive',   'PROBATION'),
    ('AGT-QUANTA',   'Quanta',   'adaptive',        'balanced',     'PROBATION'),
    ('AGT-MERIDIAN', 'Meridian', 'mean_reversion',  'conservative', 'PROBATION'),
    ('AGT-PULSE',    'Pulse',    'momentum',        'balanced',     'PROBATION'),
    ('AGT-NEXUS',    'Nexus',    'adaptive',        'aggressive',   'PROBATION'),
    ('AGT-SIGMA',    'Sigma',    'breakout',        'conservative', 'PROBATION')
ON CONFLICT (id) DO NOTHING;

-- ─── Model versions ──────────────────────────────────────────────────────────
-- One active version each. model_hash is a placeholder until a real artifact is
-- trained and hashed in Phase 4 — these are deliberately obvious, not
-- realistic-looking fakes.

INSERT INTO model_versions (agent_id, version, model_family, model_hash, is_active) VALUES
    ('AGT-AXIOM',    1, 'cnn_lstm',          repeat('0', 63) || '1', TRUE),
    ('AGT-VECTOR',   1, 'gradient_boosting', repeat('0', 63) || '2', TRUE),
    ('AGT-HELIX',    1, 'baseline',          repeat('0', 63) || '3', TRUE),
    ('AGT-QUANTA',   1, 'transformer',       repeat('0', 63) || '4', TRUE),
    ('AGT-MERIDIAN', 1, 'gradient_boosting', repeat('0', 63) || '5', TRUE),
    ('AGT-PULSE',    1, 'cnn_lstm',          repeat('0', 63) || '6', TRUE),
    ('AGT-NEXUS',    1, 'transformer',       repeat('0', 63) || '7', TRUE),
    ('AGT-SIGMA',    1, 'baseline',          repeat('0', 63) || '8', TRUE)
ON CONFLICT (agent_id, version) DO NOTHING;

-- ─── Governance defaults ─────────────────────────────────────────────────────

INSERT INTO governance_proposals (title, param_name, current_value, proposed_value, ends_at)
VALUES (
    'Raise MWU learning rate to accelerate reallocation',
    'eta', 0.01, 0.02, NOW() + INTERVAL '5 days'
)
ON CONFLICT DO NOTHING;
