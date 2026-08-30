"""
MWU capital allocation — IRIS_BUILD_PROMPT v2.0 section 7, Phase 7.

    agents.allocation.mwu        the update rule, and the four invariants
    agents.allocation.allocator  driving it from real reputation

Allocation authority is not custody. This decides how much of a vault an agent
may direct; the on-chain gate in Phase 2 is what stops it ever holding a key.

Importing nothing at package level — `allocator` is runnable with `python -m`,
and re-exporting would put the package in sys.modules before the module runs as
__main__.
"""
