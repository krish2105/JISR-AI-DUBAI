"""
ops.py — Operations metrics for owners and admins (Phase 14): volume, speed, errors, model tokens and cost.

    GET /ops/metrics?days=7     (ops.read)

Everything is computed from the organisation's own run records and events; cost uses the per-run usage recorded by
the model router at published prices (pricing.yaml), so "cost per quote" is measured, not estimated.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import median

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import require
from app.auth.service import Principal
from app.config import get_settings
from app.db.models import Approval, Run, RunEventRow
from app.db.session import session_scope
from app.llm.router import get_router
from app.llm.usage import pricing

router = APIRouter(prefix="/ops", tags=["operations"])


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(q * len(ordered)))], 2)


@router.get("/metrics")
async def metrics(days: int = 7, principal: Principal = Depends(require("ops.read"))) -> dict:
    days = max(1, min(days, 90))
    since = datetime.now(UTC) - timedelta(days=days)
    async with session_scope() as db:
        runs = (await db.scalars(select(Run).where(Run.org_id == principal.org_id, Run.created_at >= since))).all()
        run_ids = [r.id for r in runs]
        spans = (await db.execute(
            select(RunEventRow.run_id, func.min(RunEventRow.ts), func.max(RunEventRow.ts))
            .where(RunEventRow.run_id.in_(run_ids)).group_by(RunEventRow.run_id))).all() if run_ids else []
        errors = await db.scalar(select(func.count()).select_from(RunEventRow).where(
            RunEventRow.run_id.in_(run_ids), RunEventRow.kind == "error")) if run_ids else 0
        pending = (await db.scalars(select(Approval.created_at).where(
            Approval.org_id == principal.org_id, Approval.status == "pending"))).all()

    per_day: dict[str, dict] = defaultdict(lambda: {"runs": 0, "tokens": 0, "cost_usd": 0.0})
    statuses: dict[str, int] = defaultdict(int)
    quote_costs = []
    for r in runs:
        day = per_day[r.created_at.date().isoformat()]
        usage = (r.state or {}).get("usage") or {}
        day["runs"] += 1
        day["tokens"] += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        day["cost_usd"] = round(day["cost_usd"] + usage.get("cost_usd", 0.0), 6)
        statuses[r.status] += 1
        if (r.state or {}).get("quote"):
            quote_costs.append(usage.get("cost_usd", 0.0))
    seconds = [(end - start).total_seconds() for _, start, end in spans if start and end]
    now = datetime.now(UTC)
    settings = get_settings()
    return {
        "days": days, "since": since.isoformat(), "llm_profile": settings.llm_profile,
        "runs": len(runs), "by_status": dict(statuses), "per_day": dict(sorted(per_day.items())),
        "agent_seconds": {"p50": _pct(seconds, 0.5), "p95": _pct(seconds, 0.95), "median": round(median(seconds), 2)
                          if seconds else None},
        "error_events": errors or 0,
        "error_rate": round((errors or 0) / len(runs), 4) if runs else 0.0,
        "cost": {"total_usd": round(sum(d["cost_usd"] for d in per_day.values()), 6),
                 "per_quote_usd": round(sum(quote_costs) / len(quote_costs), 6) if quote_costs else None,
                 "prices_as_of": pricing()["as_of"]},
        "approvals": {"pending": len(pending),
                      "oldest_minutes": round(max((now - p).total_seconds() for p in pending) / 60, 1)
                      if pending else None},
        "budget": get_router().budget_status(),
    }
