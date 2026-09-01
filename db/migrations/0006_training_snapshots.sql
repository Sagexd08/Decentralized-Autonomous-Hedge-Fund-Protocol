-- The training set's identity, legible from any process.
-- IRIS_BUILD_PROMPT v2.0 sections 0c and 12; invariant 3.
--
-- `ml.training.dataset` freezes a training series to disk and points a JSON
-- file at it. That is sufficient when one machine both fits the models and
-- serves the dashboard, and it is exactly wrong when they are different
-- machines — which is what a free deployment is: the scheduled cycle fits the
-- models and holds the snapshot, the API serves the pages and has never seen
-- it.
--
-- The consequence is not a crash, it is a misreport. `/api/market/training`
-- would answer "no training snapshot", and the §0c banner reads that field to
-- decide between "real market data" and "live prices, synthetic models" — so a
-- protocol whose models were fitted on real BTC would describe itself as
-- synthetic. That understates rather than overstates, so it is the safe
-- direction; it is still the product saying something false about itself.
--
-- Only the *identity* lives here. The series itself stays on disk next to the
-- fitted weights, because it is megabytes and nothing but a fit needs it.

CREATE TABLE IF NOT EXISTS training_snapshots (
    digest         VARCHAR(32) PRIMARY KEY,
    asset          VARCHAR(16) NOT NULL,
    source         VARCHAR(24) NOT NULL
                   CHECK (source IN ('SIMULATION', 'TESTNET', 'LIVE')),
    provider       VARCHAR(32),
    samples        INTEGER     NOT NULL CHECK (samples > 0),
    first_at       TIMESTAMPTZ,
    last_at        TIMESTAMPTZ,
    return_sd_bps  NUMERIC(10, 4),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The same rule market_events carries: a claim that data came from a real
-- market has to name which one. A snapshot labelled LIVE with no venue would
-- let a synthetic fit be reported as real, which is the specific lie the whole
-- provenance chain exists to prevent.
DO $$ BEGIN
    ALTER TABLE training_snapshots
        ADD CONSTRAINT training_snapshots_live_names_its_venue
        CHECK (source <> 'LIVE' OR provider IS NOT NULL);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_training_snapshots_recent
    ON training_snapshots (created_at DESC);

-- A snapshot is a historical fact about which weights exist, so it is append
-- only. Re-freezing the same series is a no-op (the digest is the key) rather
-- than a rewrite, and a model in the field must always be traceable to the
-- data it was fitted on — invariant 3 is meaningless if the training set's
-- record can be edited afterwards.
CREATE OR REPLACE FUNCTION training_snapshots_reject_rewrite()
RETURNS TRIGGER AS $fn$
BEGIN
    RAISE EXCEPTION
        'training snapshot % is the record of what a model was fitted on and cannot be % ',
        COALESCE(OLD.digest, NEW.digest), lower(TG_OP)
        USING ERRCODE = 'integrity_constraint_violation';
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_training_snapshots_append_only ON training_snapshots;
CREATE TRIGGER trg_training_snapshots_append_only
    BEFORE UPDATE OR DELETE ON training_snapshots
    FOR EACH ROW EXECUTE FUNCTION training_snapshots_reject_rewrite();
