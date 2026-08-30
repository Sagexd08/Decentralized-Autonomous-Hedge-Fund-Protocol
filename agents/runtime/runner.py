"""
Agent runner — IRIS_BUILD_PROMPT v2.0 sections 10 and 19; Phase 3 DoD.

Executes one agent through the trading graph and leaves a durable, auditable
trace in Postgres:

  * an `agent_runs` row, opened before the graph starts and closed after;
  * a `graph_checkpoints` row per node;
  * a `predictions` row when the run commits.

Two different things are called "checkpointing" here and they are not the same:

  * **LangGraph's checkpointer** (`PostgresSaver`) persists graph state so a
    run can be *resumed* after a crash. Section 10 asks for it explicitly.
  * **`graph_checkpoints`** is our audit trail, written per node and read by
    the Observatory. It outlives the run and is never pruned by LangGraph.

Both land in Postgres. Only the second is queried by the product.

    python -m agents.runtime.runner --agent AGT-AXIOM --asset BTC --seed 42
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional

from agents.graphs.trading_graph import build_graph
from agents.runtime import persistence
from agents.state import AgentState


@dataclass
class RunResult:
    agent_run_id: str
    state: AgentState
    prediction_id: Optional[str]
    checkpoints: int
    latency_ms: int

    @property
    def outcome(self) -> str:
        if self.state.errors:
            return "FAILED"
        return "ABSTAINED" if self.state.abstained else "COMPLETED"


def run_agent(
    *,
    agent_id: str,
    asset: str = "BTC",
    seed: int = 0,
    strategy: Optional[str] = None,
    dsn: Optional[str] = None,
    use_langgraph_checkpointer: bool = True,
) -> RunResult:
    """
    Run one agent end to end.

    Everything is written inside a single transaction, so a run either lands
    completely or not at all — a half-recorded run would be worse than no
    record, because the Observatory would render a graph that never happened.
    """
    started = time.time()

    with persistence.connection(dsn) as conn:
        resolved_strategy = strategy or persistence.agent_strategy(conn, agent_id)
        model_version_id = persistence.active_model_version(conn, agent_id)
        agent_run_id = persistence.start_run(conn, agent_id=agent_id)

        initial = AgentState(
            agent_id=agent_id,
            agent_run_id=agent_run_id,
            asset=asset,
            strategy=resolved_strategy,
            model_version_id=model_version_id,
            seed=seed,
        )

        counter = {"seq": 0}
        previous_digest = {"hash": persistence.state_digest(initial)}

        def on_node(node: str, state: AgentState) -> None:
            persistence.record_node(
                conn,
                agent_run_id=agent_run_id,
                seq=counter["seq"],
                node=node,
                state=state,
                input_hash=previous_digest["hash"],
            )
            counter["seq"] += 1
            previous_digest["hash"] = persistence.state_digest(state)

        graph = build_graph(on_node=on_node)

        # The checkpointer must stay open for the whole invocation — it holds
        # its own connection, and letting the context manager close before
        # `invoke` returns leaves the graph talking to a dead socket.
        with checkpointer(dsn, use_langgraph_checkpointer) as saver:
            compiled = graph.compile(checkpointer=saver)
            config = {"configurable": {"thread_id": agent_run_id}}
            final_raw = compiled.invoke(initial, config=config)

        final = (
            final_raw
            if isinstance(final_raw, AgentState)
            else AgentState.model_validate(final_raw)
        )

        prediction_id = persistence.persist_prediction(conn, state=final)
        latency_ms = int((time.time() - started) * 1000)
        persistence.finish_run(
            conn, agent_run_id=agent_run_id, state=final, latency_ms=latency_ms
        )

    return RunResult(
        agent_run_id=agent_run_id,
        state=final,
        prediction_id=prediction_id,
        checkpoints=counter["seq"],
        latency_ms=latency_ms,
    )


@contextmanager
def checkpointer(dsn: Optional[str], use_postgres: bool) -> Iterator[object]:
    """
    Yield LangGraph's checkpointer, open for the caller's whole block.

    Section 10 says to start on MemorySaver and move to Postgres once Neon is
    wired. It is wired, so Postgres is the default — but a checkpointer that
    cannot connect must not take the run down with it: the audit trail in
    `graph_checkpoints` is written independently and is the one the product
    reads. So this degrades to MemorySaver and says so on stderr rather than
    failing.
    """
    if use_postgres:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            with ExitStack() as stack:
                saver = stack.enter_context(
                    PostgresSaver.from_conn_string(dsn or persistence.dsn())
                )
                saver.setup()
                yield saver
                return
        except Exception as exc:  # pragma: no cover - environment dependent
            print(
                f"[runner] PostgresSaver unavailable ({exc}); "
                f"falling back to MemorySaver. graph_checkpoints is unaffected.",
                file=sys.stderr,
            )

    from langgraph.checkpoint.memory import MemorySaver

    yield MemorySaver()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one IRIS agent through the graph.")
    parser.add_argument("--agent", default="AGT-AXIOM")
    parser.add_argument("--asset", default="BTC")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--strategy", default=None)
    parser.add_argument("--json", action="store_true", help="emit the result as JSON")
    args = parser.parse_args(argv)

    result = run_agent(
        agent_id=args.agent,
        asset=args.asset,
        seed=args.seed,
        strategy=args.strategy,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "agent_run_id": result.agent_run_id,
                    "outcome": result.outcome,
                    "checkpoints": result.checkpoints,
                    "prediction_id": result.prediction_id,
                    "prediction_hash": result.state.prediction_hash,
                    "latency_ms": result.latency_ms,
                },
                indent=2,
            )
        )
        return 0

    s = result.state
    print(f"run        {result.agent_run_id}")
    print(f"agent      {s.agent_id} ({s.strategy}) on {s.asset}")
    print(f"regime     {s.regime} (vol {s.risk.volatility_bps if s.risk else '—'}bps)")
    if s.decision:
        print(
            f"decision   {s.decision.direction} "
            f"{s.decision.expected_return:+.4%} @ conf {s.decision.confidence:.2f}"
        )
    print(f"outcome    {result.outcome}")
    if s.abstained:
        print(f"abstained  {s.abstain_reason}")
    if s.prediction_hash:
        print(f"commitment {s.prediction_hash}")
        print(f"           committed {s.committed_at}")
        print(f"           horizon   {s.horizon_end}")
    print(f"nodes      {result.checkpoints} checkpointed in {result.latency_ms}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
