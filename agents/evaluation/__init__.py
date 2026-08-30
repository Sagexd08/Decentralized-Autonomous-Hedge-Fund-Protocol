"""
Prediction settlement and evaluation — IRIS_BUILD_PROMPT v2.0 Phase 5.

    agents.evaluation.prices      the reference price, and the refusal to invent one
    agents.evaluation.scoring     how a settled prediction earns a number
    agents.evaluation.settlement  the sweep, and the CLI that runs it

Deliberately importing nothing at package level. `settlement` and `prices` are
both runnable with `python -m`, and re-exporting them here means the package is
already in `sys.modules` when the module runs as `__main__` — which Python
reports as a RuntimeWarning about unpredictable behaviour, because the module
then exists twice under two names.
"""
