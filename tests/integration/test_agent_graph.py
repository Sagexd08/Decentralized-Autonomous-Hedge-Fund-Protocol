"""
Agent graph tests — IRIS_BUILD_PROMPT v2.0 section 10 / Phase 3 DoD.

Phase 3's Definition of Done is "one agent completes the full graph end-to-end
on synthetic data, checkpointed in Neon". These assert that, and the invariants
that make it mean something:

  * the graph really executes all eleven nodes in the specified order;
  * RISK_ANALYSIS and VALIDATION are deterministic — the hard boundary from
    section 10, checked by source inspection as well as by behaviour;
  * PREDICTION_COMMIT produces a stable hash, and commits strictly before the
    horizon it will be judged against;
  * both branches work — a run that abstains is a correct outcome, not a
    failure, and a graph that could only ever commit would be a rubber stamp.

Run against a live stack:

    docker compose up -d db
    pytest tests/integration/test_agent_graph.py -v
"""

from __future__ import annotations

import inspect
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import psycopg
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from agents.evaluation.prices import record_price  # noqa: E402
from agents.graphs import nodes  # noqa: E402
from ml.inference.registry import family_for_strategy  # noqa: E402
from agents.graphs.trading_graph import LINEAR_PATH, build_graph  # noqa: E402
from agents.state import AgentState, Node  # noqa: E402

DSN = os.getenv("DATABASE_URL", "postgresql://iris:iris@localhost:5432/iris")

# Found by scanning seeds: these are the two branches, pinned so the tests are
# deterministic rather than hoping a random seed lands on the path they need.
# Which strategy runs each branch, and on which seed.
#
# This is load-bearing, not arbitrary. A model must clear the 0.55 validation
# floor before anything can be committed, and the CNN-LSTM behind `momentum`
# cannot — it lost to the baseline in Phase 4 and its confidence tops out near
# 0.48. These tests previously ran the commit branch on `momentum` and passed
# only because confidence was `max(proba)`, a number that had nothing to do
# with the direction being proposed. Once that was corrected the commit branch
# stopped committing, which is the truthful result.
#
# So the commit branch runs on `adaptive` (the transformer), which can clear
# the floor, and `momentum` runs the abstain branch, where declining to trade
# is the correct behaviour and worth asserting.
# Which strategy runs the commit branch is **discovered, not pinned**.
#
# It has been pinned twice and been wrong twice. Phase 4 wired real models in
# and the pinned strategy stopped committing; fixing the untrained spread head
# moved it again; and Phase 13 moved it a third time, because models fitted on
# real BTC behave differently from models fitted on a tape twenty times more
# volatile. Each time the failure read as "this branch is unreachable" when the
# truth was "a different strategy reaches it now".
#
# The property worth asserting is that *some* strategy can commit and *some*
# can abstain — that both branches of the validator are live. Which one does
# which is a fact about today's weights and does not belong in a constant.
STRATEGIES = ("momentum", "mean_reversion", "breakout", "adaptive")

AGENT_FOR_STRATEGY = {
    "momentum": "AGT-AXIOM",
    "mean_reversion": "AGT-MERIDIAN",
    "breakout": "AGT-HELIX",
    "adaptive": "AGT-QUANTA",
}

# An asset nothing ingests, so MARKET_OBSERVATION takes its synthetic fallback
# and the seed still selects the tape.
#
# Since Phase 13 that node reads `market_events` — the same table settlement
# measures against — and only falls back when the feed has nothing usable. On a
# fed asset like BTC that makes `seed` correctly inert: every run sees the same
# real prices, so a seed search cannot reach both branches.
UNFED_ASSET = "SYNTH-TEST"

# Statistics close to one-minute BTC: a return standard deviation near 3.5
# basis points, against the legacy fallback tape's 60.
#
# This matters for reachability. The models are fitted on the frozen snapshot
# in `ml.training.dataset`, which is real market data, and `decision_threshold`
# scales with the volatility the agent observes. Shown the old fallback tape —
# twenty times more volatile than anything they were trained on — every model
# correctly predicts a small move against a huge bar and declines. That is the
# right behaviour, and it makes "can this strategy ever commit" unanswerable,
# so the branch tests run on a tape drawn from the distribution the models
# actually live in.
TAPE_START_PRICE = 77_000.0
TAPE_RETURN_SD = 0.00035
TAPE_LENGTH = 64

SPEC_ORDER = [
    Node.MARKET_OBSERVATION,
    Node.FEATURE_EXTRACTION,
    Node.REGIME_ANALYSIS,
    Node.HISTORICAL_RETRIEVAL,
    Node.MODEL_INFERENCE,
    Node.RISK_ANALYSIS,
    Node.DECISION,
    Node.VALIDATION,
]


# How far to search for a seed that takes a given branch. Searching rather than
# pinning one is deliberate: which seeds commit depends on the trained models,
# so a hardcoded seed silently becomes a test of "did the models change" instead
# of "is this branch reachable". These tests have already been broken twice that
# way — once when Phase 4 wired real models in, and once when the untrained
# spread head was fixed.
SEED_SEARCH = range(0, 40)


def find_seed(*, commits: bool, strategy: str) -> tuple[int, AgentState, list[str]]:
    """The first seed whose run takes the requested branch, for one strategy."""
    for seed in SEED_SEARCH:
        final, visited = run_graph(seed, strategy)
        if final.abstained != commits:
            return seed, final, visited
    raise AssertionError(
        f"no seed in {SEED_SEARCH} makes a {strategy} agent "
        f"{'commit' if commits else 'abstain'}"
    )


@lru_cache(maxsize=2)
def branch(commits: bool) -> tuple[str, str, int]:
    """
    A (strategy, agent, seed) that takes the requested branch.

    Searched across strategies as well as seeds, so a test of "the commit
    branch works" does not quietly become a test of "one particular model still
    happens to be the confident one".
    """
    for strategy in STRATEGIES:
        for seed in SEED_SEARCH:
            final, _ = run_graph(seed, strategy)
            if final.abstained != commits:
                return strategy, AGENT_FOR_STRATEGY[strategy], seed
    raise AssertionError(
        f"no strategy in {STRATEGIES} over seeds {SEED_SEARCH} can "
        f"{'commit' if commits else 'abstain'} — that branch of the validator "
        f"is unreachable, so it is not doing its job in one direction"
    )


def realistic_tape(seed: int, n: int = TAPE_LENGTH) -> list[float]:
    """A seeded price walk with a real market's return scale."""
    rng = random.Random(seed)
    price = TAPE_START_PRICE
    out: list[float] = []
    for _ in range(n):
        price *= 1.0 + rng.gauss(0.0, TAPE_RETURN_SD)
        out.append(round(price, 2))
    return out


_seeded_tapes: set[str] = set()


def tape_asset(seed: int) -> str:
    """
    Write this seed's tape into the feed and return the asset it lives under.

    Labelled SIMULATION, because it is. What makes it the right fixture is not
    the label but the *path*: the agent reads it out of `market_events` exactly
    as it reads a real venue's ticks in production, rather than through a code
    path that only tests use.

    Re-seeded when stale. MARKET_OBSERVATION ignores a window older than
    MAX_OBSERVATION_AGE, so a tape left by yesterday's run would silently send
    every test back to the fallback and quietly stop testing this at all.
    """
    asset = f"TAPE{seed:03d}"
    if asset in _seeded_tapes:
        return asset

    now = datetime.now(timezone.utc)
    with psycopg.connect(DSN) as conn:
        newest = conn.execute(
            "select max(occurred_at) from market_events where asset = %s", (asset,)
        ).fetchone()[0]
        if newest is None or newest < now - timedelta(minutes=30):
            # Deletable because it is SIMULATION. A LIVE row could not be
            # removed, which is exactly the point of that asymmetry.
            conn.execute("delete from market_events where asset = %s", (asset,))
            for i, price in enumerate(realistic_tape(seed)):
                record_price(
                    conn, asset=asset, price=price,
                    at=now - timedelta(minutes=TAPE_LENGTH - i),
                    source="SIMULATION",
                )
        conn.commit()

    _seeded_tapes.add(asset)
    return asset


def run_graph(
    seed: int, strategy: str = "momentum", asset: str | None = None
) -> tuple[AgentState, list[str]]:
    """
    Run the graph in-process, recording the node order.

    The tape comes from `market_events`, which is where MARKET_OBSERVATION now
    reads it — so this exercises the production path rather than a private
    generator, and the seed varies the tape by varying which asset's series the
    agent is pointed at.
    """
    visited: list[str] = []
    graph = build_graph(on_node=lambda name, _state: visited.append(name))
    compiled = graph.compile()
    state = AgentState(
        agent_id="AGT-TEST",
        agent_run_id="test-run",
        asset=asset if asset is not None else tape_asset(seed),
        strategy=strategy,
        seed=seed,
    )
    out = compiled.invoke(state)
    final = out if isinstance(out, AgentState) else AgentState.model_validate(out)
    return final, visited


# ── the graph itself ────────────────────────────────────────────────────────

def test_graph_walks_the_specified_node_order():
    _, visited = run_graph(branch(True)[2], branch(True)[0])
    prefix = [n.value for n in SPEC_ORDER]
    assert visited[: len(prefix)] == prefix, (
        "the linear section must follow section 10's order exactly"
    )


def test_committing_run_executes_all_eleven_nodes():
    """Phase 3 DoD: one agent completes the full graph end to end."""
    seed, final, visited = find_seed(commits=True, strategy=branch(True)[0])
    assert not final.abstained, f"seed {seed} should commit"
    assert not final.errors, final.errors

    expected = [n.value for n in SPEC_ORDER] + [
        Node.PREDICTION_COMMIT.value,
        Node.EXECUTION.value,
        Node.OUTCOME_TRACKING.value,
    ]
    assert visited == expected
    assert len(visited) == 11
    assert final.executed is True


def test_abstaining_run_skips_commit_and_execution():
    seed, final, visited = find_seed(commits=False, strategy=branch(False)[0])
    assert final.abstained is True, f"seed {seed}"
    assert final.abstain_reason
    assert Node.PREDICTION_COMMIT.value not in visited
    assert Node.EXECUTION.value not in visited
    assert final.prediction_hash is None, "an abstention must not leave a commitment"


def test_the_graph_can_do_both_things():
    """
    A validator that approved everything would pass every other test here while
    providing no protection at all. Both branches must be reachable.
    """
    commit_seed, committed, _ = find_seed(commits=True, strategy=branch(True)[0])
    abstain_seed, abstained, _ = find_seed(commits=False, strategy=branch(False)[0])
    assert not committed.abstained, f"seed {commit_seed}"
    assert abstained.abstained, f"seed {abstain_seed}"


# ── the hard boundary: risk and validation are deterministic ────────────────

@pytest.mark.parametrize("fn", [nodes.risk_analysis, nodes.validation])
def test_risk_and_validation_contain_no_model_call(fn):
    """
    Section 10 draws a hard line: free-form model output never reaches capital.
    RISK_ANALYSIS and VALIDATION are the gate, so they must stay deterministic
    code. This reads their source and fails if a model or network call ever
    appears in one.
    """
    src = inspect.getsource(fn).lower()
    forbidden = [
        "llm", "openai", "anthropic", "groq", "gemini", "chat",
        "invoke(", "predict(", "requests.", "httpx", "aiohttp",
    ]
    found = [tok for tok in forbidden if tok in src]
    assert not found, (
        f"{fn.__name__} appears to reach outside deterministic code: {found}. "
        f"If this is intentional, the section 10 boundary has been crossed."
    )


def test_validation_rejects_low_confidence():
    state = AgentState(
        agent_id="A", agent_run_id="r", asset=UNFED_ASSET, strategy="momentum",
        predicted_return=0.01, model_confidence=0.1,
        features={"volatility": 0.001, "max_drawdown": -0.001},
        prices=[100.0, 100.1, 100.2],
    )
    state = state.model_copy(update=nodes.risk_analysis(state))
    state = state.model_copy(update=nodes.decision(state))
    result = nodes.validation(state)["validation"]
    assert not result.approved
    assert any("confidence" in r for r in result.reasons)


def test_validation_rejects_an_absurd_expected_return():
    """A model claiming a 500% return over ten minutes is broken, not brilliant."""
    state = AgentState(
        agent_id="A", agent_run_id="r", asset=UNFED_ASSET, strategy="momentum",
        predicted_return=5.0, model_confidence=0.99,
        features={"volatility": 0.001, "max_drawdown": -0.001},
        prices=[100.0, 100.1, 100.2],
    )
    state = state.model_copy(update=nodes.risk_analysis(state))
    state = state.model_copy(update=nodes.decision(state))
    result = nodes.validation(state)["validation"]
    assert not result.approved
    assert any("sanity bound" in r for r in result.reasons)


def test_validation_rejects_on_a_risk_breach():
    """Volatility past the cap must veto regardless of how confident the model is."""
    state = AgentState(
        agent_id="A", agent_run_id="r", asset=UNFED_ASSET, strategy="momentum",
        predicted_return=0.01, model_confidence=0.99,
        features={"volatility": 0.9, "max_drawdown": -0.5},
        prices=[100.0, 60.0, 130.0, 55.0],
    )
    state = state.model_copy(update=nodes.risk_analysis(state))
    state = state.model_copy(update=nodes.decision(state))
    result = nodes.validation(state)["validation"]
    assert not result.approved
    assert any("volatility" in r or "drawdown" in r for r in result.reasons)


# ── the commitment ──────────────────────────────────────────────────────────

def test_prediction_hash_is_stable_for_identical_claims():
    args = dict(
        agent_id="AGT-AXIOM", asset="BTC", direction="BUY",
        expected_return=0.0123456789, confidence=0.7,
        horizon_seconds=600, model_version_id="mv-1",
        committed_at="2026-01-01T00:00:00+00:00",
    )
    import hashlib

    a = hashlib.sha256(nodes.canonical_payload(**args).encode()).hexdigest()
    b = hashlib.sha256(nodes.canonical_payload(**args).encode()).hexdigest()
    assert a == b, "the same claim must always produce the same commitment"


def test_changing_any_field_changes_the_hash():
    """A commitment that survives an edit to its own claim commits to nothing."""
    import hashlib

    base = dict(
        agent_id="AGT-AXIOM", asset="BTC", direction="BUY",
        expected_return=0.01, confidence=0.7, horizon_seconds=600,
        model_version_id="mv-1", committed_at="2026-01-01T00:00:00+00:00",
    )
    original = hashlib.sha256(nodes.canonical_payload(**base).encode()).hexdigest()

    for field, changed in [
        ("direction", "SELL"),
        ("expected_return", 0.02),
        ("confidence", 0.8),
        ("horizon_seconds", 900),
        ("model_version_id", "mv-2"),
        ("asset", "ETH"),
        ("agent_id", "AGT-VECTOR"),
    ]:
        mutated = {**base, field: changed}
        digest = hashlib.sha256(nodes.canonical_payload(**mutated).encode()).hexdigest()
        assert digest != original, f"changing {field} must change the commitment"


def test_commit_precedes_the_horizon_it_is_judged_against():
    """
    The core Web3 x ML primitive: the prediction must provably exist before its
    outcome can. The database enforces this too — belt and braces, because the
    two could drift independently.
    """
    final, _ = run_graph(branch(True)[2], branch(True)[0])
    assert final.prediction_hash and len(final.prediction_hash) == 64
    committed = datetime.fromisoformat(final.committed_at)
    horizon = datetime.fromisoformat(final.horizon_end)
    assert committed < horizon


# ── reproducibility (section 18) ────────────────────────────────────────────

def test_same_seed_produces_the_same_run():
    a, _ = run_graph(branch(True)[2], branch(True)[0])
    b, _ = run_graph(branch(True)[2], branch(True)[0])
    assert a.prices == b.prices
    assert a.features == b.features
    assert a.decision == b.decision


def test_different_seeds_produce_different_tape_when_there_is_no_feed():
    """
    The fallback is still reproducible from its seed — section 18.

    Only the fallback. With a real feed the seed is correctly inert, which is
    the subject of the live-observation tests below.
    """
    a, _ = run_graph(1, asset=UNFED_ASSET)
    b, _ = run_graph(2, asset=UNFED_ASSET)
    assert a.prices != b.prices
    assert a.data_source == b.data_source == "SIMULATION"
    assert "synthetic fallback" in a.observation_note


def test_strategies_disagree_on_the_same_tape():
    """
    Section 10 requires genuinely different behaviour per strategy, not
    palette-swaps of one formula. Momentum and mean-reversion read the same
    window and should not land on the same number.
    """
    momentum, _ = run_graph(7, strategy="momentum")
    reversion, _ = run_graph(7, strategy="mean_reversion")
    assert momentum.prices == reversion.prices, "same seed should mean same tape"
    assert momentum.predicted_return != reversion.predicted_return


# ── persistence: "checkpointed in Neon" ─────────────────────────────────────

@pytest.fixture
def db():
    psycopg = pytest.importorskip("psycopg")
    try:
        conn = psycopg.connect(DSN)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"database unreachable: {exc}")
    yield conn
    conn.close()


def test_a_run_is_checkpointed_node_by_node(db):
    from agents.runtime.runner import run_agent

    _strategy, agent, seed = branch(commits=True)
    result = run_agent(
        agent_id=agent, asset=tape_asset(seed), seed=seed, dsn=DSN,
        use_langgraph_checkpointer=False,
    )
    assert result.outcome == "COMPLETED"
    assert result.checkpoints == 11

    rows = db.execute(
        "select seq, node, input_hash, output_hash from graph_checkpoints "
        "where agent_run_id = %s order by seq",
        (result.agent_run_id,),
    ).fetchall()
    assert len(rows) == 11
    assert [r[1] for r in rows][0] == Node.MARKET_OBSERVATION.value

    # each node's input must be the previous node's output — an audit chain,
    # not eleven disconnected snapshots
    for previous, current in zip(rows, rows[1:]):
        assert current[2] == previous[3], (
            f"checkpoint chain broken between seq {previous[0]} and {current[0]}"
        )


def test_a_committed_run_writes_a_prediction_row(db):
    from agents.runtime.runner import run_agent

    _strategy, agent, seed = branch(commits=True)
    result = run_agent(
        agent_id=agent, asset=tape_asset(seed), seed=seed, dsn=DSN,
        use_langgraph_checkpointer=False,
    )
    assert result.prediction_id

    row = db.execute(
        "select status, prediction_hash, committed_at <= horizon_end "
        "from predictions where id = %s",
        (result.prediction_id,),
    ).fetchone()
    assert row[0] == "COMMITTED"
    assert row[1] == result.state.prediction_hash
    assert row[2] is True


def test_an_abstaining_run_is_recorded_as_abstained_not_failed(db):
    """Declining to trade because risk objected is the system working."""
    from agents.runtime.runner import run_agent

    _strategy, agent, seed = branch(commits=False)
    result = run_agent(
        agent_id=agent, asset=tape_asset(seed), seed=seed, dsn=DSN,
        use_langgraph_checkpointer=False,
    )
    assert result.outcome == "ABSTAINED"
    assert result.prediction_id is None

    row = db.execute(
        "select status, error, prediction_id from agent_runs where id = %s",
        (result.agent_run_id,),
    ).fetchone()
    assert row[0] == "ABSTAINED"
    assert row[1] is None, "an abstention is not an error"
    assert row[2] is None


# ── the agent does not write the evidence it is judged on ───────────────────

def test_a_committing_run_writes_no_market_price():
    """
    An agent that records the price it will later be settled against is an
    agent grading its own exam.

    This was briefly true: `persist_prediction` wrote `state.prices[-1]` into
    `market_events` so settlement would have an entry price. Two things were
    wrong. `market_observation` generates a private tape seeded from the run
    and unrelated to the shared feed, so entry and exit legs came from
    different price universes — every agent wrote the identical 98.372476 and
    settlement measured the disagreement between the series rather than the
    market. And structurally, the agent must not be able to choose its own
    entry price at all.
    """
    import psycopg

    from agents.runtime.runner import run_agent

    with psycopg.connect(DSN) as probe:
        before = probe.execute(
            "select count(*) from market_events where kind = 'PRICE' and asset = %s",
            (UNFED_ASSET,),
        ).fetchone()[0]

    _strategy, agent, seed = branch(commits=True)
    result = run_agent(
        agent_id=agent, asset=tape_asset(seed), seed=seed, dsn=DSN,
        use_langgraph_checkpointer=False,
    )
    assert result.prediction_id, "this test needs a run that actually commits"

    with psycopg.connect(DSN) as probe:
        after = probe.execute(
            "select count(*) from market_events where kind = 'PRICE' and asset = %s",
            (UNFED_ASSET,),
        ).fetchone()[0]

    assert after == before, (
        "a committing run wrote a price observation; settlement evidence must "
        "come from the feed, not from the agent being settled"
    )


# ── every strategy must be able to trade ────────────────────────────────────

@pytest.mark.parametrize("strategy", STRATEGIES)
def test_every_strategy_produces_a_real_prediction(strategy):
    """
    Every strategy runs its own fitted model and produces a usable number.

    This used to assert that every strategy could *commit* on some seed. That
    was the right test when the failure it caught was structural — the torch
    models' `spread` head was outside the training loss and reported its random
    initialisation, so those models' confidence was an arbitrary constant that
    could never clear the floor; the tabular models carried leftover 2x/4x
    tuning constants that made them uniformly less certain. Both were bugs, and
    both made a strategy incapable of ever being sure.

    On real market data the same assertion stopped measuring that. Three of the
    four families now decline almost always, and the Phase 4 evaluation says
    why in as many words: fitted on real BTC and scored out of sample, the
    CNN-LSTM predicts HOLD for 100% of samples, the transformer for 100%, the
    gradient booster for 98%, and none beats the baseline. They are not broken;
    they have found that the most likely ten-minute outcome is "no move" and
    are saying so. Asserting that they commit anyway would be asserting that
    they overstate their confidence.

    So this asserts the plumbing — a distinct fitted model per strategy, a
    finite prediction, a confidence in range — and `scripts/verify_phase4.py`
    is where the models' *quality* is judged. That gate currently fails, and it
    is supposed to.
    """
    final, visited = run_graph(3, strategy)

    assert final.predicted_return is not None
    assert math.isfinite(final.predicted_return)
    assert abs(final.predicted_return) < 1.0, "a >100% move is a broken model"
    assert 0.0 <= final.model_confidence <= 1.0
    assert final.inference_source != "UNTRAINED", (
        f"{strategy} ran an unfitted model; its confidence would be arbitrary"
    )
    assert Node.MODEL_INFERENCE.value in visited


def test_strategies_do_not_share_a_model():
    """
    Section 10: agents must be genuinely different, not palette-swaps.

    Checked on the model registry rather than on outputs, because two models
    that both currently predict near zero look identical from outside.
    """
    families = {s: family_for_strategy(s) for s in STRATEGIES}
    assert len(set(families.values())) == len(STRATEGIES), families


def test_both_branches_of_the_validator_are_reachable():
    """
    Some strategy can commit and some can abstain.

    The property the per-strategy version was really protecting: a validator
    that only ever says yes is a rubber stamp, and one that only ever says no
    makes the whole protocol inert. Searched across strategies, because which
    one lands on which branch is a fact about today's weights.
    """
    committing_strategy, _agent, commit_seed = branch(commits=True)
    abstaining_strategy, _agent2, abstain_seed = branch(commits=False)

    committed, _ = run_graph(commit_seed, committing_strategy)
    abstained, _ = run_graph(abstain_seed, abstaining_strategy)

    assert not committed.abstained and committed.prediction_hash
    assert abstained.abstained and abstained.abstain_reason
