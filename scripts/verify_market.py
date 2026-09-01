#!/usr/bin/env python
"""
Market data gate — real market data, end to end.

**Not a numbered phase.** IRIS_BUILD_PROMPT v2.0's Phase 13 is "simulation +
backtesting: the same seed produces the same result", and that is still
outstanding — see STATE.md, *Next phase*. This work was requested out of
sequence and is gated on its own terms rather than borrowing a phase number
whose Definition of Done it does not meet.

The protocol ran for twelve phases on a seeded Ornstein-Uhlenbeck tape. Every
number it produced was honestly labelled SIMULATION from `market_events.source`
through `prediction_outcomes.data_source` and out to the UI, so nothing was
misrepresented — but nothing was real either.

This gate asks whether the whole chain now rests on a real market, and it is
built around the observation that *every* way this can go wrong looks fine from
the outside:

  * a feed that stopped two hours ago still returns rows, and a stale tape is
    indistinguishable from a calm market;
  * a model fitted on the synthetic tape still emits confident predictions on
    live prices — overstated by roughly a factor of sixty, with an honest hash
    and an honest settlement wrapped around a number that means nothing;
  * a settlement that takes its entry from one price universe and its exit from
    another produces a return, and if the two universes are two exchanges
    rather than a simulator, that return is entirely plausible;
  * and a UI that hardcodes "simulated" is wrong in the safe direction, while a
    UI that hardcodes "live" is wrong in the direction section 0c exists to
    prevent.

So the checks are: the data is real and current, one asset means one price
series, the models were fitted on the same market they trade, the evidence
cannot be rewritten after the fact, and the page says which of those is
actually true right now.

    python scripts/verify_market.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import psycopg
except ModuleNotFoundError:  # pragma: no cover - host path
    print("dependencies unavailable here; running the gate inside the api container.",
          flush=True)
    raise SystemExit(
        subprocess.run(
            ["docker", "compose", "exec", "-T", "api",
             "python", "/repo/scripts/verify_market.py"],
        ).returncode
    )

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")
def _reachable(*candidates: str) -> str:
    """
    The first base URL that answers.

    The gate runs either on the host, where the services are on localhost, or
    inside the api container, where they are on the compose network under their
    service names. Hardcoding one made the same gate pass from one place and
    fail from the other.
    """
    for base in candidates:
        try:
            urllib.request.urlopen(base + "/health", timeout=3).close()
            return base
        except Exception:  # noqa: BLE001
            continue
    return candidates[-1]


API = os.getenv("IRIS_API_URL") or _reachable(
    "http://localhost:8000", "http://api:8000"
)
WEB = os.getenv("IRIS_WEB_URL") or _reachable(
    "http://localhost:3000", "http://web:3000"
)
ASSET = os.getenv("IRIS_GATE_ASSET", "BTC")

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
results: list[tuple[bool, str, str]] = []

# A real market's one-minute returns. Anything far outside this is either not a
# real market or not one-minute data.
MIN_REALISTIC_SD_BPS = 0.3
MAX_REALISTIC_SD_BPS = 60.0


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label, detail))
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  {mark}  {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))


def get(url: str, timeout: float = 20.0):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def text(url: str, timeout: float = 60.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "iris-gate"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def _provenance_attr(body: str) -> str:
    """What the page actually claimed, so a failure is diagnosable."""
    marker = 'data-provenance="'
    start = body.find(marker)
    if start == -1:
        return "absent"
    start += len(marker)
    return body[start:body.find('"', start)]


def main() -> int:
    print(f"\nMarket data gate — real market data, end to end ({ASSET})\n")

    # ── 1. the data is real, and it is current ──────────────────────────────
    print(f"{DIM}the feed{RESET}")

    with psycopg.connect(DSN) as conn:
        from agents.market.ingest import feed_status, live_coverage

        rows = feed_status(conn, assets=[ASSET])
        coverage = live_coverage(conn, asset=ASSET, minutes=240)
        live_rows = [r for r in rows if r["source"] == "LIVE"]

        total_live = conn.execute(
            """select count(*) from market_events
                where asset = %s and kind = 'PRICE' and source = 'LIVE'""",
            (ASSET,),
        ).fetchone()[0]

    check(bool(live_rows),
          "the protocol holds real market observations",
          f"{total_live} LIVE rows for {ASSET}")

    venues = sorted({r["provider"] for r in live_rows if r["provider"]})
    check(bool(venues),
          "every real observation names the venue that produced it",
          f"venues: {', '.join(venues) or 'none'}")

    lag = min((r["lag_seconds"] for r in live_rows
               if r["lag_seconds"] is not None), default=None)
    check(lag is not None and lag < 300,
          "the feed is current, not merely present",
          f"newest LIVE observation is {lag}s old"
          if lag is not None else "no LIVE observation at all")

    check(coverage["coverage"] >= 0.80,
          "the tape actually covers the window an agent reads",
          f"{coverage['coverage']:.0%} of the last 4h "
          f"({coverage['distinct_minutes']}/{coverage['expected_minutes']} minutes)")

    # A count of rows is not coverage, and a feed writing the same minute over
    # and over would satisfy every check above.
    with psycopg.connect(DSN) as conn:
        duplicates = conn.execute(
            """select count(*) from (
                   select asset, occurred_at, source, count(*) as n
                     from market_events
                    where asset = %s and kind = 'PRICE' and provider is not null
                    group by 1, 2, 3 having count(*) > 1
               ) d""",
            (ASSET,),
        ).fetchone()[0]
    check(duplicates == 0,
          "no minute of the market is recorded twice",
          f"{duplicates} duplicated tick(s)")

    # ── 2. the prices look like a market ────────────────────────────────────
    print(f"\n{DIM}the prices{RESET}")

    with psycopg.connect(DSN) as conn:
        series = [
            float(r[0])
            for r in conn.execute(
                """select (payload->>'price')::float8 from market_events
                    where asset = %s and kind = 'PRICE' and source = 'LIVE'
                    order by occurred_at desc limit 600""",
                (ASSET,),
            ).fetchall()
        ][::-1]

    returns = [
        (series[i] - series[i - 1]) / series[i - 1] for i in range(1, len(series))
    ] or [0.0]
    mean = sum(returns) / len(returns)
    sd_bps = (sum((r - mean) ** 2 for r in returns) / len(returns)) ** 0.5 * 10_000

    check(MIN_REALISTIC_SD_BPS <= sd_bps <= MAX_REALISTIC_SD_BPS,
          "the observed volatility is a market's, not a simulator's",
          f"one-step return sd {sd_bps:.2f}bps "
          f"(the synthetic tape's is ~60)")

    check(all(p > 0 for p in series) and len(series) > 100,
          "every recorded price is a usable number",
          f"{len(series)} observations, "
          f"{min(series):,.2f} to {max(series):,.2f}")

    # ── 3. one asset, one price series ──────────────────────────────────────
    print(f"\n{DIM}one price universe{RESET}")

    from agents.evaluation.prices import latest_window, price_at

    with psycopg.connect(DSN) as conn:
        window = latest_window(conn, asset=ASSET, size=64)
    check(bool(window) and len({o.source for o in window}) == 1
          and len({o.provider for o in window}) == 1,
          "the window an agent reads never splices two sources",
          f"{len(window)} observations, all {window[-1].source}/"
          f"{window[-1].provider}" if window else "no window")

    # The strongest source must win even when a nearer weaker one exists —
    # otherwise a settlement can land on either side of a 77,000x step.
    with psycopg.connect(DSN) as conn:
        probe = f"G13{uuid.uuid4().hex[:8]}".upper()[:16]
        now = datetime.now(timezone.utc)
        conn.execute(
            """insert into market_events (asset, kind, payload, source, occurred_at)
               values (%s, 'PRICE', '{"price": 100.0}', 'SIMULATION', %s)""",
            (probe, now),
        )
        conn.execute(
            """insert into market_events
                   (asset, kind, payload, source, provider, ingest_mode, occurred_at)
               values (%s, 'PRICE', '{"price": 77000.0}', 'LIVE', 'binance',
                       'backfill', %s)""",
            (probe, now - timedelta(seconds=120)),
        )
        chosen = price_at(conn, asset=probe, at=now)
        conn.rollback()

    check(chosen is not None and chosen.source == "LIVE",
          "a real price outranks a nearer simulated one",
          f"chose {chosen.source} at {chosen.price:,.2f}" if chosen else "chose nothing")

    # ── 4. settlement measures within one universe ──────────────────────────
    with psycopg.connect(DSN) as conn:
        from agents.evaluation.settlement import settle_one

        # An agent that actually has a registered model version. The first row
        # by id is a leftover test fixture with none, and `predictions`
        # requires one.
        agent, model_version_id = conn.execute(
            """select a.id, m.id
                 from agents a join model_versions m on m.agent_id = a.id
                where a.status <> 'RETIRED'
                order by a.id limit 1"""
        ).fetchone()

        probe = f"G13X{uuid.uuid4().hex[:7]}".upper()[:16]
        committed = datetime.now(timezone.utc) - timedelta(minutes=30)
        pid = str(uuid.uuid4())
        conn.execute(
            """insert into predictions
                   (id, agent_id, model_version_id, asset, direction,
                    expected_return, confidence, horizon_seconds,
                    prediction_hash, status, predicted_at, committed_at,
                    horizon_end)
               values (%s, %s, %s, %s, 'BUY', 0.001, 0.8, 600, %s, 'COMMITTED',
                       %s, %s, %s)""",
            (pid, agent, model_version_id, probe,
             uuid.uuid4().hex + uuid.uuid4().hex[:32],
             committed, committed, committed + timedelta(seconds=600)),
        )
        # Entry from one venue, exit from another: a plausible-looking return
        # that is really the spread between two instruments.
        for at, price, venue in (
            (committed, 77_000.0, "binance"),
            (committed + timedelta(seconds=600), 77_030.0, "coinbase"),
        ):
            conn.execute(
                """insert into market_events
                       (asset, kind, payload, source, provider, ingest_mode,
                        occurred_at)
                   values (%s, 'PRICE', %s, 'LIVE', %s, 'backfill', %s)""",
                (probe, json.dumps({"price": price}), venue, at),
            )
        row = conn.execute(
            """select id, agent_id, asset, direction, expected_return, confidence,
                      committed_at, horizon_end, status
                 from predictions where id = %s""",
            (pid,),
        ).fetchone()
        crossed = settle_one(conn, row)
        conn.rollback()

    check(crossed is None,
          "settlement refuses to measure across two venues",
          "an entry and an exit from different exchanges leaves the "
          "prediction unscored rather than crediting the spread")

    # ── 5. the models were fitted on the market they trade ──────────────────
    print(f"\n{DIM}the models{RESET}")

    training = get(f"{API}/api/market/training")
    check(bool(training.get("is_real_market_data")),
          "the models are fitted on real market data",
          training.get("description", ""))

    check(training.get("provider") in venues if venues else False,
          "the training set comes from the venue the agents trade on",
          f"trained on {training.get('provider')}, trading on {', '.join(venues)}")

    from ml.inference.artifacts import FEED_STEP_SECONDS, TRAINING_HORIZON_STEPS
    from agents.graphs.nodes import (
        DEFAULT_HORIZON_SECONDS,
        FEED_STEP_SECONDS as NODE_STEP,
    )

    check(TRAINING_HORIZON_STEPS == DEFAULT_HORIZON_SECONDS / NODE_STEP
          and FEED_STEP_SECONDS == NODE_STEP,
          "the horizon the models learn is the horizon they are judged over",
          f"{TRAINING_HORIZON_STEPS} steps x {NODE_STEP}s "
          f"= {DEFAULT_HORIZON_SECONDS}s")

    sd = training.get("return_sd_bps")
    check(sd is not None and MIN_REALISTIC_SD_BPS <= sd <= MAX_REALISTIC_SD_BPS,
          "the training set has a real market's return scale",
          f"training return sd {sd}bps against the live tape's {sd_bps:.2f}bps")

    # ── 6. an agent observes what it is settled against ─────────────────────
    print(f"\n{DIM}the agent{RESET}")

    from agents.runtime.runner import run_agent

    with psycopg.connect(DSN) as conn:
        candidate = conn.execute(
            """select a.id from agents a
                 join model_versions m on m.agent_id = a.id
                where a.status <> 'RETIRED'
                order by a.id limit 1"""
        ).fetchone()[0]

    result = run_agent(agent_id=candidate, asset=ASSET, seed=11,
                       use_langgraph_checkpointer=False)
    state = result.state

    check(state.data_source == "LIVE",
          "the agent observed real prices",
          f"{state.observation_note}")

    check(state.price_provider in venues,
          "the agent read the same venue settlement will measure against",
          f"agent saw {state.price_provider}; feed holds {', '.join(venues)}")

    check(len(state.prices) >= 33 and all(p > 0 for p in state.prices),
          "the observed window is long enough to compute a feature over",
          f"{len(state.prices)} observations")

    # The prediction must be plausible *for this market*. A model trained on the
    # synthetic tape produces a number that is not, and nothing else in the
    # system can tell.
    if state.decision is not None:
        predicted_bps = abs(state.decision.expected_return) * 10_000
        horizon_sigma_bps = sd_bps * (DEFAULT_HORIZON_SECONDS / NODE_STEP) ** 0.5
        check(predicted_bps <= 6 * horizon_sigma_bps,
              "the prediction is plausible for this market's volatility",
              f"predicted {predicted_bps:.2f}bps against a "
              f"{horizon_sigma_bps:.2f}bps horizon sigma")
    else:
        check(True,
              "the prediction is plausible for this market's volatility",
              "the agent abstained; nothing was claimed")

    # ── 7. the evidence cannot be rewritten ─────────────────────────────────
    print(f"\n{DIM}the record{RESET}")

    with psycopg.connect(DSN) as conn:
        target = conn.execute(
            """select id from market_events
                where asset = %s and source = 'LIVE' order by occurred_at desc
                limit 1""",
            (ASSET,),
        ).fetchone()[0]

        conn.execute("savepoint probe")
        try:
            conn.execute(
                "update market_events set payload = %s where id = %s",
                (json.dumps({"price": 1.0}), target),
            )
            mutable = True
        except psycopg.errors.IntegrityConstraintViolation:
            mutable = False
        conn.rollback()

        conn.execute("savepoint probe2")
        try:
            conn.execute("delete from market_events where id = %s", (target,))
            deletable = True
        except psycopg.errors.IntegrityConstraintViolation:
            deletable = False
        conn.rollback()

    check(not mutable,
          "a recorded market observation cannot be restated",
          "the evidence every IRIS Score rests on is frozen, like the "
          "prediction it judges")
    check(not deletable,
          "a record of a real market cannot be deleted",
          "an agent's score already rests on it")

    with psycopg.connect(DSN) as conn:
        conn.execute("savepoint probe3")
        try:
            conn.execute(
                """insert into market_events (asset, kind, payload, source,
                                              occurred_at)
                   values ('G13NAN', 'PRICE', '{"price": "NaN"}', 'SIMULATION',
                           now())"""
            )
            nan_landed = True
        except psycopg.errors.IntegrityConstraintViolation:
            nan_landed = False
        conn.rollback()
    check(not nan_landed,
          "a price that is not a number never lands",
          "Postgres defines NaN = NaN as true, so this needs an explicit test")

    with psycopg.connect(DSN) as conn:
        conn.execute("savepoint probe4")
        try:
            conn.execute(
                """insert into market_events (asset, kind, payload, source,
                                              provider, occurred_at)
                   values ('G13FAKE', 'PRICE', '{"price": 1}', 'LIVE', NULL,
                           now())"""
            )
            unattributed = True
        except psycopg.errors.CheckViolation:
            unattributed = False
        conn.rollback()
    check(not unattributed,
          "claiming a price is real requires naming who said so",
          "synthetic data cannot be relabelled LIVE without asserting a venue")

    # ── 8. the API and the page say which of this is true ───────────────────
    print(f"\n{DIM}what the product says (section 0c){RESET}")

    health = get(f"{API}/api/market/health?asset={ASSET}")
    check(health["healthy"] is True,
          "the API reports the feed as healthy, with its reasons",
          f"lag {health['lag_seconds']}s, "
          f"coverage {health['coverage']['coverage']:.0%}")

    check(health["poller"]["running"] and health["poller"]["last_error"] is None,
          "the live poller is running inside the API",
          f"{health['poller']['polls']} polls, "
          f"{health['poller']['observations_written']} observations written")

    prices = get(f"{API}/api/market/prices?asset={ASSET}&limit=32")
    check(prices["provenance"]["live"] is True
          and prices["provenance"]["sources"] == ["LIVE"],
          "the price endpoint reports live provenance",
          prices["provenance"]["note"][:72])

    summary = get(f"{API}/api/protocol/summary")
    check("provenance" in summary,
          "the protocol summary still carries provenance on every response")

    venue_spread = get(f"{API}/api/market/venues?asset={ASSET}")
    check(venue_spread["spread_bps"] is not None
          and venue_spread["spread_bps"] < 100,
          "independent venues agree on the price, and the gap is measured",
          f"{len(venue_spread['quotes'])} venues, "
          f"spread {venue_spread['spread_bps']}bps")

    # The label has to be in the server-rendered HTML: a §0c notice that needs
    # JavaScript is absent exactly where a reader forms their first impression.
    #
    # Warmed first, and deliberately so. On a container that has just started,
    # the first request for a route competes with Turbopack compiling it, the
    # component's own fetch for provenance times out, and the page correctly
    # renders "unconfirmed" — which failed this gate on a stack that was
    # working. The property under test is "the server renders the label", not
    # "Next compiles within one request", and a gate that answers differently
    # depending on which of those it caught is a gate people learn to re-run.
    ROUTES = ("/arena", "/observatory", "/ledger")
    for route in ROUTES:
        try:
            text(f"{WEB}{route}")
        except Exception:  # noqa: BLE001 - the real request below reports it
            pass

    # Asserted as "the label is accurate", not "the label says live".
    #
    # The notice reports the weakest of three things: the feed, the training
    # set, and the provenance of the rows on the page. With a live feed and
    # real models but a settled record that still contains simulated outcomes,
    # the truthful answer is "mixed" — and demanding the word "live" here would
    # be a gate requiring the product to overstate, which is the failure §0c
    # exists to prevent, written into the check meant to prevent it.
    #
    # What a live feed does rule out is "simulated" and "unconfirmed".
    REAL_FEED_KINDS = {"live", "mixed"}
    for route in ROUTES:
        try:
            body = text(f"{WEB}{route}")
        except Exception as exc:  # noqa: BLE001
            check(False, f"{route} renders a provenance label server-side", str(exc))
            continue
        kind = _provenance_attr(body)
        check(kind in REAL_FEED_KINDS,
              f"{route} reports the real feed server-side",
              f"data-provenance={kind!r}, in the HTML before hydration and "
              f"without JavaScript")

    # The inverse failure: the page must not claim live when it cannot confirm
    # it. Asserted on the code rather than by breaking the stack.
    # Either the repo root (run from the host) or the read-only mount the api
    # container gets for exactly this.
    relative = "apps/web/components/iris/provenance-notice.tsx"
    candidates = [
        Path(__file__).resolve().parents[1] / relative,
        Path("/repo") / relative,
    ]
    notice = next((c for c in candidates if c.exists()), None)
    source = notice.read_text(encoding="utf-8") if notice else ""
    check('kind: "unknown"' in source and "Provenance unconfirmed" in source,
          "an unreachable API renders 'unconfirmed', never 'live'",
          "the safe direction is the one that admits it does not know")
    check("Live prices, synthetic models" in source,
          "live prices behind synthetic models are called out separately",
          "the combination that looks best from the outside and is worst")

    print()
    passed = sum(1 for ok, _, _ in results if ok)
    total = len(results)
    if passed == total:
        print(f"{GREEN}Market data gate PASSED{RESET} — {passed}/{total} checks.\n")
        return 0
    print(f"{RED}Market data gate FAILED{RESET} — {passed}/{total}.")
    for ok, label, _ in results:
        if not ok:
            print(f"  - {label}")
    print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
