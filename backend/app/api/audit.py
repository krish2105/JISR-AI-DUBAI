"""
audit.py — Read-only API for the hash-chained audit log.

    GET /audit?limit=50      newest entries first
    GET /audit/verify        recompute the whole chain; reports the first tampered row
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import org_id_header
from app.db.models import AuditEntry
from app.db.session import session_scope
from app.governance.audit import verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit(limit: int = 50, org_id: str = Depends(org_id_header)) -> list[dict]:
    """Latest audit entries for the caller's organisation."""
    async with session_scope() as db:
        rows = (await db.scalars(select(AuditEntry).where(AuditEntry.org_id == org_id)
                                 .order_by(AuditEntry.id.desc()).limit(min(limit, 500)))).all()
    return [{"id": e.id, "ts": e.ts.isoformat(), "actor": e.actor, "action": e.action, "run_id": e.run_id,
             "details": e.details, "hash": e.hash, "prev_hash": e.prev_hash} for e in rows]


@router.get("/verify")
async def verify(org_id: str = Depends(org_id_header)) -> dict:
    """Verify the organisation's chain end to end."""
    async with session_scope() as db:
        report = await verify_chain(db, org_id)
    return report.model_dump()
