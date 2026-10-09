"""
gate.py — Compare the latest eval results with thresholds.yaml and the committed baseline.

Exit code 1 (CI fails) when:
    * a `hard` threshold is breached, or
    * any thresholded metric is worse than eval/baseline.json by more than `regression_margin`, or
    * a suite with a hard threshold has no results (nothing ran = not proven).
`target` thresholds are printed as TARGET (not failing) until their phase makes them hard.

Usage:
    uv run python -m eval.gate [--summary $GITHUB_STEP_SUMMARY]
    uv run python -m eval.gate --update-baseline      # after an intentional, reviewed change
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

from eval.common import BACKEND, latest_results

THRESHOLDS = BACKEND / "eval" / "thresholds.yaml"
BASELINE = BACKEND / "eval" / "baseline.json"


def evaluate(results: dict[str, dict], thresholds: dict, baseline: dict) -> tuple[list[tuple], bool]:
    """Return table rows (suite, metric, value, rule, status) and whether the gate failed."""
    margin = thresholds.get("regression_margin", 0.02)
    rows, failed = [], False
    for suite, metrics in thresholds.items():
        if suite == "regression_margin":
            continue
        res = results.get(suite)
        mode = "fast" if res and res.get("fast") else "full"
        for metric, rule in metrics.items():
            limit = rule.get("min", rule.get("max"))
            higher_better = "min" in rule
            phase = f", P{rule['phase']}" if "phase" in rule else ""
            rule_text = f"{'≥' if higher_better else '≤'} {limit} ({rule['gate']}{phase})"
            if res is None or metric not in res["metrics"]:
                # `optional` suites need local assets (e.g. the knowledge base): absent there = SKIP, not FAIL
                status = "MISSING" if rule["gate"] == "hard" and not rule.get("optional") else "SKIP"
                failed |= status == "MISSING"
                rows.append((suite, metric, "—", rule_text, status))
                continue
            value = res["metrics"][metric]
            ok = value >= limit if higher_better else value <= limit
            status = "PASS" if ok else ("FAIL" if rule["gate"] == "hard" else "TARGET")
            base = baseline.get(mode, {}).get(suite, {}).get(metric)
            if base is not None and rule.get("regression", True):
                worse = (base - value) if higher_better else (value - base)
                if worse > margin:
                    prefix = "FAIL + " if status == "FAIL" else ""
                    status = f"{prefix}REGRESSED (baseline {base:.3f})"
            failed |= status.startswith("FAIL") or "REGRESSED" in status
            rows.append((suite, metric, f"{value:.3f}", rule_text, status))
    return rows, failed


def markdown(rows: list[tuple]) -> str:
    """Render the gate table as markdown (for the terminal, the PR summary and EVAL_REPORT.md)."""
    lines = ["| suite | metric | value | rule | status |", "|---|---|---|---|---|"]
    lines += [f"| {s} | {m} | {v} | {r} | {st} |" for s, m, v, r, st in rows]
    return "\n".join(lines)


def update_baseline(results: dict[str, dict]) -> None:
    """Store the latest metrics as the baseline for their mode (fast/full)."""
    baseline = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    for suite, res in results.items():
        mode = "fast" if res.get("fast") else "full"
        baseline.setdefault(mode, {})[suite] = res["metrics"] | {"_git_sha": res["git_sha"]}
    BASELINE.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    print(f"Baseline updated: {BASELINE}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Eval quality gate")
    parser.add_argument("--summary", help="append the table to this markdown file (CI step summary)")
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()

    results = latest_results()
    if args.update_baseline:
        update_baseline(results)
        return 0
    thresholds = yaml.safe_load(THRESHOLDS.read_text())
    baseline = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    rows, failed = evaluate(results, thresholds, baseline)
    table = markdown(rows)
    print(table)
    print("\nGATE:", "FAILED" if failed else "PASSED")
    if args.summary:
        with Path(args.summary).open("a", encoding="utf-8") as fh:
            fh.write("## Eval gate\n\n" + table + f"\n\n**Gate: {'FAILED' if failed else 'PASSED'}**\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
