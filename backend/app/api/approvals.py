"""
approvals.py — The approval inbox API.

    GET  /approvals?status=pending       held actions for the caller's organisation
    POST /approvals/{id}/approve         approve (optionally with an edited draft text)
    POST /approvals/{id}/reject          reject (with an optional note)

Note: v3 sketched `POST /approvals/{id}:approve`; we use `/approvals/{id}/approve` because
path segments are clearer in FastAPI and in browser tools (docs/DECISIONS.md E8).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import org_id_header
from app.db.models import Approval
from app.db.session import session_scope
from app.runs.service import ApprovalError, decide

router = APIRouter(prefix="/approvals", tags=["approvals"])


class DecisionBody(BaseModel):
    """Optional note, and for approvals an optional edited message text."""

    note: str | None = Field(default=None, max_length=1000)
    edited_text: str | None = Field(default=None, max_length=8000)


def _approval_dict(a: Approval) -> dict:
    """Serialise an approval for the dashboard."""
    return {
        "id": a.id, "run_id": a.run_id, "created_at": a.created_at.isoformat(), "action_type": a.action_type,
        "title": a.title, "payload": a.payload, "reason": a.reason, "evidence": a.evidence, "risk": a.risk,
        "rule_id": a.rule_id, "status": a.status, "decided_by": a.decided_by,
        "decided_at": a.decided_at.isoformat() if a.decided_at else None, "decision_note": a.decision_note,
    }


@router.get("")
async def list_approvals(status: str = "pending", org_id: str = Depends(org_id_header)) -> list[dict]:
    """Approvals of the caller's organisation, newest first (`status=all` for every state)."""
    query = select(Approval).where(Approval.org_id == org_id)
    if status != "all":
        query = query.where(Approval.status == status)
    async with session_scope() as db:
        rows = (await db.scalars(query.order_by(Approval.created_at.desc()).limit(100))).all()
    return [_approval_dict(a) for a in rows]


async def _decide(approval_id: str, decision: str, body: DecisionBody, org_id: str) -> dict:
    """Shared handler: map service errors to HTTP status codes."""
    try:
        approval = await decide(approval_id, org_id=org_id, decision=decision, note=body.note,
                                edited_text=body.edited_text if decision == "approve" else None)
    except ApprovalError as exc:
        code = 404 if "not found" in str(exc) else 409
        raise HTTPException(code, str(exc)) from exc
    return _approval_dict(approval)


@router.post("/{approval_id}/approve")
async def approve(approval_id: str, body: DecisionBody | None = None, org_id: str = Depends(org_id_header)) -> dict:
    """Approve a held action (and perform it through the simulator)."""
    return await _decide(approval_id, "approve", body or DecisionBody(), org_id)


@router.post("/{approval_id}/reject")
async def reject(approval_id: str, body: DecisionBody | None = None, org_id: str = Depends(org_id_header)) -> dict:
    """Reject a held action; nothing is sent."""
    return await _decide(approval_id, "reject", body or DecisionBody(), org_id)
