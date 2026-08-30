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
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from agents.graphs import nodes  # noqa: E402
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
STRATEGY_COMMITS = "adaptive"
STRATEGY_ABSTAINS = "momentum"

AGENT_COMMITS = "AGT-QUANTA"    # adaptive -> transformer
AGENT_ABSTAINS = "AGT-AXIOM"    # momentum -> cnn_lstm

SEED_COMMITS = 7
SEED_ABSTAINS = 0

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
    """The first seed whose run takes the requested branch."""
    for seed in SEED_SEARCH:
        final, visited = run_graph(seed, strategy)
        if final.abstained != commits:
            return seed, final, visited
    raise AssertionError(
        f"no seed in {SEED_SEARCH} makes a {strategy} agent "
        f"{'commit' if commits else 'abstain'} — that branch is unreachable, "
        f"which means the validator is not doing its job in one direction"
    )


def run_graph(seed: int, strategy: str = STRATEGY_COMMITS) -> tuple[AgentState, list[str]]:
    """Run the graph in-process with no database, recording the node order."""
    visited: list[str] = []
    graph = build_graph(on_node=lambda name, _state: visited.append(name))
    compiled = graph.compile()
    state = AgentState(
        agent_id="AGT-TEST",
        agent_run_id="test-run",
        asset="BTC",
        strategy=strategy,
        seed=seed,
    )
    out = compiled.invoke(state)
    final = out if isinstance(out, AgentState) else AgentState.model_validate(out)
    return final, visited


# ── the graph itself ────────────────────────────────────────────────────────

def test_graph_walks_the_specified_node_order():
    _, visited = run_graph(SEED_COMMITS, STRATEGY_COMMITS)
    prefix = [n.value for n in SPEC_ORDER]
    assert visited[: len(prefix)] == prefix, (
        "the linear section must follow section 10's order exactly"
    )


def test_committing_run_executes_all_eleven_nodes():
    """Phase 3 DoD: one agent completes the full graph end to end."""
    seed, final, visited = find_seed(commits=True, strategy=STRATEGY_COMMITS)
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
    seed, final, visited = find_seed(commits=False, strategy=STRATEGY_ABSTAINS)
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
    commit_seed, committed, _ = find_seed(commits=True, strategy=STRATEGY_COMMITS)
    abstain_seed, abstained, _ = find_seed(commits=False, strategy=STRATEGY_ABSTAINS)
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
        agent_id="A", agent_run_id="r", asset="BTC", strategy="momentum",
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
        agent_id="A", agent_run_id="r", asset="BTC", strategy="momentum",
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
        agent_id="A", agent_run_id="r", asset="BTC", strategy="momentum",
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
    final, _ = run_graph(SEED_COMMITS, STRATEGY_COMMITS)
    assert final.prediction_hash and len(final.prediction_hash) == 64
    committed = datetime.fromisoformat(final.committed_at)
    horizon = datetime.fromisoformat(final.horizon_end)
    assert committed < horizon


# ── reproducibility (section 18) ────────────────────────────────────────────

def test_same_seed_produces_the_same_run():
    a, _ = run_graph(SEED_COMMITS, STRATEGY_COMMITS)
    b, _ = run_graph(SEED_COMMITS, STRATEGY_COMMITS)
    assert a.prices == b.prices
    assert a.features == b.features
    assert a.decision == b.decision


def test_different_seeds_produce_different_tape():
    a, _ = run_graph(1)
    b, _ = run_graph(2)
    assert a.prices != b.prices


def test_strategies_disagree_on_the_same_tape():
    """
    Section 10 requires genuinely different behaviour per strategy, not
    palette-swaps of one formula. Momentum and mean-reversion read the same
    window and should not land on the same number.
    """
    momentum, _ = run_graph(SEED_COMMITS, strategy="momentum")
    reversion, _ = run_graph(SEED_COMMITS, strategy="mean_reversion")
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

    result = run_agent(
        agent_id=AGENT_COMMITS, asset="BTC", seed=SEED_COMMITS, dsn=DSN,
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

    result = run_agent(
        agent_id=AGENT_COMMITS, asset="BTC", seed=SEED_COMMITS, dsn=DSN,
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

    result = run_agent(
        agent_id=AGENT_ABSTAINS, asset="BTC", seed=SEED_ABSTAINS, dsn=DSN,
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
            ("BTC",),
        ).fetchone()[0]

    result = run_agent(
        agent_id=AGENT_COMMITS, asset="BTC", seed=SEED_COMMITS, dsn=DSN,
        use_langgraph_checkpointer=False,
    )
    assert result.prediction_id, "this test needs a run that actually commits"

    with psycopg.connect(DSN) as probe:
        after = probe.execute(
            "select count(*) from market_events where kind = 'PRICE' and asset = %s",
            ("BTC",),
        ).fetchone()[0]

    assert after == before, (
        "a committing run wrote a price observation; settlement evidence must "
        "come from the feed, not from the agent being settled"
    )


# ── every strategy must be able to trade ────────────────────────────────────

@pytest.mark.parametrize(
    "strategy", ["momentum", "mean_reversion", "breakout", "adaptive"]
)
def test_every_strategy_can_reach_a_commitment(strategy):
    """
    A strategy that structurally cannot clear the validation floor is dead
    weight: it occupies an allocation slot and returns nothing, forever.

    Both `momentum` and `mean_reversion` were in that state, for two different
    reasons that both looked like "the model is just weak":

      * The torch models' `spread` head was never in the training loss
        (`pred, _ = self.net(xb)`), so it reported its random initialisation.
        Confidence is `expected_return / spread`, so every confidence those
        models produced was an arbitrary constant — CNN-LSTM drew a large one
        and could never exceed 0.48.
      * The tabular models multiplied their error scale by a leftover 2x / 4x
        tuning constant from the old hardcoded-HOLD-logit formulation, which
        under the current one just made them look uniformly less certain.

    This asserts reachability, not a hit rate. An agent *should* abstain when
    it is genuinely unsure; it should not be incapable of ever being sure.
    """
    for seed in SEED_SEARCH:
        final, _ = run_graph(seed, strategy)
        if not final.abstained:
            return
    raise AssertionError(
        f"no seed in {SEED_SEARCH} lets a {strategy} agent commit — that "
        f"strategy cannot trade at all"
    )


@pytest.mark.parametrize(
    "strategy", ["momentum", "mean_reversion", "breakout", "adaptive"]
)
def test_every_strategy_can_also_abstain(strategy):
    """The other half. A strategy that always commits is not being validated."""
    for seed in SEED_SEARCH:
        final, _ = run_graph(seed, strategy)
        if final.abstained:
            return
    raise AssertionError(
        f"no seed in {SEED_SEARCH} makes a {strategy} agent abstain — the "
        f"validation floor is not binding for it"
    )
