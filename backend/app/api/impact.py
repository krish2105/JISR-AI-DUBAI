"""
impact.py — The Impact Ledger: what Jisr did for the business, computed from the run records (never typed in).

    GET /impact?days=30    summary + one ledger row per run

Measured (from the database): enquiries handled, quotes drafted / approved / rejected, agent time per run, risks
caught (document issues, warning buyer signals, policy blocks), acknowledgements sent automatically and how fast,
CEPA duty "up to" amounts (the MFN duty a 0% preference would remove; the preferential rate still needs a human).
Estimated (clearly labelled): minutes saved = quotes drafted x (manual minutes - review minutes), from the
business profile's ROI assumptions until the pilot measures the real baseline.
"""

from datetime import UTC, datetime, timedelta
from statistics import median

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import org_id_header
from app.db.models import Approval, AuditEntry, Run, RunEventRow
from app.db.session import session_scope
from app.profile import get_business_profile

router = APIRouter(tags=["impact"])


@router.get("/impact")
async def impact(days: int = 30, org_id: str = Depends(org_id_header)) -> dict:
    """Summary and ledger for the last N days."""
    since = datetime.now(UTC) - timedelta(days=max(1, min(days, 365)))
    async with session_scope() as db:
        runs = (await db.scalars(select(Run).where(Run.org_id == org_id, Run.created_at >= since)
                                 .order_by(Run.created_at.desc()))).all()
        ids = [r.id for r in runs]
        events = (await db.scalars(select(RunEventRow).where(RunEventRow.run_id.in_(ids)))).all() if ids else []
        approvals = (await db.scalars(select(Approval).where(Approval.run_id.in_(ids)))).all() if ids else []
        audit = (await db.scalars(select(AuditEntry).where(AuditEntry.org_id == org_id, AuditEntry.ts >= since,
                                                           AuditEntry.action.in_(["action.autonomous_sent",
                                                                                  "policy.blocked"])))).all()
    by_run: dict[str, list[RunEventRow]] = {}
    for e in events:
        by_run.setdefault(e.run_id, []).append(e)
    ack_seconds, agent_seconds, ledger = [], [], []
    for run in runs:
        evs = sorted(by_run.get(run.id, []), key=lambda e: e.seq)
        start = next((e.ts for e in evs if e.kind == "run_started"), None)
        gov = next((e.ts for e in evs if e.agent == "governance" and e.kind == "agent_finished"), None)
        ack = next((e.ts for e in evs if e.kind == "tool_result" and e.payload.get("tool") == "send_acknowledgement"),
                   None)
        secs = (gov - start).total_seconds() if start and gov else None
        if secs is not None:
            agent_seconds.append(secs)
        if start and ack:
            ack_seconds.append((ack - start).total_seconds())
        s = run.state or {}
        risks = (len(s.get("doc_issues", [])) +
                 sum(1 for x in s.get("buyer_signals", []) if x.get("risk") in ("medium", "high")))
        ledger.append({"run_id": run.id, "created_at": run.created_at.isoformat(), "channel": run.channel,
                       "status": run.status, "buyer": (s.get("rfq") or {}).get("buyer_name"),
                       "quote_total_aed": (s.get("quote") or {}).get("total_aed"),
                       "duty_upto_aed": (s.get("impact") or {}).get("duty_saving_upto_aed"),
                       "risks": risks, "agent_seconds": round(secs, 1) if secs is not None else None,
                       "kind": "collections" if run.sample_id == "collections" else
                               ("clarification" if any(d.get("kind") == "clarification" for d in s.get("drafts", []))
                                else "quote" if (s.get("quote") or {}).get("lines") else "other")})
    quotes = [r for r in ledger if r["kind"] == "quote"]
    roi = get_business_profile().roi
    saved = len(quotes) * max(0.0, roi.manual_minutes_per_quote - roi.review_minutes_per_quote)
    approved = [a for a in approvals if a.status == "approved"]
    return {
        "since": since.isoformat(), "days": days,
        "measured": {
            "enquiries": len(runs), "quotes_drafted": len(quotes),
            "approved_and_sent": len(approved), "rejected": sum(a.status == "rejected" for a in approvals),
            "waiting": sum(a.status == "pending" for a in approvals),
            "median_agent_seconds": round(median(agent_seconds), 1) if agent_seconds else None,
            "acknowledged_automatically": sum(a.action == "action.autonomous_sent" for a in audit),
            "median_seconds_to_acknowledge": round(median(ack_seconds), 1) if ack_seconds else None,
            "risks_caught": sum(r["risks"] for r in ledger) + sum(a.action == "policy.blocked" for a in audit),
            "blocked_by_policy": sum(a.action == "policy.blocked" for a in audit),
            "duty_upto_aed": round(sum(r["duty_upto_aed"] or 0 for r in ledger), 2),
        },
        "estimated": {"minutes_saved": round(saved), "assumptions": roi.model_dump()},
        "ledger": ledger[:200],
    }
