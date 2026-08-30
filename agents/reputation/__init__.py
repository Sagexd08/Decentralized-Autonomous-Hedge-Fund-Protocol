"""
The IRIS Score — IRIS_BUILD_PROMPT v2.0 section 12, Phase 6.

    agents.reputation.dimensions  the six dimensions, each a pure function
    agents.reputation.score       the weighted score, and the CLI

Importing nothing at package level, for the same reason as
`agents.evaluation`: `score` is runnable with `python -m`, and re-exporting it
here puts the package in `sys.modules` before the module runs as `__main__`,
which Python reports as a RuntimeWarning about the module existing twice.
"""
