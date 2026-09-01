#!/usr/bin/env python
"""
Why is each agent trading, or not?

"The agents aren't trading" has at least four different causes, and they need
different responses:

  * the **market** is quiet, so no model predicts a move worth taking — the
    system working, and the most common answer;
  * the **model** has no directional view, whatever the market is doing —
    a model-quality problem, which `scripts/verify_phase4.py` judges;
  * the **feed** is stale or thin, so the agent is reasoning over a window that
    does not describe now — an operational problem;
  * a **gate** is miscalibrated, rejecting proposals it should accept — which
    is what the flat 5bps threshold and the all-classes confidence floor both
    turned out to be.

Guessing between those from an empty Arena is how a calibration bug survives
for weeks. This prints the numbers behind every abstention: what the model
predicted, how sure it was of the side, what each gate required, and which one
actually refused.

    python scripts/why_abstained.py
    python scripts/why_abstained.py --asset ETH
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import psycopg  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - host path
    print("dependencies unavailable here; running inside the api container.",
          flush=True)
    raise SystemExit(
        subprocess.run(
            ["docker", "compose", "exec", "-T", "api",
             "python", "/repo/scripts/why_abstained.py", *sys.argv[1:]],
        ).returncode
    )

GREEN, RED, DIM, YELLOW, RESET = (
    "\033[32m", "\033[31m", "\033[2m", "\033[33m", "\033[0m"
)


def main(argv: list[str] | None = None) -> int:
    from agents.graphs.nodes import (
        MIN_DIRECTIONAL_CONFIDENCE,
        decision_threshold,
    )
    from agents.runtime.persistence import connection
    from agents.runtime.runner import run_agent

    parser = argparse.ArgumentParser(description="Why did each agent abstain?")
    parser.add_argument("--asset", default="BTC")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    with connection() as conn:
        agents = conn.execute(
            """select a.id, a.strategy from agents a
                 join model_versions m on m.agent_id = a.id
                where a.status <> 'RETIRED'
                order by a.id"""
        ).fetchall()

    if not agents:
        print("no registered agent has a model version")
        return 1

    print(f"\n{args.asset} — what each agent saw, and which gate answered\n")
    print(f"{'agent':<14}{'strategy':<16}{'outcome':<11}{'predicted':>11}"
          f"{'|dir|':>8}{'needs':>9}   refused by")
    print("-" * 96)

    committed = 0
    note = ""
    for i, (agent, strategy) in enumerate(agents):
        result = run_agent(agent_id=agent, asset=args.asset, seed=args.seed + i,
                           use_langgraph_checkpointer=False)
        state = result.state
        decision = state.decision
        threshold = decision_threshold(state) * 1e4
        predicted = (state.predicted_return or 0.0) * 1e4
        directional = state.model_directional_confidence
        note = state.observation_note

        if result.outcome == "COMPLETED":
            committed += 1
            gate, colour = "— traded", GREEN
        elif decision is None or decision.direction == "HOLD":
            gate = f"magnitude: {abs(predicted):.2f}bps < {threshold:.2f}bps"
            colour = DIM
        elif directional < MIN_DIRECTIONAL_CONFIDENCE:
            gate = (f"direction: {directional:.2f} < "
                    f"{MIN_DIRECTIONAL_CONFIDENCE}")
            colour = YELLOW
        elif state.risk is not None and state.risk.breaches:
            gate = f"risk: {state.risk.breaches[0][:34]}"
            colour = RED
        else:
            gate = (state.abstain_reason or "unknown")[:40]
            colour = RED

        print(f"{agent:<14}{strategy:<16}{result.outcome:<11}{predicted:>+10.2f}b"
              f"{directional:>8.2f}{threshold:>8.2f}b   {colour}{gate}{RESET}")

    print("-" * 96)
    print(f"{committed}/{len(agents)} committed")
    if note:
        print(f"{DIM}window: {note}{RESET}")
    print()
    print(f"{DIM}magnitude — DECISION would not propose a side at all; the "
          f"predicted move is inside the band scoring treats as flat.{RESET}")
    print(f"{DIM}direction — a side was proposed, but the model is not "
          f"sufficiently sure which one.{RESET}")
    print(f"{DIM}Neither is a fault. An agent that trades on every window is "
          f"not being validated.{RESET}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
