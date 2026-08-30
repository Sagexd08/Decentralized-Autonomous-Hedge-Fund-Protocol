"""
Risk limits and slashing — IRIS_BUILD_PROMPT v2.0 section 8, Phase 8.

    agents.risk.limits  the limits, and breach detection over a settled record
    agents.risk.engine  the chain: breach -> freeze -> slash -> reduced allocation

The last link lives in Phase 7: `allocatable_agents` excludes FROZEN, SLASHED
and RETIRED, so a freeze moves capital without this module touching the
allocator.

Importing nothing at package level — `engine` is runnable with `python -m`.
"""
