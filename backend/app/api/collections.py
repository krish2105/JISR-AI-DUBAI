"""
collections.py — Collections API.

    GET  /collections/invoices     open and paid invoices of the caller's organisation
    POST /collections/run          draft reminders for overdue invoices (each one waits in the approval inbox)
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.agents.collections import run_collections
from app.api.deps import org_id_header
from app.db.models import Invoice
from app.db.session import session_scope

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("/invoices")
async def invoices(org_id: str = Depends(org_id_header)) -> list[dict]:
    """Invoices with their due date and last reminder."""
    async with session_scope() as db:
        rows = (await db.scalars(select(Invoice).where(Invoice.org_id == org_id).order_by(Invoice.due_on))).all()
    return [{"id": i.id, "buyer_name": i.buyer_name, "language": i.language, "amount_aed": i.amount_aed,
             "issued_on": i.issued_on.date().isoformat(), "due_on": i.due_on.date().isoformat(), "status": i.status,
             "last_reminder_at": i.last_reminder_at.isoformat() if i.last_reminder_at else None} for i in rows]


@router.post("/run")
async def run(org_id: str = Depends(org_id_header)) -> dict:
    """Run the collections check now (normally daily)."""
    created = await run_collections(org_id)
    return {"drafted": len(created), "reminders": created}
