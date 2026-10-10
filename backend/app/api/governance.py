"""
governance.py — Governance API: kill switch, policies and autonomy levels, Agent Passports, autonomous actions.

    GET  /governance                    kill switch state, every policy rule, the autonomy level of every action type
    POST /governance/kill-switch        {"engaged": true|false, "reason": "..."}  (audited)
    GET  /governance/autonomous?hours=24  what the agents did on their own (from the audit chain)
    GET  /passports                     Agent Passports with live eval metrics and 24 h activity
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import org_id_header
from app.channels.outbox import set_kill_switch
from app.db.models import AuditEntry, OrgSettings, Run, RunEventRow
from app.db.session import session_scope
from app.governance.passports import passports_view
from app.governance.policy_engine import get_policy_engine

router = APIRouter(tags=["governance"])


class KillSwitchBody(BaseModel):
    """Turn the kill switch on (with a reason) or off."""

    engaged: bool
    reason: str | None = Field(default=None, max_length=500)


@router.get("/governance")
async def governance_status(org_id: str = Depends(org_id_header)) -> dict:
    """Everything that decides what Jisr may do, as data."""
    engine = get_policy_engine()
    async with session_scope() as db:
        row = await db.get(OrgSettings, org_id)
    return {
        "kill_switch": bool(row and row.kill_switch), "kill_reason": row.kill_reason if row else None,
        "updated_by": row.updated_by if row else None,
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        "policies": [{"id": r.id, "description": r.description, "effect": r.effect, "risk": r.risk,
                      "when": r.when.model_dump(exclude_none=True)} for r in engine.rules],
        "default_effect": engine.default_effect,
        "autonomy": [{"action_type": a, "level": v.get("level"), "why": v.get("why")}
                     for a, v in engine.autonomy.items()],
        "default_level": engine.default_level,
    }


@router.post("/governance/kill-switch")
async def kill_switch(body: KillSwitchBody, org_id: str = Depends(org_id_header)) -> dict:
    """Engage or release the organisation's kill switch (nothing leaves while it is on)."""
    async with session_scope() as db:
        await set_kill_switch(db, org_id, body.engaged, actor="human:demo-user", reason=body.reason)
    return await governance_status(org_id)


@router.get("/governance/autonomous")
async def autonomous_actions(hours: int = 24, org_id: str = Depends(org_id_header)) -> dict:
    """Actions Jisr performed without a human in the last N hours, straight from the audit chain."""
    since = datetime.now(UTC) - timedelta(hours=max(1, min(hours, 24 * 30)))
    async with session_scope() as db:
        rows = (await db.scalars(select(AuditEntry).where(
            AuditEntry.org_id == org_id, AuditEntry.ts >= since,
            AuditEntry.action.in_(["action.autonomous_sent", "policy.blocked", "send.refused_kill_switch"]))
            .order_by(AuditEntry.id.desc()).limit(200))).all()
    items = [{"id": r.id, "ts": r.ts.isoformat(), "action": r.action, "run_id": r.run_id, "details": r.details}
             for r in rows]
    return {"since": since.isoformat(), "done_alone": sum(i["action"] == "action.autonomous_sent" for i in items),
            "blocked": sum(i["action"] != "action.autonomous_sent" for i in items), "items": items}


@router.get("/passports")
async def passports(org_id: str = Depends(org_id_header)) -> list[dict]:
    """Agent Passports: permissions (enforced), autonomy, measured quality and recent activity."""
    from eval.common import latest_results  # the eval package reads backend/eval/results

    since = datetime.now(UTC) - timedelta(hours=24)
    async with session_scope() as db:
        rows = (await db.execute(
            select(RunEventRow.agent, RunEventRow.kind, func.count())
            .join(Run, Run.id == RunEventRow.run_id)
            .where(Run.org_id == org_id, RunEventRow.ts >= since)
            .group_by(RunEventRow.agent, RunEventRow.kind))).all()
    activity: dict[str, dict] = {}
    for agent, kind, count in rows:
        activity.setdefault(agent, {})[kind] = count
    engine = get_policy_engine()
    try:
        results = latest_results()
    except Exception:  # results folder missing in a slim deployment: passports still work
        results = {}
    return passports_view(results, engine.level_for, activity)
