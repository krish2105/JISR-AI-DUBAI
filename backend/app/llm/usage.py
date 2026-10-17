"""
usage.py — Tokens and cost per run (Phase 14): what one quote costs, measured, not estimated.

The router adds every call's tokens to the accumulator of the run that is executing (a context variable set by
`execute_run`); the run stores the totals in its state (`usage`). Prices come from pricing.yaml (published rates,
dated); unknown and offline models cost 0 and are labelled.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

import yaml

PRICING_FILE = Path(__file__).with_name("pricing.yaml")
_RUN_USAGE: ContextVar[dict | None] = ContextVar("run_usage", default=None)


@lru_cache
def pricing() -> dict:
    return yaml.safe_load(PRICING_FILE.read_text(encoding="utf-8"))


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Cost of one call at published rates (0.0 for offline, budget-fallback or unpriced models: exact ids only)."""
    price = pricing()["models"].get(model)
    if not price:
        return 0.0
    return input_tokens / 1e6 * price["input_per_mtok"] + output_tokens / 1e6 * price["output_per_mtok"]


def record(model: str, input_tokens: int, output_tokens: int) -> None:
    """Add one call to the current run's totals (no-op outside a run)."""
    acc = _RUN_USAGE.get()
    if acc is None:
        return
    acc["calls"] += 1
    acc["input_tokens"] += input_tokens
    acc["output_tokens"] += output_tokens
    acc["cost_usd"] = round(acc["cost_usd"] + cost_usd(model, input_tokens, output_tokens), 6)
    per = acc["by_model"].setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
    per["calls"] += 1
    per["input_tokens"] += input_tokens
    per["output_tokens"] += output_tokens


@contextmanager
def tracking_run():
    """Collect usage for the code inside the block; yields the accumulator dict."""
    acc = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "by_model": {},
           "prices_as_of": pricing()["as_of"]}
    token = _RUN_USAGE.set(acc)
    try:
        yield acc
    finally:
        _RUN_USAGE.reset(token)
