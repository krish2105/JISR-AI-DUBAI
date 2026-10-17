"""
audit.py — Read-only API for the hash-chained audit log.

    GET /audit?limit=50      newest entries first
    GET /audit/verify        recompute the whole chain; reports the first tampered row
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import require
from app.auth.service import Principal
from app.db.models import AuditEntry
from app.db.session import session_scope
from app.governance.audit import verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit(limit: int = 50, principal: Principal = Depends(require("audit.read"))) -> list[dict]:
    """Latest audit entries for the caller's organisation."""
    async with session_scope() as db:
        rows = (await db.scalars(select(AuditEntry).where(AuditEntry.org_id == principal.org_id)
                                 .order_by(AuditEntry.id.desc()).limit(min(limit, 500)))).all()
    return [{"id": e.id, "ts": e.ts.isoformat(), "actor": e.actor, "action": e.action, "run_id": e.run_id,
             "details": e.details, "hash": e.hash, "prev_hash": e.prev_hash} for e in rows]


@router.get("/verify")
async def verify(principal: Principal = Depends(require("audit.read"))) -> dict:
    """Verify the organisation's chain end to end."""
    async with session_scope() as db:
        report = await verify_chain(db, principal.org_id)
    return report.model_dump()


@router.get("/export")
async def export(principal: Principal = Depends(require("audit.export"))) -> dict:
    """The whole chain, oldest first, with its verification report (for auditors and advisers)."""
    async with session_scope() as db:
        report = await verify_chain(db, principal.org_id)
        rows = (await db.scalars(select(AuditEntry).where(AuditEntry.org_id == principal.org_id)
                                 .order_by(AuditEntry.id))).all()
    return {"org_id": principal.org_id, "verification": report.model_dump(),
            "entries": [{"id": e.id, "ts": e.ts.isoformat(), "actor": e.actor, "action": e.action,
                         "run_id": e.run_id, "details": e.details, "prev_hash": e.prev_hash, "hash": e.hash}
                        for e in rows]}
