"""
fx.py — Exchange rates with source and timestamp (INR -> AED).

Why this file exists:
    A quote is only as good as its exchange rate, and a judge (or a buyer) will ask "which rate, from when?".
    Every rate Jisr uses carries its source, the date of the published rate and when we fetched it.

How INR -> AED is computed (live provider):
    The ECB reference rates (via the free Frankfurter API) do not include AED, but the UAE dirham is pegged to
    the US dollar at 3.6725 AED/USD (Central Bank of the UAE, since 1997). So:
        INR -> AED = 3.6725 / (USD -> INR)
Providers:
    fixed  a configured demo rate (tests, offline demo, replay): deterministic, clearly labelled
    live   Frankfurter (ECB) USD/INR x AED peg; cached for FX_CACHE_HOURS; if the API is down, the last good
           rate is used and marked `stale` (never silently)
"""

import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.config import get_settings

AED_PER_USD = 3.6725                    # CBUAE peg; see docs/CLAIMS_REGISTER.md
FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=INR"


class FxRate(BaseModel):
    """One INR -> AED rate with full provenance."""

    base: str = "INR"
    quote: str = "AED"
    rate: float
    source: str
    rate_date: str | None = None        # date the rate was published (ECB business day)
    fetched_at: str                     # when Jisr obtained it (UTC ISO)
    stale: bool = False                 # True if the live API failed and a cached rate was reused


_memory_cache: dict[str, tuple[float, FxRate]] = {}


def _cache_file() -> Path:
    """Where the last good live rate is kept (for stale fallback across restarts)."""
    return Path(get_settings().trace_dir) / "fx_cache.json"


def fixed_rate(rate: float) -> FxRate:
    """The configured demo rate, labelled as such."""
    return FxRate(rate=rate, source="Fixed demo rate (configured; not a market rate)",
                  fetched_at=datetime.now(UTC).isoformat(timespec="seconds"))


async def live_rate() -> FxRate:
    """ECB USD/INR via Frankfurter combined with the AED peg; cached; stale fallback on failure."""
    ttl = get_settings().fx_cache_hours * 3600
    cached = _memory_cache.get("INR_AED")
    if cached and time.time() - cached[0] < ttl:
        return cached[1]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(FRANKFURTER_URL)
            resp.raise_for_status()
            data = resp.json()
        usd_inr = float(data["rates"]["INR"])
        fx = FxRate(rate=round(AED_PER_USD / usd_inr, 6),
                    source=f"ECB reference USD/INR {usd_inr} via Frankfurter x CBUAE peg {AED_PER_USD} AED/USD",
                    rate_date=data.get("date"), fetched_at=datetime.now(UTC).isoformat(timespec="seconds"))
        _memory_cache["INR_AED"] = (time.time(), fx)
        path = _cache_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fx.model_dump_json(), encoding="utf-8")
        return fx
    except (httpx.HTTPError, KeyError, ValueError):
        path = _cache_file()
        if path.exists():
            return FxRate.model_validate_json(path.read_text(encoding="utf-8")).model_copy(update={"stale": True})
        raise


async def get_inr_to_aed(fixed: float) -> FxRate:
    """The rate the quote should use, per the FX_PROVIDER setting (fixed | live)."""
    if get_settings().fx_provider == "live":
        try:
            return await live_rate()
        except Exception:
            return fixed_rate(fixed).model_copy(update={"source": "Fixed demo rate (live FX unavailable)",
                                                        "stale": True})
    return fixed_rate(fixed)
