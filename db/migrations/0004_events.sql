-- ═════════════════════════════════════════════════════════════════════════════
-- IRIS — Phase 9: the protocol event stream
-- IRIS_BUILD_PROMPT v2.0 sections 14 and 19.
--
-- Phase 9's DoD is "real events from phases 3-8 reach a connected client", and
-- the load-bearing word is *real*. A WebSocket that invents its own traffic is
-- indistinguishable from a working one until somebody checks the database, and
-- the pre-v2 sockets in this repo do exactly that — they broadcast simulated
-- ticks on a timer and predate every table they would need to read.
--
-- The strongest available guarantee is to make the event *be* a row. This is an
-- outbox: triggers on the eight tables phases 3-8 write append to a single
-- ordered log, and the socket does nothing but read it. So an event with no row
-- behind it cannot be produced — not because the streaming code is careful, but
-- because there is nowhere for it to come from.
--
-- One log rather than eight pollers also buys ordering. `seq` is monotonic
-- across every source, so a client that reconnects with a watermark resumes
-- exactly where it left off, and a prediction can never arrive before the run
-- that produced it.
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS protocol_events (
    seq          BIGSERIAL PRIMARY KEY,
    kind         VARCHAR(40) NOT NULL,
    source_table VARCHAR(40) NOT NULL,
    -- The primary key of the row that caused this event. TEXT because the
    -- sources are a mix of UUID, VARCHAR and BIGINT — this column exists so a
    -- client can go and read the row itself, which is the difference between a
    -- feed and a claim.
    source_id    TEXT        NOT NULL,
    agent_id     VARCHAR(24) REFERENCES agents(id) ON DELETE SET NULL,
    -- Provenance travels with the event. A frame that drops it hands the UI a
    -- number with no way to know it came from a simulated tape (section 0c).
    data_source  VARCHAR(24) NOT NULL DEFAULT 'SIMULATION'
                 CHECK (data_source IN ('SIMULATION', 'TESTNET', 'LIVE')),
    payload      JSONB       NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_protocol_events_agent ON protocol_events(agent_id, seq DESC);
CREATE INDEX IF NOT EXISTS idx_protocol_events_kind  ON protocol_events(kind, seq DESC);

-- The log is append-only. It is the record the Observatory renders and the
-- audit trail a settled prediction is defended with; an editable stream is a
-- stream nobody can rely on.
CREATE OR REPLACE FUNCTION protocol_events_are_append_only()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'protocol_events is append-only (attempted % on seq %)',
        TG_OP, OLD.seq
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_protocol_events_immutable ON protocol_events;
CREATE TRIGGER trg_protocol_events_immutable
    BEFORE UPDATE OR DELETE ON protocol_events
    FOR EACH ROW EXECUTE FUNCTION protocol_events_are_append_only();

-- ─────────────────────────────────────────────────────────────────────────────
-- Emission
-- ─────────────────────────────────────────────────────────────────────────────
-- NOTIFY as well as INSERT, so a listener does not have to poll. The payload
-- carries only the sequence number: NOTIFY has an 8000-byte limit and silently
-- fails above it, so sending the event body would work in testing and drop
-- exactly the largest, most interesting events in production.

CREATE OR REPLACE FUNCTION emit_protocol_event(
    p_kind TEXT, p_table TEXT, p_id TEXT,
    p_agent TEXT, p_source TEXT, p_payload JSONB
) RETURNS BIGINT AS $$
DECLARE
    new_seq BIGINT;
BEGIN
    INSERT INTO protocol_events (kind, source_table, source_id, agent_id, data_source, payload)
    VALUES (p_kind, p_table, p_id, p_agent, coalesce(p_source, 'SIMULATION'), p_payload)
    RETURNING seq INTO new_seq;

    PERFORM pg_notify('iris_events', new_seq::text);
    RETURN new_seq;
END;
$$ LANGUAGE plpgsql;

-- ── agent runs ───────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION ev_agent_runs() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM emit_protocol_event(
            'RUN_STARTED', 'agent_runs', NEW.id::text, NEW.agent_id, 'SIMULATION',
            jsonb_build_object('status', NEW.status, 'started_at', NEW.started_at));
    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        PERFORM emit_protocol_event(
            'RUN_' || NEW.status, 'agent_runs', NEW.id::text, NEW.agent_id, 'SIMULATION',
            jsonb_build_object('status', NEW.status, 'latency_ms', NEW.latency_ms,
                               'error', NEW.error, 'prediction_id', NEW.prediction_id));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ev_agent_runs ON agent_runs;
CREATE TRIGGER trg_ev_agent_runs AFTER INSERT OR UPDATE ON agent_runs
    FOR EACH ROW EXECUTE FUNCTION ev_agent_runs();

-- ── graph checkpoints ────────────────────────────────────────────────────────
-- Eleven per run. Chatty on purpose: the AI Observatory in section 15 renders
-- the graph node by node, and a stream that only carried the final decision
-- would make that view a reconstruction rather than a recording.

CREATE OR REPLACE FUNCTION ev_graph_checkpoints() RETURNS TRIGGER AS $$
DECLARE
    who VARCHAR(24);
BEGIN
    SELECT agent_id INTO who FROM agent_runs WHERE id = NEW.agent_run_id;
    PERFORM emit_protocol_event(
        'NODE_COMPLETED', 'graph_checkpoints', NEW.id::text, who, 'SIMULATION',
        jsonb_build_object('node', NEW.node, 'seq', NEW.seq,
                           'agent_run_id', NEW.agent_run_id,
                           'latency_ms', NEW.latency_ms,
                           'output_hash', NEW.output_hash));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ev_graph_checkpoints ON graph_checkpoints;
CREATE TRIGGER trg_ev_graph_checkpoints AFTER INSERT ON graph_checkpoints
    FOR EACH ROW EXECUTE FUNCTION ev_graph_checkpoints();

-- ── predictions ──────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION ev_predictions() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        PERFORM emit_protocol_event(
            'PREDICTION_' || NEW.status, 'predictions', NEW.id::text,
            NEW.agent_id, 'SIMULATION',
            jsonb_build_object('asset', NEW.asset, 'direction', NEW.direction,
                               'expected_return', NEW.expected_return,
                               'confidence', NEW.confidence,
                               'prediction_hash', NEW.prediction_hash,
                               'committed_at', NEW.committed_at,
                               'horizon_end', NEW.horizon_end));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ev_predictions ON predictions;
CREATE TRIGGER trg_ev_predictions AFTER INSERT OR UPDATE ON predictions
    FOR EACH ROW EXECUTE FUNCTION ev_predictions();

-- ── outcomes ─────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION ev_prediction_outcomes() RETURNS TRIGGER AS $$
DECLARE
    who VARCHAR(24);
    what VARCHAR(16);
BEGIN
    SELECT agent_id, asset INTO who, what FROM predictions WHERE id = NEW.prediction_id;
    PERFORM emit_protocol_event(
        CASE WHEN NEW.evaluation_score IS NULL THEN 'PREDICTION_SETTLED'
             ELSE 'PREDICTION_SCORED' END,
        'prediction_outcomes', NEW.prediction_id::text, who, NEW.data_source,
        jsonb_build_object('asset', what,
                           'actual_return', NEW.actual_return,
                           'error', NEW.error,
                           'direction_correct', NEW.direction_correct,
                           'evaluation_score', NEW.evaluation_score,
                           'settled_at', NEW.settled_at));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ev_prediction_outcomes ON prediction_outcomes;
CREATE TRIGGER trg_ev_prediction_outcomes AFTER INSERT OR UPDATE ON prediction_outcomes
    FOR EACH ROW EXECUTE FUNCTION ev_prediction_outcomes();

-- ── reputation ───────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION ev_reputation_scores() RETURNS TRIGGER AS $$
BEGIN
    PERFORM emit_protocol_event(
        'REPUTATION_UPDATED', 'reputation_scores', NEW.id::text, NEW.agent_id,
        coalesce(NEW.dimensions->>'_data_source', 'SIMULATION'),
        jsonb_build_object('iris_score', NEW.iris_score,
                           'dimensions', NEW.dimensions,
                           'weights', NEW.weights));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ev_reputation_scores ON reputation_scores;
CREATE TRIGGER trg_ev_reputation_scores AFTER INSERT ON reputation_scores
    FOR EACH ROW EXECUTE FUNCTION ev_reputation_scores();

-- ── allocation ───────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION ev_allocation_history() RETURNS TRIGGER AS $$
BEGIN
    PERFORM emit_protocol_event(
        'ALLOCATION_UPDATED', 'allocation_history', NEW.id::text, NEW.agent_id,
        'SIMULATION',
        jsonb_build_object('step', NEW.step, 'weight', NEW.weight,
                           'score', NEW.score, 'eta', NEW.eta,
                           'vault_id', NEW.vault_id));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ev_allocation_history ON allocation_history;
CREATE TRIGGER trg_ev_allocation_history AFTER INSERT ON allocation_history
    FOR EACH ROW EXECUTE FUNCTION ev_allocation_history();

-- ── risk and slashing ────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION ev_risk_events() RETURNS TRIGGER AS $$
BEGIN
    PERFORM emit_protocol_event(
        'RISK_' || NEW.kind, 'risk_events', NEW.id::text, NEW.agent_id,
        NEW.data_source,
        jsonb_build_object('kind', NEW.kind, 'severity', NEW.severity,
                           'measured_bps', NEW.measured_bps,
                           'limit_bps', NEW.limit_bps, 'detail', NEW.detail));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ev_risk_events ON risk_events;
CREATE TRIGGER trg_ev_risk_events AFTER INSERT ON risk_events
    FOR EACH ROW EXECUTE FUNCTION ev_risk_events();

CREATE OR REPLACE FUNCTION ev_slash_events() RETURNS TRIGGER AS $$
BEGIN
    PERFORM emit_protocol_event(
        'AGENT_SLASHED', 'slash_events', NEW.id::text, NEW.agent_id,
        NEW.data_source,
        jsonb_build_object('drawdown_bps', NEW.drawdown_bps,
                           'slash_bps', NEW.slash_bps,
                           'amount_slashed', NEW.amount_slashed,
                           'risk_event_id', NEW.risk_event_id));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ev_slash_events ON slash_events;
CREATE TRIGGER trg_ev_slash_events AFTER INSERT ON slash_events
    FOR EACH ROW EXECUTE FUNCTION ev_slash_events();

-- ── agent status ─────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION ev_agents() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        PERFORM emit_protocol_event(
            'AGENT_' || NEW.status, 'agents', NEW.id, NEW.id, 'SIMULATION',
            jsonb_build_object('from', OLD.status, 'to', NEW.status,
                               'retirement_reason', NEW.retirement_reason));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ev_agents ON agents;
CREATE TRIGGER trg_ev_agents AFTER UPDATE OF status ON agents
    FOR EACH ROW EXECUTE FUNCTION ev_agents();
