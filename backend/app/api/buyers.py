"""
buyers.py — Buyers and their data rights (Phase 20, DECISIONS H4).

    GET    /buyers                         buyers Jisr remembers (masked contact, counts, signals)   (buyers.read)
    GET    /buyers/{contact_key}/export    everything held about one buyer (access request)          (buyers.read)
    DELETE /buyers/{contact_key}           erase one buyer (contact, memory, message text)           (buyers.erase)

Erasure keeps what the business must keep (invoice amounts and dates, approvals' decisions, the hash-chained audit
log, which never contains message text or contact details) and removes or scrubs everything that identifies the buyer.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update

from app.api.deps import require
from app.auth.service import Principal
from app.db.models import Approval, BuyerMemory, Contact, Invoice, Run
from app.db.session import session_scope
from app.governance.audit import append_audit

router = APIRouter(prefix="/buyers", tags=["buyers"])
ERASED = "[erased at the buyer's request]"


def _mask(address: str | None) -> str:
    """Show enough to recognise a contact, not enough to use it."""
    if not address:
        return "—"
    if len(address) <= 6:
        return "•" * len(address)
    return f"{address[:5]}•••{address[-2:]}"


@router.get("")
async def buyers(principal: Principal = Depends(require("buyers.read"))) -> list[dict]:
    async with session_scope() as db:
        rows = (await db.execute(
            select(BuyerMemory, Contact).outerjoin(Contact, Contact.contact_key == BuyerMemory.contact_key)
            .where(BuyerMemory.org_id == principal.org_id).order_by(BuyerMemory.last_seen.desc()))).all()
    return [{"contact_key": m.contact_key, "channel": c.channel if c else None,
             "contact": _mask(c.address if c else None),
             "name": c.display_name if c else None, "first_seen": m.first_seen.isoformat(),
             "last_seen": m.last_seen.isoformat(), "runs": m.runs, "quotes_sent": m.quotes_sent,
             "last_incoterm": m.last_incoterm, "last_quote_total_aed": m.last_quote_total_aed,
             "languages": m.languages, "risk_signals": m.risk_signals} for m, c in rows]


async def _owned(db, principal: Principal, contact_key: str) -> tuple[Contact | None, BuyerMemory | None]:
    contact = await db.get(Contact, contact_key)
    memory = await db.get(BuyerMemory, (contact_key, principal.org_id))
    if (contact is None or contact.org_id != principal.org_id) and memory is None:
        raise HTTPException(404, "Buyer not found.")
    return (contact if contact is not None and contact.org_id == principal.org_id else None), memory


@router.get("/{contact_key}/export")
async def export(contact_key: str, principal: Principal = Depends(require("buyers.read"))) -> dict:
    """Everything Jisr holds about one buyer, for a data-subject access request."""
    async with session_scope() as db:
        contact, memory = await _owned(db, principal, contact_key)
        runs = (await db.scalars(select(Run).where(Run.org_id == principal.org_id, Run.contact_key == contact_key)
                                 .order_by(Run.created_at))).all()
        run_ids = [r.id for r in runs]
        approvals = (await db.scalars(select(Approval).where(Approval.run_id.in_(run_ids)))).all() if run_ids else []
        invoices = (await db.scalars(select(Invoice).where(Invoice.org_id == principal.org_id,
                                                           Invoice.contact_key == contact_key))).all()
        await append_audit(db, org_id=principal.org_id, actor=principal.actor, action="data.buyer_exported",
                           details={"contact_key": contact_key, "runs": len(runs)})
    return {
        "contact": {"channel": contact.channel, "address": contact.address, "name": contact.display_name,
                    "last_inbound_at": contact.last_inbound_at.isoformat() if contact.last_inbound_at else None}
        if contact else None,
        "memory": {"runs": memory.runs, "quotes_sent": memory.quotes_sent, "languages": memory.languages,
                   "last_incoterm": memory.last_incoterm, "risk_signals": memory.risk_signals} if memory else None,
        "enquiries": [{"run_id": r.id, "received": r.created_at.isoformat(), "status": r.status,
                       "message_masked": r.raw_redacted,
                       "quote_total_aed": (r.state.get("quote") or {}).get("total_aed")} for r in runs],
        "replies": [{"run_id": a.run_id, "status": a.status, "text": a.payload.get("text")} for a in approvals],
        "invoices": [{"number": i.number or i.id, "amount_aed": i.amount_aed, "status": i.status,
                      "due_on": i.due_on.date().isoformat()} for i in invoices],
    }


@router.delete("/{contact_key}")
async def erase(contact_key: str, principal: Principal = Depends(require("buyers.erase"))) -> dict:
    """Erase a buyer: contact and memory deleted, message text and drafts scrubbed, invoices unlinked (kept)."""
    async with session_scope() as db:
        contact, memory = await _owned(db, principal, contact_key)
        runs = (await db.scalars(select(Run).where(Run.org_id == principal.org_id,
                                                   Run.contact_key == contact_key))).all()
        for run in runs:
            state = dict(run.state or {})
            state["raw_message_redacted"] = ERASED
            state["drafts"] = [{**d, "text": ERASED} for d in state.get("drafts") or []]
            if isinstance(state.get("rfq"), dict):
                state["rfq"] = {**state["rfq"], "buyer_name": None}
            state["contact_key"] = None
            run.state, run.raw_redacted, run.contact_key = state, ERASED, None
        run_ids = [r.id for r in runs]
        if run_ids:
            for approval in (await db.scalars(select(Approval).where(Approval.run_id.in_(run_ids)))).all():
                if approval.payload.get("text"):
                    approval.payload = {**approval.payload, "text": ERASED}
        await db.execute(update(Invoice).where(Invoice.org_id == principal.org_id, Invoice.contact_key == contact_key)
                         .values(contact_key=None))
        if contact is not None:
            await db.delete(contact)
        if memory is not None:
            await db.delete(memory)
        await append_audit(db, org_id=principal.org_id, actor=principal.actor, action="data.buyer_erased",
                           details={"contact_key": contact_key, "runs_scrubbed": len(runs)})
    return {"erased": contact_key, "runs_scrubbed": len(runs)}
