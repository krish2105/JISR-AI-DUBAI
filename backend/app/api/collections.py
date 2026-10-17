"""
collections.py — Collections API.

    GET  /collections/invoices     open and paid invoices of the caller's organisation
    POST /collections/run          draft reminders for overdue invoices (each one waits in the approval inbox)
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.agents.collections import run_collections
from app.api.deps import require
from app.auth.service import Principal
from app.db.models import Invoice
from app.db.session import session_scope

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("/invoices")
async def invoices(principal: Principal = Depends(require("runs.read"))) -> list[dict]:
    """Invoices with their due date and last reminder."""
    async with session_scope() as db:
        rows = (await db.scalars(select(Invoice).where(Invoice.org_id == principal.org_id)
                                 .order_by(Invoice.due_on))).all()
    return [{"id": i.id, "number": i.number or i.id, "buyer_name": i.buyer_name, "language": i.language,
             "amount_aed": i.amount_aed,
             "issued_on": i.issued_on.date().isoformat(), "due_on": i.due_on.date().isoformat(), "status": i.status,
             "last_reminder_at": i.last_reminder_at.isoformat() if i.last_reminder_at else None} for i in rows]


@router.post("/run")
async def run(principal: Principal = Depends(require("collections.run"))) -> dict:
    """Run the collections check now (normally daily)."""
    created = await run_collections(principal.org_id, actor=f"collections ({principal.actor})")
    return {"drafted": len(created), "reminders": created}
