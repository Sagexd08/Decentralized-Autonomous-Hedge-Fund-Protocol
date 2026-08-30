#!/usr/bin/env python3
"""
Phase 4 gate check — IRIS_BUILD_PROMPT v2.0 section 27.

Definition of Done:
    All 4 model classes return predictions via the common interface;
    baseline comparison logged.

Both clauses are checked, and the second is checked strictly: it is not enough
for a comparison to exist, it has to be *honest*. A model that answers the same
class every time, or whose regression error is orders of magnitude worse than
the baseline's, must not be reported as beating it — that was a real failure
here before the disqualifiers were added.

    docker compose up -d api
    python scripts/verify_phase4.py
"""

from __future__ import annotations

import subprocess
import sys

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"

PROBE = r"""
import json, random
import numpy as np
from ml.inference.registry import all_models, evaluate_all, format_report

rng = random.Random(11)
p, prices = 100.0, []
for _ in range(600):
    p += 0.02 * (100.0 - p) + rng.gauss(0, 0.6)
    prices.append(p)

scores = evaluate_all(np.array(prices), seed=0, train=True)
report = format_report(scores)

print("---REPORT---")
print(report)
print("---JSON---")
print(json.dumps({
    "classes": sorted(all_models()),
    "hashes": {n: m.model_hash for n, m in all_models().items()},
    "scores": {
        n: {
            "acc": s.accuracy, "mse": s.mse, "trades": s.trades,
            "dominant": s.dominant_class_share, "verdict": s.verdict,
            "version": s.model_version,
        } for n, s in scores.items()
    },
    "report_has_verdicts": "verdict" in report and "Beating the baseline:" in report,
}))
"""


def ok(label, detail=""):
    print(f"  {GREEN}PASS{RESET}  {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))
    return True


def bad(label, detail=""):
    print(f"  {RED}FAIL{RESET}  {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))
    return False


def main() -> int:
    print("\nPhase 4 gate — four model classes, one interface, honest comparison\n")
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "api", "python", "-c", PROBE],
        capture_output=True, text=True,
    )
    out = proc.stdout
    if "---JSON---" not in out:
        print(f"{RED}probe failed:{RESET}\n{(proc.stderr or out)[-2000:]}")
        return 2

    import json
    report, payload = out.split("---JSON---")
    data = json.loads(payload.strip())
    print(report.split("---REPORT---", 1)[-1].rstrip())
    print()

    r = []
    expected = ["baseline", "cnn_lstm", "gradient_boosting", "transformer"]
    r.append(ok("all four model classes present")
             if data["classes"] == expected
             else bad("all four model classes present", str(data["classes"])))

    hashes = set(data["hashes"].values())
    r.append(ok("each model has a distinct sha256 identity")
             if len(hashes) == 4 and all(len(h) == 64 for h in hashes)
             else bad("each model has a distinct sha256 identity"))

    scores = data["scores"]
    r.append(ok("every model produced a scored prediction set")
             if all(s["trades"] >= 0 and s["version"] for s in scores.values())
             else bad("every model produced a scored prediction set"))

    r.append(ok("comparison is printed, not buried")
             if data["report_has_verdicts"]
             else bad("comparison is printed, not buried"))

    r.append(ok("every model carries a verdict")
             if all(s["verdict"] != "UNSCORED" for s in scores.values())
             else bad("every model carries a verdict"))

    # The honesty checks.
    liars = [
        n for n, s in scores.items()
        if s["verdict"] == "BEATS BASELINE" and s["dominant"] >= 0.90
    ]
    r.append(ok("no degenerate model is reported as beating the baseline")
             if not liars else bad("no degenerate model claims a win", str(liars)))

    base_mse = scores["baseline"]["mse"]
    wild = [
        n for n, s in scores.items()
        if s["verdict"] == "BEATS BASELINE" and s["mse"] > base_mse * 10
    ]
    r.append(ok("no wildly-miscalibrated model claims a win")
             if not wild else bad("no wildly-miscalibrated model claims a win", str(wild)))

    winners = [n for n, s in scores.items() if s["verdict"] == "BEATS BASELINE"]
    r.append(ok("at least one model genuinely beats the baseline", ", ".join(winners))
             if winners
             else bad("at least one model genuinely beats the baseline",
                      "none — the ML layer is not earning its complexity"))

    print()
    if all(r):
        print(f"{GREEN}Phase 4 gate PASSED{RESET} — {len(r)}/{len(r)} checks.\n")
        return 0
    print(f"{RED}Phase 4 gate FAILED{RESET} — {sum(r)}/{len(r)}.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
