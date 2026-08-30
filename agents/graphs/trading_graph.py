"""
The trading graph — IRIS_BUILD_PROMPT v2.0 section 10.

Assembles the eleven nodes into a LangGraph `StateGraph` with a single branch:
VALIDATION either approves (commit, execute, track) or rejects (abstain).

    MARKET_OBSERVATION
        -> FEATURE_EXTRACTION
        -> REGIME_ANALYSIS
        -> HISTORICAL_RETRIEVAL
        -> MODEL_INFERENCE
        -> RISK_ANALYSIS
        -> DECISION
        -> VALIDATION
             |- approved -> PREDICTION_COMMIT -> EXECUTION -> OUTCOME_TRACKING
             `- rejected -> ABSTAIN
"""

from __future__ import annotations

from typing import Callable

from langgraph.graph import END, StateGraph

from agents.graphs import nodes
from agents.state import AgentState, Node

# Node name -> implementation. Order here is the order in the spec, which is
# also the execution order for the linear section of the graph.
NODE_IMPLS: dict[str, Callable] = {
    Node.MARKET_OBSERVATION.value: nodes.market_observation,
    Node.FEATURE_EXTRACTION.value: nodes.feature_extraction,
    Node.REGIME_ANALYSIS.value: nodes.regime_analysis,
    Node.HISTORICAL_RETRIEVAL.value: nodes.historical_retrieval,
    Node.MODEL_INFERENCE.value: nodes.model_inference,
    Node.RISK_ANALYSIS.value: nodes.risk_analysis,
    Node.DECISION.value: nodes.decision,
    Node.VALIDATION.value: nodes.validation,
    Node.PREDICTION_COMMIT.value: nodes.prediction_commit,
    Node.EXECUTION.value: nodes.execution,
    Node.ABSTAIN.value: nodes.abstain,
    Node.OUTCOME_TRACKING.value: nodes.outcome_tracking,
}

# The straight run from observation to validation.
LINEAR_PATH = [
    Node.MARKET_OBSERVATION,
    Node.FEATURE_EXTRACTION,
    Node.REGIME_ANALYSIS,
    Node.HISTORICAL_RETRIEVAL,
    Node.MODEL_INFERENCE,
    Node.RISK_ANALYSIS,
    Node.DECISION,
    Node.VALIDATION,
]


def build_graph(*, on_node: Callable[[str, AgentState], None] | None = None):
    """
    Build the compiled-ready StateGraph.

    `on_node` is invoked after each node with the node name and the state as it
    stands. The runtime uses it to write a `graph_checkpoints` row per node, so
    the AI Observatory (section 15) renders real execution rather than a mock.
    Passing None keeps the graph usable in a plain unit test with no database.
    """
    graph = StateGraph(AgentState)

    for name, fn in NODE_IMPLS.items():
        graph.add_node(name, _wrap(name, fn, on_node))

    graph.set_entry_point(Node.MARKET_OBSERVATION.value)

    for current, following in zip(LINEAR_PATH, LINEAR_PATH[1:]):
        graph.add_edge(current.value, following.value)

    graph.add_conditional_edges(
        Node.VALIDATION.value,
        nodes.route_after_validation,
        {
            "commit": Node.PREDICTION_COMMIT.value,
            "abstain": Node.ABSTAIN.value,
        },
    )

    graph.add_edge(Node.PREDICTION_COMMIT.value, Node.EXECUTION.value)
    graph.add_edge(Node.EXECUTION.value, Node.OUTCOME_TRACKING.value)
    graph.add_edge(Node.OUTCOME_TRACKING.value, END)
    graph.add_edge(Node.ABSTAIN.value, END)

    return graph


def _wrap(name: str, fn: Callable, on_node: Callable[[str, AgentState], None] | None):
    """
    Adapt a node function so the runtime can observe it.

    The observer runs on the *merged* state, so a checkpoint row records what
    the graph looked like after the node ran, not the fragment the node
    returned. An observer that raises must not take the run down with it —
    losing telemetry is not a reason to lose the run — so failures there are
    recorded on the state and swallowed.
    """

    def run(state: AgentState) -> dict:
        update = fn(state)
        if on_node is not None:
            try:
                on_node(name, _merged_view(state, update))
            except Exception as exc:  # pragma: no cover - telemetry must not break runs
                update.setdefault("errors", list(state.errors))
                update["errors"] = [*update["errors"], f"checkpoint({name}): {exc}"]
        return update

    return run


def _merged_view(state: AgentState, update: dict) -> AgentState:
    """
    The state as it will stand once LangGraph merges this node's update.

    `model_copy` assigns rather than reduces, so a reducer-annotated field
    would be replaced instead of merged. `node_latency_ms` is the only such
    field, and the observer needs it — it is what section 19 records as the
    node's latency — so it is merged by hand here rather than dropped.
    """
    plain = {k: v for k, v in update.items() if k != "node_latency_ms"}
    merged = state.model_copy(update=plain)
    merged.node_latency_ms = {
        **state.node_latency_ms,
        **update.get("node_latency_ms", {}),
    }
    return merged
