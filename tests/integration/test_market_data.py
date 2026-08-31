"""
The market data layer against a real database — Phase 13.

Migration 0005 makes three claims structural, and the point of these tests is
that the *database* refuses, not that the application declines to ask:

  1. a recorded observation of a real market cannot be restated or deleted;
  2. a price that is not a usable number never lands at all;
  3. the same tick cannot be written twice by the ingest pipeline.

Then the property the whole phase turns on: a price series must never splice
two universes together. BTC is near 77,000 on an exchange and near 100 on the
synthetic tape, so a window or a settlement that crosses between them is not
slightly wrong — it reports a return of tens of thousands of percent, and
every score, weight and slash computed from it is a description of the splice.

Every test runs inside a transaction that is rolled back.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.evaluation.prices import (  # noqa: E402
    SOURCE_RANK,
    latest_window,
    price_at,
    record_price,
    strongest_source,
)
from agents.evaluation.settlement import settle_one  # noqa: E402
from agents.market.ingest import (  # noqa: E402
    feed_status,
    live_coverage,
    record_observation,
)

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")
AGENT = "AGT-AXIOM"


@pytest.fixture
def conn():
    c = psycopg.connect(DSN)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


def unique_asset(tag: str) -> str:
    """Isolate each test's tape; a shared asset leaks prices between tests."""
    return f"T{tag[:6]}{uuid.uuid4().hex[:6]}".upper()[:16]


def live(conn, *, asset, price, at, provider="binance", mode="backfill") -> bool:
    return record_observation(
        conn, asset=asset, price=price, at=at, source="LIVE",
        provider=provider, ingest_mode=mode,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. A real observation is immutable
# ─────────────────────────────────────────────────────────────────────────────

def test_a_live_price_cannot_be_restated(conn, now):
    """
    The evidence every reputation score rests on.

    Invariant 2 froze the prediction. Without this, the thing the prediction is
    judged against stays editable — so anyone holding the connection string can
    rewrite every score in the system after the fact, and no audit of the
    predictions table would show it.
    """
    asset = unique_asset("immut")
    live(conn, asset=asset, price=77_000.0, at=now)
    pid = conn.execute(
        "select id from market_events where asset = %s", (asset,)
    ).fetchone()[0]

    with pytest.raises(psycopg.errors.IntegrityConstraintViolation,
                       match="cannot be restated"):
        conn.execute(
            "update market_events set payload = %s where id = %s",
            ('{"price": 1.0}', pid),
        )
    conn.rollback()


@pytest.mark.parametrize(
    "column, value",
    [
        ("asset", "OTHER"),
        ("source", "SIMULATION"),
        ("provider", "coinbase"),
        ("ingest_mode", "stream"),
    ],
)
def test_no_measured_field_of_a_live_price_may_change(conn, now, column, value):
    asset = unique_asset("field")
    live(conn, asset=asset, price=77_000.0, at=now)
    pid = conn.execute(
        "select id from market_events where asset = %s", (asset,)
    ).fetchone()[0]

    with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
        conn.execute(
            f"update market_events set {column} = %s where id = %s", (value, pid)
        )
    conn.rollback()


def test_the_timestamp_of_an_observation_cannot_move(conn, now):
    """
    Moving `occurred_at` is the subtlest possible rewrite: the price is
    untouched, and the observation simply comes to describe a different minute
    — which is enough to change which prediction it settles.
    """
    asset = unique_asset("when")
    live(conn, asset=asset, price=77_000.0, at=now)
    pid = conn.execute(
        "select id from market_events where asset = %s", (asset,)
    ).fetchone()[0]

    with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
        conn.execute(
            "update market_events set occurred_at = %s where id = %s",
            (now + timedelta(hours=1), pid),
        )
    conn.rollback()


def test_a_live_price_cannot_be_deleted(conn, now):
    asset = unique_asset("del")
    live(conn, asset=asset, price=77_000.0, at=now)

    with pytest.raises(psycopg.errors.IntegrityConstraintViolation,
                       match="cannot be deleted"):
        conn.execute("delete from market_events where asset = %s", (asset,))
    conn.rollback()


def test_a_simulated_price_may_be_deleted(conn, now):
    """
    Deliberately asymmetric. A synthetic tape is a fixture and makes no claim
    about the world; forbidding its removal would make the schema enforce a
    property of the *feed* on every writer, and leave tests unable to clean up
    after themselves.
    """
    asset = unique_asset("simdel")
    record_price(conn, asset=asset, price=100.0, at=now, source="SIMULATION")
    conn.execute("delete from market_events where asset = %s", (asset,))
    assert conn.execute(
        "select count(*) from market_events where asset = %s", (asset,)
    ).fetchone()[0] == 0


def test_an_unchanged_update_is_allowed(conn, now):
    """The guard rejects restatement, not every UPDATE that touches the row."""
    asset = unique_asset("noop")
    live(conn, asset=asset, price=77_000.0, at=now)
    pid = conn.execute(
        "select id from market_events where asset = %s", (asset,)
    ).fetchone()[0]
    conn.execute("update market_events set embedding = NULL where id = %s", (pid,))


# ─────────────────────────────────────────────────────────────────────────────
# 2. A price must be a price
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_an_unusable_price_never_lands(conn, now, bad):
    """
    `realised_return` divides by the entry price. A zero makes the return
    infinite and a negative flips its sign — and by the time either reached an
    IRIS Score nothing could tell it from a real number.
    """
    asset = unique_asset("bad")
    with pytest.raises(psycopg.errors.IntegrityConstraintViolation,
                       match="unusable price"):
        live(conn, asset=asset, price=bad, at=now)
    conn.rollback()


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_float_is_rejected_before_it_is_even_a_row(conn, now, bad):
    """
    JSON has no NaN or Infinity, so Postgres refuses the literal outright and
    the trigger never sees it. Asserted anyway: the guarantee that matters is
    that the value does not land, not which layer stops it — and a future
    switch to a serialiser that happily writes `NaN` would silently move this
    from an error to a stored value.
    """
    asset = unique_asset("nonfin")
    with pytest.raises(psycopg.Error):
        live(conn, asset=asset, price=bad, at=now)
    conn.rollback()
    assert conn.execute(
        "select count(*) from market_events where asset = %s", (asset,)
    ).fetchone()[0] == 0


def test_a_nan_smuggled_in_as_a_string_is_caught_by_the_trigger(conn, now):
    """
    The case the trigger exists for.

    `{"price": "NaN"}` is perfectly valid JSON, and Postgres casts the string
    'NaN' to a genuine floating-point NaN without complaint. It would then
    propagate through every average computed over it, all the way into a
    reputation score, poisoning each one silently.
    """
    asset = unique_asset("nanstr")
    with pytest.raises(psycopg.errors.IntegrityConstraintViolation,
                       match="unusable price"):
        conn.execute(
            """insert into market_events (asset, kind, payload, source, occurred_at)
               values (%s, 'PRICE', '{"price": "NaN"}', 'SIMULATION', %s)""",
            (asset, now),
        )
    conn.rollback()


def test_a_price_that_is_not_a_number_at_all_is_refused(conn, now):
    asset = unique_asset("word")
    with pytest.raises(psycopg.errors.IntegrityConstraintViolation,
                       match="non-numeric price"):
        conn.execute(
            """insert into market_events (asset, kind, payload, source, occurred_at)
               values (%s, 'PRICE', '{"price": "cheap"}', 'SIMULATION', %s)""",
            (asset, now),
        )
    conn.rollback()


def test_an_observation_with_no_price_is_refused(conn, now):
    asset = unique_asset("noprice")
    with pytest.raises(psycopg.errors.IntegrityConstraintViolation,
                       match="carries no price"):
        conn.execute(
            """insert into market_events (asset, kind, payload, source, occurred_at)
               values (%s, 'PRICE', '{"volume": 3}', 'SIMULATION', %s)""",
            (asset, now),
        )
    conn.rollback()


def test_a_non_price_event_is_not_forced_to_carry_one(conn, now):
    """The guard is about prices; news and regime events have no price field."""
    asset = unique_asset("news")
    conn.execute(
        """insert into market_events (asset, kind, payload, source, occurred_at)
           values (%s, 'REGIME', '{"regime": "STRESSED"}', 'SIMULATION', %s)""",
        (asset, now),
    )


def test_claiming_LIVE_requires_naming_the_venue(conn, now):
    """
    The constraint that stops synthetic data from being relabelled real. To
    claim a price came from a market, you must say which one.
    """
    asset = unique_asset("novenue")
    with pytest.raises(psycopg.errors.CheckViolation,
                       match="market_events_live_names_its_venue"):
        conn.execute(
            """insert into market_events
                   (asset, kind, payload, source, provider, occurred_at)
               values (%s, 'PRICE', '{"price": 77000}', 'LIVE', NULL, %s)""",
            (asset, now),
        )
    conn.rollback()


def test_an_unknown_source_label_is_refused(conn, now):
    asset = unique_asset("src")
    with pytest.raises(psycopg.errors.CheckViolation,
                       match="market_events_source_known"):
        conn.execute(
            """insert into market_events
                   (asset, kind, payload, source, occurred_at)
               values (%s, 'PRICE', '{"price": 1}', 'REALTIME', %s)""",
            (asset, now),
        )
    conn.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# 3. The same tick must not land twice
# ─────────────────────────────────────────────────────────────────────────────

def test_the_ingest_pipeline_is_idempotent(conn, now):
    """
    A poller retrying after a timeout, or a backfill overlapping a stream,
    would otherwise write the same minute repeatedly — double-weighting it in
    every window computed over the tape, which makes volatility look real.
    """
    asset = unique_asset("dedupe")
    assert live(conn, asset=asset, price=77_000.0, at=now) is True
    assert live(conn, asset=asset, price=77_000.0, at=now) is False
    assert conn.execute(
        "select count(*) from market_events where asset = %s", (asset,)
    ).fetchone()[0] == 1


def test_a_conflicting_tick_does_not_overwrite_the_first(conn, now):
    """
    ON CONFLICT DO NOTHING, not DO UPDATE. The first observation of a minute is
    the record; a retry must not restate it — which the immutability trigger
    would refuse anyway.
    """
    asset = unique_asset("first")
    live(conn, asset=asset, price=77_000.0, at=now)
    live(conn, asset=asset, price=1.0, at=now)
    price = conn.execute(
        "select (payload->>'price')::float8 from market_events where asset = %s",
        (asset,),
    ).fetchone()[0]
    assert price == 77_000.0


def test_deduplication_does_not_constrain_the_simulator(conn, now):
    """
    The unique index is partial — only rows carrying a provider. A test or the
    simulator may legitimately write two observations at one instant, for
    instance to assert that `price_at` picks the nearest.
    """
    asset = unique_asset("sim2")
    record_price(conn, asset=asset, price=100.0, at=now, source="SIMULATION")
    record_price(conn, asset=asset, price=101.0, at=now, source="SIMULATION")
    assert conn.execute(
        "select count(*) from market_events where asset = %s", (asset,)
    ).fetchone()[0] == 2


def test_two_venues_may_both_record_the_same_minute(conn, now):
    """
    Deduplication is per source, not global. Two venues observing one minute
    are two facts; the tape simply must not mix them, which is a different
    rule and is tested below.
    """
    asset = unique_asset("twovenue")
    assert live(conn, asset=asset, price=77_000.0, at=now, provider="binance")
    # Same key except the venue, so the partial unique index does not collide.
    conn.execute(
        """insert into market_events
               (asset, kind, payload, source, provider, ingest_mode, occurred_at)
           values (%s, 'PRICE', '{"price": 77010}', 'TESTNET', 'coinbase',
                   'backfill', %s)""",
        (asset, now),
    )
    assert conn.execute(
        "select count(*) from market_events where asset = %s", (asset,)
    ).fetchone()[0] == 2


# ─────────────────────────────────────────────────────────────────────────────
# One asset, one price universe
# ─────────────────────────────────────────────────────────────────────────────

def test_a_real_price_outranks_a_nearer_simulated_one(conn, now):
    """
    Source beats proximity, and it has to.

    With a synthetic tape near 100 and an exchange near 77,000 covering the
    same instant, "nearest observation" is a coin flip between two universes —
    and a settlement that lands on different sides of it reports a return of
    roughly 77,000%.
    """
    asset = unique_asset("rank")
    record_price(conn, asset=asset, price=100.0, at=now, source="SIMULATION")
    live(conn, asset=asset, price=77_000.0, at=now - timedelta(seconds=120))

    observed = price_at(conn, asset=asset, at=now)
    assert observed is not None
    assert observed.source == "LIVE"
    assert observed.price == 77_000.0


def test_the_window_never_splices_two_sources(conn, now):
    asset = unique_asset("splice")
    for i in range(40):
        at = now - timedelta(minutes=40 - i)
        live(conn, asset=asset, price=77_000.0 + i, at=at)
        record_price(conn, asset=asset, price=100.0 + i, at=at, source="SIMULATION")

    window = latest_window(conn, asset=asset, size=40)
    assert len(window) == 40
    assert {o.source for o in window} == {"LIVE"}
    assert all(o.price > 1_000 for o in window)


def test_the_window_can_be_pinned_to_the_simulated_tape(conn, now):
    """The preference is a default, not a lock — a caller may still ask."""
    asset = unique_asset("pin")
    for i in range(10):
        at = now - timedelta(minutes=10 - i)
        live(conn, asset=asset, price=77_000.0 + i, at=at)
        record_price(conn, asset=asset, price=100.0 + i, at=at, source="SIMULATION")

    window = latest_window(conn, asset=asset, size=10, source="SIMULATION")
    assert {o.source for o in window} == {"SIMULATION"}


def test_the_strongest_available_source_is_chosen_not_the_best_imaginable(conn, now):
    """
    With no live data the answer is SIMULATION, not None and not a refusal.
    Section 0c is satisfied by saying what the data is, not by declining to
    run on it.
    """
    asset = unique_asset("weak")
    record_price(conn, asset=asset, price=100.0, at=now, source="SIMULATION")
    assert strongest_source(conn, asset=asset) == "SIMULATION"

    live(conn, asset=asset, price=77_000.0, at=now)
    assert strongest_source(conn, asset=asset) == "LIVE"


def test_source_rank_orders_provenance_from_weakest_to_strongest():
    assert SOURCE_RANK["LIVE"] > SOURCE_RANK["TESTNET"] > SOURCE_RANK["SIMULATION"]


def test_a_stale_window_is_reported_as_absent(conn, now):
    """
    A feed that stopped an hour ago still returns rows. `max_age` is what turns
    "there is data" into "there is data about now".
    """
    asset = unique_asset("stale")
    for i in range(40):
        live(conn, asset=asset, price=77_000.0 + i,
             at=now - timedelta(hours=6) + timedelta(minutes=i))

    assert latest_window(conn, asset=asset, size=40) != []
    assert latest_window(conn, asset=asset, size=40,
                         max_age=timedelta(minutes=30)) == []


# ─────────────────────────────────────────────────────────────────────────────
# Settlement pins both legs to one universe
# ─────────────────────────────────────────────────────────────────────────────

def commit_prediction(conn, *, asset, committed_at, horizon_seconds=600,
                      direction="BUY", expected_return=0.001):
    model_version_id = conn.execute(
        "select id from model_versions where agent_id = %s limit 1", (AGENT,)
    ).fetchone()[0]
    pid = str(uuid.uuid4())
    conn.execute(
        """
        insert into predictions
            (id, agent_id, model_version_id, asset, direction, expected_return,
             confidence, horizon_seconds, prediction_hash, status,
             predicted_at, committed_at, horizon_end)
        values (%s, %s, %s, %s, %s, %s, 0.8, %s, %s, 'COMMITTED', %s, %s, %s)
        """,
        (pid, AGENT, model_version_id, asset, direction, expected_return,
         horizon_seconds, uuid.uuid4().hex + uuid.uuid4().hex[:32],
         committed_at, committed_at,
         committed_at + timedelta(seconds=horizon_seconds)),
    )
    return conn.execute(
        """select id, agent_id, asset, direction, expected_return, confidence,
                  committed_at, horizon_end, status
             from predictions where id = %s""",
        (pid,),
    ).fetchone()


def test_settlement_refuses_to_measure_across_two_universes(conn, now):
    """
    The bug this whole phase is shaped around, in its most dangerous form.

    Entry has only a simulated price near 100; exit has only a real one near
    77,000. Unpinned, the return is +76,900% — a number that flows straight
    into an IRIS Score, a risk breach and a slash, and looks like nothing but a
    spectacular agent. Pinned, the exit leg is simply missing and the
    prediction stays WAITING_FOR_OUTCOME: a gap in the record instead of a lie
    in it.
    """
    asset = unique_asset("cross")
    committed = now - timedelta(minutes=30)
    row = commit_prediction(conn, asset=asset, committed_at=committed)

    record_price(conn, asset=asset, price=100.0, at=committed, source="SIMULATION")
    live(conn, asset=asset, price=77_000.0, at=committed + timedelta(seconds=600))

    assert settle_one(conn, row) is None
    assert conn.execute(
        "select status from predictions where id = %s", (row[0],)
    ).fetchone()[0] == "WAITING_FOR_OUTCOME"


def test_settlement_measures_within_one_universe(conn, now):
    asset = unique_asset("within")
    committed = now - timedelta(minutes=30)
    row = commit_prediction(conn, asset=asset, committed_at=committed)

    live(conn, asset=asset, price=77_000.0, at=committed)
    live(conn, asset=asset, price=77_770.0, at=committed + timedelta(seconds=600))

    settlement = settle_one(conn, row)
    assert settlement is not None
    assert settlement.data_source == "LIVE"
    assert settlement.actual_return == pytest.approx(0.01, rel=1e-6)


def test_settlement_does_not_cross_between_two_venues(conn, now):
    """
    The plausible version of the same bug, and therefore the worse one.

    Two exchanges quoting BTC sit a few basis points apart. A settlement with
    an entry from one and an exit from the other produces a perfectly
    believable return that is really the spread between two instruments,
    credited to the agent as judgement.
    """
    asset = unique_asset("venue")
    committed = now - timedelta(minutes=30)
    row = commit_prediction(conn, asset=asset, committed_at=committed)

    live(conn, asset=asset, price=77_000.0, at=committed, provider="binance")
    live(conn, asset=asset, price=77_030.0,
         at=committed + timedelta(seconds=600), provider="coinbase")

    assert settle_one(conn, row) is None
    assert conn.execute(
        "select status from predictions where id = %s", (row[0],)
    ).fetchone()[0] == "WAITING_FOR_OUTCOME"


def test_a_settled_live_outcome_is_labelled_live(conn, now):
    """The label the UI reads has to be earned by both legs, and here it is."""
    asset = unique_asset("label")
    committed = now - timedelta(minutes=30)
    row = commit_prediction(conn, asset=asset, committed_at=committed)
    live(conn, asset=asset, price=77_000.0, at=committed)
    live(conn, asset=asset, price=77_100.0, at=committed + timedelta(seconds=600))

    settle_one(conn, row)
    assert conn.execute(
        "select data_source from prediction_outcomes where prediction_id = %s",
        (row[0],),
    ).fetchone()[0] == "LIVE"


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

def test_coverage_counts_minutes_rather_than_rows(conn, now):
    """
    A thousand observations of one minute and a thousand spread over a day
    support very different claims, and only the second lets a model compute a
    window or a settlement find both its legs.
    """
    asset = unique_asset("cover")
    for _ in range(50):
        # 50 rows, one minute — each a distinct instant so dedupe allows them
        live(conn, asset=asset, price=77_000.0,
             at=now - timedelta(seconds=_ % 60, microseconds=_))

    result = live_coverage(conn, asset=asset, minutes=240)
    assert result["observations"] >= 50
    assert result["distinct_minutes"] <= 2
    assert result["coverage"] < 0.02


def test_feed_status_reports_staleness_per_source(conn, now):
    asset = unique_asset("status")
    live(conn, asset=asset, price=77_000.0, at=now)
    record_price(conn, asset=asset, price=100.0,
                 at=now - timedelta(hours=8), source="SIMULATION")

    rows = {r["source"]: r for r in feed_status(conn, assets=[asset])}
    assert rows["LIVE"]["stale"] is False
    assert rows["LIVE"]["provider"] == "binance"
    # A feed that stopped eight hours ago is indistinguishable from a calm
    # market unless something says so.
    assert rows["SIMULATION"]["stale"] is True
