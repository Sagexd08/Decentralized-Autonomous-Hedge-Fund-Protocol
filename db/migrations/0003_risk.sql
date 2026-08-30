-- ═════════════════════════════════════════════════════════════════════════════
-- IRIS — Phase 8: risk and slashing
-- IRIS_BUILD_PROMPT v2.0 sections 8 and 13.
--
-- The Phase 8 DoD is a *chain*: breach -> freeze -> slash -> reduced
-- allocation. Four things that each work is not the same as four things that
-- connect, so this migration makes the links structural rather than a matter
-- of the code happening to call them in order.
-- ═════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Provenance on a slash
-- ─────────────────────────────────────────────────────────────────────────────
-- A slash is the most consequential thing the protocol does to an agent, and
-- everything upstream of it is currently simulated. Without this column the
-- Model Cemetery in section 15 becomes a list of agents punished for a
-- synthetic tape, with nothing on the row to say so.

ALTER TABLE slash_events
    ADD COLUMN IF NOT EXISTS data_source VARCHAR(24) NOT NULL DEFAULT 'SIMULATION';

ALTER TABLE slash_events DROP CONSTRAINT IF EXISTS slash_events_data_source_check;
ALTER TABLE slash_events ADD CONSTRAINT slash_events_data_source_check
    CHECK (data_source IN ('SIMULATION', 'TESTNET', 'LIVE'));

ALTER TABLE risk_events
    ADD COLUMN IF NOT EXISTS data_source VARCHAR(24) NOT NULL DEFAULT 'SIMULATION';

ALTER TABLE risk_events DROP CONSTRAINT IF EXISTS risk_events_data_source_check;
ALTER TABLE risk_events ADD CONSTRAINT risk_events_data_source_check
    CHECK (data_source IN ('SIMULATION', 'TESTNET', 'LIVE'));

-- A slash may never be recorded against evidence weaker than the slash claims
-- to be. Enforced rather than trusted, because the failure is silent: a LIVE
-- slash row citing a SIMULATION breach reads as a real punishment.
CREATE OR REPLACE FUNCTION slash_provenance_matches_breach()
RETURNS TRIGGER AS $$
DECLARE
    breach_source TEXT;
    rank_of CONSTANT TEXT[] := ARRAY['SIMULATION', 'TESTNET', 'LIVE'];
BEGIN
    IF NEW.risk_event_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT data_source INTO breach_source
      FROM risk_events WHERE id = NEW.risk_event_id;

    IF breach_source IS NOT NULL
       AND array_position(rank_of, NEW.data_source)
         > array_position(rank_of, breach_source)
    THEN
        RAISE EXCEPTION
            'slash on agent % claims % evidence but its breach is %',
            NEW.agent_id, NEW.data_source, breach_source
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_slash_provenance ON slash_events;
CREATE TRIGGER trg_slash_provenance
    BEFORE INSERT ON slash_events
    FOR EACH ROW EXECUTE FUNCTION slash_provenance_matches_breach();

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. A slash cannot exceed the stake
-- ─────────────────────────────────────────────────────────────────────────────
-- `slash_bps` is a fraction of stake in basis points. Anything above 10,000
-- would take more than the agent ever staked, which is not a penalty — it is a
-- debt the protocol has no way to collect.

ALTER TABLE slash_events DROP CONSTRAINT IF EXISTS slash_events_bps_range;
ALTER TABLE slash_events ADD CONSTRAINT slash_events_bps_range
    CHECK (slash_bps > 0 AND slash_bps <= 10000);

ALTER TABLE slash_events DROP CONSTRAINT IF EXISTS slash_events_amount_non_negative;
ALTER TABLE slash_events ADD CONSTRAINT slash_events_amount_non_negative
    CHECK (amount_slashed IS NULL OR amount_slashed >= 0);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. A slash must cite the breach it punishes
-- ─────────────────────────────────────────────────────────────────────────────
-- This is the causal link the DoD asks for, made unavoidable. The FK already
-- exists but is nullable, so a slash could be recorded with no breach behind
-- it — which is exactly the shape of a punishment nobody can appeal.
--
-- The FK is ON DELETE SET NULL, so an *existing* slash may end up with a null
-- reference if its breach is ever removed. The trigger therefore constrains
-- the insert rather than the column.

CREATE OR REPLACE FUNCTION slash_requires_a_breach()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.risk_event_id IS NULL THEN
        RAISE EXCEPTION
            'slash on agent % cites no risk event; a slash must name the '
            'breach it punishes', NEW.agent_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM risk_events
         WHERE id = NEW.risk_event_id AND agent_id = NEW.agent_id
    ) THEN
        RAISE EXCEPTION
            'slash on agent % cites a risk event belonging to another agent',
            NEW.agent_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_slash_requires_breach ON slash_events;
CREATE TRIGGER trg_slash_requires_breach
    BEFORE INSERT ON slash_events
    FOR EACH ROW EXECUTE FUNCTION slash_requires_a_breach();

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Freezing is reversible; slashing is not
-- ─────────────────────────────────────────────────────────────────────────────
-- FROZEN -> ACTIVE is a recovery and must stay possible: the MWU floor in
-- Phase 7 exists so an agent can earn its way back, and a freeze with no exit
-- is a different penalty from the one the allocator was designed around.
--
-- SLASHED -> ACTIVE is not a recovery, it is erasing a punishment. An agent
-- that has been slashed may be retired, but it does not quietly become active
-- again.

CREATE OR REPLACE FUNCTION agent_status_transition_is_legal()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = NEW.status THEN
        RETURN NEW;
    END IF;

    IF OLD.status = 'RETIRED' THEN
        RAISE EXCEPTION 'agent % is retired; it cannot return to %',
            OLD.id, NEW.status
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF OLD.status = 'SLASHED' AND NEW.status IN ('ACTIVE', 'PROBATION') THEN
        RAISE EXCEPTION
            'agent % was slashed; it cannot be restored to %. Retire it or '
            'register a new agent.', OLD.id, NEW.status
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_agent_status_legal ON agents;
CREATE TRIGGER trg_agent_status_legal
    BEFORE UPDATE OF status ON agents
    FOR EACH ROW EXECUTE FUNCTION agent_status_transition_is_legal();

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Indexes the sweep actually uses
-- ─────────────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_risk_events_open
    ON risk_events(agent_id, created_at DESC)
    WHERE severity = 'CRITICAL';

CREATE INDEX IF NOT EXISTS idx_agents_frozen ON agents(status) WHERE status = 'FROZEN';
