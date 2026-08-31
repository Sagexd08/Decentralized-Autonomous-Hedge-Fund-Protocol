-- IRIS Protocol — the market data layer becomes real.
-- IRIS_BUILD_PROMPT v2.0 sections 0c, 5 and 13. Phase 13.
--
-- Until now every price in this system came from a seeded Ornstein-Uhlenbeck
-- tape. `market_events.source` already carried the honesty label, and that
-- label rode through settlement into `prediction_outcomes.data_source` and out
-- to the UI — so nothing was ever misrepresented. But the column only ever
-- held one value.
--
-- This migration is what has to be true of the table before a *real* exchange
-- observation is allowed into it. Three things, in order of how much they
-- matter:
--
--   1. A real observation is immutable. Once the protocol has written down
--      what the market did at an instant, that is the ground truth every
--      agent's reputation is computed from. If it can be edited afterwards,
--      every score in the system can be rewritten retroactively by whoever
--      holds the connection string — and the commit-before-outcome primitive
--      in section 5 protects the claim but not the evidence. Invariant 2
--      froze the prediction. This freezes the thing it is judged against.
--
--   2. A price must be a price. A NULL, a zero, a negative or a NaN in this
--      payload becomes an infinite or sign-flipped return in
--      `realised_return`, and that number goes straight into an IRIS Score.
--
--   3. The same tick must not land twice. A poller that retries, or a backfill
--      overlapping a stream, would otherwise double-weight one minute of the
--      market in every window computed over it.

-- ─────────────────────────────────────────────────────────────────────────────
-- Provenance gets more precise
-- ─────────────────────────────────────────────────────────────────────────────

-- Which venue said so. NULL for the simulated tape, which has no venue — and
-- that NULL is load-bearing below, since it is what separates a row the ingest
-- pipeline wrote from a row a test or the simulator wrote.
ALTER TABLE market_events ADD COLUMN IF NOT EXISTS provider VARCHAR(32);

-- How it arrived: 'stream' for a tick observed near-live, 'backfill' for a
-- candle read from history. Both are real observations of a real market; they
-- differ in how far behind the clock they were when recorded, and section 0c
-- asks for historical data to be identifiable as such rather than blended in.
ALTER TABLE market_events ADD COLUMN IF NOT EXISTS ingest_mode VARCHAR(16);

DO $$ BEGIN
    ALTER TABLE market_events
        ADD CONSTRAINT market_events_source_known
        CHECK (source IN ('SIMULATION', 'TESTNET', 'LIVE'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE market_events
        ADD CONSTRAINT market_events_ingest_mode_known
        CHECK (ingest_mode IS NULL OR ingest_mode IN ('stream', 'backfill', 'seed'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- A venue is required for a real observation and meaningless without one.
-- This is the constraint that stops synthetic data being relabelled LIVE by a
-- careless insert: to claim LIVE you must name who said so.
DO $$ BEGIN
    ALTER TABLE market_events
        ADD CONSTRAINT market_events_live_names_its_venue
        CHECK (source <> 'LIVE' OR provider IS NOT NULL);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. A price must be a price
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION market_events_price_is_usable()
RETURNS TRIGGER AS $fn$
DECLARE
    raw   TEXT;
    value DOUBLE PRECISION;
BEGIN
    IF NEW.kind <> 'PRICE' THEN
        RETURN NEW;
    END IF;

    raw := NEW.payload->>'price';
    IF raw IS NULL THEN
        RAISE EXCEPTION
            'market observation for % at % carries no price',
            NEW.asset, NEW.occurred_at
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    BEGIN
        value := raw::DOUBLE PRECISION;
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION
            'market observation for % at % has a non-numeric price (%)',
            NEW.asset, NEW.occurred_at, raw
            USING ERRCODE = 'integrity_constraint_violation';
    END;

    -- A settled outcome divides by this number. Zero, negative or non-finite
    -- makes the resulting return meaningless rather than merely wrong, and by
    -- the time it reached a reputation score it would be indistinguishable
    -- from a real one.
    --
    -- NaN is tested by equality against 'NaN', not by the usual `value <>
    -- value`. Postgres deliberately departs from IEEE 754 here: it defines
    -- NaN = NaN as TRUE so that floats have a total order and can be indexed
    -- and sorted. So the idiomatic self-inequality check silently never fires,
    -- and `{"price": "NaN"}` — valid JSON, cast to a real NaN without
    -- complaint — went straight into the table until a test asked it to.
    IF value IS NULL
       OR value =  'NaN'::DOUBLE PRECISION
       OR value =  'Infinity'::DOUBLE PRECISION
       OR value = '-Infinity'::DOUBLE PRECISION
       OR value <= 0 THEN
        RAISE EXCEPTION
            'market observation for % at % has an unusable price (%)',
            NEW.asset, NEW.occurred_at, raw
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_market_events_price_is_usable ON market_events;
CREATE TRIGGER trg_market_events_price_is_usable
    BEFORE INSERT OR UPDATE ON market_events
    FOR EACH ROW EXECUTE FUNCTION market_events_price_is_usable();

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. The same tick must not land twice
-- ─────────────────────────────────────────────────────────────────────────────

-- Deduplicate anything written before this index existed. Deliberately ordered
-- before the delete guard below: after that trigger exists, a LIVE row cannot
-- be removed even to repair a duplicate.
DELETE FROM market_events a
 USING market_events b
 WHERE a.provider IS NOT NULL
   AND b.provider IS NOT NULL
   AND a.ctid < b.ctid
   AND a.asset = b.asset
   AND a.kind = b.kind
   AND a.occurred_at = b.occurred_at
   AND a.source = b.source;

-- Partial, on purpose. Only rows the ingest pipeline wrote carry a provider,
-- so only those are deduplicated. A test or the simulator may legitimately
-- write two observations at the same instant — for instance to assert that
-- `price_at` picks the nearest — and forbidding that would make the schema
-- enforce a property of the feed on every writer.
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_events_ingested_tick
    ON market_events (asset, kind, occurred_at, source)
    WHERE provider IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_market_events_source
    ON market_events (asset, source, occurred_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. A real observation is immutable
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION market_events_reject_restatement()
RETURNS TRIGGER AS $fn$
BEGIN
    -- The measured facts. `embedding` is excluded deliberately: it is a
    -- derived index over the payload, recomputable at any time, and carries no
    -- claim about what the market did.
    IF NEW.asset       IS DISTINCT FROM OLD.asset
    OR NEW.kind        IS DISTINCT FROM OLD.kind
    OR NEW.payload     IS DISTINCT FROM OLD.payload
    OR NEW.source      IS DISTINCT FROM OLD.source
    OR NEW.provider    IS DISTINCT FROM OLD.provider
    OR NEW.ingest_mode IS DISTINCT FROM OLD.ingest_mode
    OR NEW.occurred_at IS DISTINCT FROM OLD.occurred_at THEN
        RAISE EXCEPTION
            'market observation % (% at %) is the evidence predictions are settled against and cannot be restated',
            OLD.id, OLD.asset, OLD.occurred_at
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_market_events_reject_restatement ON market_events;
CREATE TRIGGER trg_market_events_reject_restatement
    BEFORE UPDATE ON market_events
    FOR EACH ROW EXECUTE FUNCTION market_events_reject_restatement();

CREATE OR REPLACE FUNCTION market_events_reject_erasure()
RETURNS TRIGGER AS $fn$
BEGIN
    -- Simulated rows are fixtures and may be thrown away; a synthetic tape
    -- makes no claim about the world. A record of what a real market actually
    -- did is not ours to delete, because agents' scores already rest on it.
    IF OLD.source = 'LIVE' THEN
        RAISE EXCEPTION
            'market observation % (% at %, from %) is a record of a real market and cannot be deleted',
            OLD.id, OLD.asset, OLD.occurred_at, COALESCE(OLD.provider, 'unknown')
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN OLD;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_market_events_reject_erasure ON market_events;
CREATE TRIGGER trg_market_events_reject_erasure
    BEFORE DELETE ON market_events
    FOR EACH ROW EXECUTE FUNCTION market_events_reject_erasure();

-- ─────────────────────────────────────────────────────────────────────────────
-- Feed health, as a query rather than a guess
-- ─────────────────────────────────────────────────────────────────────────────

-- The API's /api/market/health reads this. A feed that has silently stopped
-- looks exactly like a calm market from the outside — the difference is `lag`,
-- so it is computed here next to the data rather than inferred by a caller.
CREATE OR REPLACE VIEW market_feed_status AS
SELECT
    asset,
    source,
    provider,
    COUNT(*)                                            AS observations,
    MIN(occurred_at)                                    AS first_seen,
    MAX(occurred_at)                                    AS last_seen,
    EXTRACT(EPOCH FROM (NOW() - MAX(occurred_at)))::INT AS lag_seconds
  FROM market_events
 WHERE kind = 'PRICE'
 GROUP BY asset, source, provider;
