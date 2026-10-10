"""
run.py — Run evaluation suites and write results + docs/EVAL_REPORT.md.

Usage (from the repo root):
    make eval                     # all suites, all splits (full run)
    make eval-fast                # test split only, small e2e sample (CI on every PR)
    uv --directory backend run python -m eval.run --suite extraction --profile dev

The run uses a throwaway SQLite database and no demo pacing, so it never touches your dev data.
`--profile` picks the LLM profile (fake by default; dev = free tiers on synthetic data; prod = Claude).
"""

import argparse
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

SUITES = ["pricing", "security", "extraction", "docs", "trust", "governance", "redteam", "e2e", "retrieval"]


def configure_environment(profile: str) -> None:
    """Set settings BEFORE the app is imported (settings are read from the environment)."""
    tmp = Path(tempfile.mkdtemp(prefix="jisr-eval-"))
    os.environ.update({
        "LLM_PROFILE": profile,
        "DATABASE_URL": f"sqlite:///{tmp / 'eval.db'}",
        "TRACE_DIR": str(tmp / "traces"),
        "DEMO_STEP_DELAY_MS": "0",
        "LLM_RECORD": "false",
        "APP_ENV": "test",
    })


async def main_async(args: argparse.Namespace) -> int:
    """Run the requested suites one after another and print a summary."""
    import importlib

    from app.db.session import get_engine, init_db
    from eval import report
    from eval.common import EvalContext, write_result

    ctx = EvalContext(fast=args.fast, split=args.split, concurrency=args.concurrency)
    await init_db()
    chosen = SUITES if args.suite == "all" else args.suite.split(",")
    print(f"Eval: suites={chosen} profile={os.environ['LLM_PROFILE']} mode={'fast' if args.fast else 'full'}")
    for name in chosen:
        started = time.perf_counter()
        module = importlib.import_module(f"eval.suites.{name}")
        result = await module.run(ctx)
        path = write_result(result, ctx)
        shown = ", ".join(f"{k}={v:.3f}" for k, v in result.metrics.items())
        print(f"  {name:<11} n={result.n:<4} {shown}  ({time.perf_counter() - started:.1f}s) -> {path.name}")
    await get_engine().dispose()
    report.write()
    print(f"Report: {report.REPORT}")
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run Jisr evaluation suites")
    parser.add_argument("--suite", default="all", help=f"all or comma list of {SUITES}")
    parser.add_argument("--fast", action="store_true", help="test split only (CI)")
    parser.add_argument("--split", choices=["train", "dev", "test"], help="restrict to one split")
    parser.add_argument("--profile", default=os.environ.get("EVAL_PROFILE", "fake"),
                        choices=["fake", "dev", "prod", "replay"])
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()
    configure_environment(args.profile)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
