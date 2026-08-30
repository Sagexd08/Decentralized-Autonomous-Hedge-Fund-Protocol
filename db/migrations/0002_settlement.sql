-- ═════════════════════════════════════════════════════════════════════════════
-- IRIS — Phase 5: prediction settlement and evaluation
-- IRIS_BUILD_PROMPT v2.0 sections 5 and 13, invariant 2.
--
-- Invariant 2: "Predictions are immutable once committed."
--
-- Phase 3 gave that invariant a hash and a CHECK on the timestamps. Neither
-- actually stops an UPDATE. `prediction_hash` is UNIQUE, so rewriting a claim
-- and *not* rehashing it leaves the hash pointing at bytes that no longer
-- exist — the record still verifies against itself only because nobody
-- recomputes it. This migration closes that: the database refuses the write.
--
-- Everything here is enforcement, not convention. An application-layer rule
-- protects against the code you wrote; a trigger protects against the psql
-- session, the migration script, and the next developer.
-- ═════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. A committed prediction's claim can never be rewritten
-- ─────────────────────────────────────────────────────────────────────────────

-- The columns that constitute the claim. `status` and `solana_sig` are not
-- here: the lifecycle has to be able to advance (COMMITTED -> SETTLED ->
-- EVALUATED) and the on-chain signature arrives after the commit. Everything
-- the hash covers is frozen.
CREATE OR REPLACE FUNCTION predictions_reject_claim_rewrite()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'PREDICTED' THEN
        RETURN NEW;   -- not yet committed; still a draft
    END IF;

    IF NEW.agent_id         IS DISTINCT FROM OLD.agent_id
    OR NEW.model_version_id IS DISTINCT FROM OLD.model_version_id
    OR NEW.asset            IS DISTINCT FROM OLD.asset
    OR NEW.direction        IS DISTINCT FROM OLD.direction
    OR NEW.expected_return  IS DISTINCT FROM OLD.expected_return
    OR NEW.confidence       IS DISTINCT FROM OLD.confidence
    OR NEW.horizon_seconds  IS DISTINCT FROM OLD.horizon_seconds
    OR NEW.prediction_hash  IS DISTINCT FROM OLD.prediction_hash
    OR NEW.predicted_at     IS DISTINCT FROM OLD.predicted_at
    OR NEW.committed_at     IS DISTINCT FROM OLD.committed_at
    OR NEW.horizon_end      IS DISTINCT FROM OLD.horizon_end
    THEN
        RAISE EXCEPTION
            'prediction % is committed; its claim is immutable (invariant 2)',
            OLD.id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_predictions_immutable ON predictions;
CREATE TRIGGER trg_predictions_immutable
    BEFORE UPDATE ON predictions
    FOR EACH ROW EXECUTE FUNCTION predictions_reject_claim_rewrite();

-- Deleting a committed prediction would erase the evidence just as effectively
-- as editing it. A retired agent keeps its record; that is the point of the
-- Model Cemetery in section 15.
CREATE OR REPLACE FUNCTION predictions_reject_delete()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status <> 'PREDICTED' THEN
        RAISE EXCEPTION
            'prediction % is committed and cannot be deleted (invariant 2)',
            OLD.id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_predictions_no_delete ON predictions;
CREATE TRIGGER trg_predictions_no_delete
    BEFORE DELETE ON predictions
    FOR EACH ROW EXECUTE FUNCTION predictions_reject_delete();

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. The lifecycle only runs forwards
-- ─────────────────────────────────────────────────────────────────────────────
-- Without this, an agent having a bad week could be walked back from EVALUATED
-- to COMMITTED and re-settled against a friendlier window.

CREATE OR REPLACE FUNCTION predictions_status_is_monotonic()
RETURNS TRIGGER AS $$
DECLARE
    rank_of CONSTANT TEXT[] := ARRAY[
        'PREDICTED', 'COMMITTED', 'WAITING_FOR_OUTCOME', 'SETTLED', 'EVALUATED'
    ];
    old_rank INT := array_position(rank_of, OLD.status);
    new_rank INT := array_position(rank_of, NEW.status);
BEGIN
    IF new_rank < old_rank THEN
        RAISE EXCEPTION
            'prediction % cannot move backwards from % to %',
            OLD.id, OLD.status, NEW.status
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_predictions_status_forward ON predictions;
CREATE TRIGGER trg_predictions_status_forward
    BEFORE UPDATE OF status ON predictions
    FOR EACH ROW EXECUTE FUNCTION predictions_status_is_monotonic();

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. An outcome cannot exist before the horizon it judges
-- ─────────────────────────────────────────────────────────────────────────────
-- This is the whole commit-before-outcome primitive stated as a constraint. It
-- needs the parent row, so it cannot be a CHECK.

CREATE OR REPLACE FUNCTION outcomes_settle_after_horizon()
RETURNS TRIGGER AS $$
DECLARE
    p RECORD;
BEGIN
    SELECT committed_at, horizon_end INTO p
      FROM predictions WHERE id = NEW.prediction_id;

    IF p.committed_at IS NULL THEN
        RAISE EXCEPTION
            'prediction % was never committed; it cannot be settled',
            NEW.prediction_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF NEW.settled_at < p.horizon_end THEN
        RAISE EXCEPTION
            'outcome for prediction % settles at %, before its horizon ends at %',
            NEW.prediction_id, NEW.settled_at, p.horizon_end
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_outcomes_after_horizon ON prediction_outcomes;
CREATE TRIGGER trg_outcomes_after_horizon
    BEFORE INSERT ON prediction_outcomes
    FOR EACH ROW EXECUTE FUNCTION outcomes_settle_after_horizon();

-- An outcome's measurement is written once. Only `evaluation_score` and the
-- on-chain signature may be filled in afterwards, because scoring is a second
-- pass over an already-settled measurement.
CREATE OR REPLACE FUNCTION outcomes_reject_remeasure()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.actual_return     IS DISTINCT FROM OLD.actual_return
    OR NEW.error             IS DISTINCT FROM OLD.error
    OR NEW.direction_correct IS DISTINCT FROM OLD.direction_correct
    OR NEW.settled_at        IS DISTINCT FROM OLD.settled_at
    OR NEW.prediction_id     IS DISTINCT FROM OLD.prediction_id
    THEN
        RAISE EXCEPTION
            'outcome for prediction % is already measured and cannot be restated',
            OLD.prediction_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_outcomes_immutable ON prediction_outcomes;
CREATE TRIGGER trg_outcomes_immutable
    BEFORE UPDATE ON prediction_outcomes
    FOR EACH ROW EXECUTE FUNCTION outcomes_reject_remeasure();

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Provenance of the number the agent is judged on
-- ─────────────────────────────────────────────────────────────────────────────
-- Section 0c: simulated data must be labelled as such wherever it surfaces. An
-- outcome computed from a simulated tape is not evidence of live performance,
-- and the UI has no way to know that unless the row says so.

ALTER TABLE prediction_outcomes
    ADD COLUMN IF NOT EXISTS data_source VARCHAR(24) NOT NULL DEFAULT 'SIMULATION';

ALTER TABLE prediction_outcomes
    DROP CONSTRAINT IF EXISTS prediction_outcomes_data_source_check;
ALTER TABLE prediction_outcomes
    ADD CONSTRAINT prediction_outcomes_data_source_check
    CHECK (data_source IN ('SIMULATION', 'TESTNET', 'LIVE'));

-- The evaluation score is on the same 0-100 scale as the IRIS Score it feeds.
ALTER TABLE prediction_outcomes
    DROP CONSTRAINT IF EXISTS prediction_outcomes_score_range;
ALTER TABLE prediction_outcomes
    ADD CONSTRAINT prediction_outcomes_score_range
    CHECK (evaluation_score IS NULL OR evaluation_score BETWEEN 0 AND 100);

CREATE INDEX IF NOT EXISTS idx_outcomes_unscored
    ON prediction_outcomes(prediction_id) WHERE evaluation_score IS NULL;
