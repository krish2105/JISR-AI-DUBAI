"""
collections.py — Collections agent: polite payment reminders for overdue invoices, always approved by the owner.

Why this file exists:
    Small exporters lose cash (and buyers) by chasing payments late or rudely. Jisr checks open invoices daily and
    drafts a reminder in the buyer's language with a tone that matches how late the payment is. Every reminder is
    an outbound message, so it waits in the approval inbox (P-OUT-001, autonomy L1).

    Anti-fraud by design: a reminder NEVER contains bank details. It points to the account on the original invoice
    and states that the seller never changes bank details by message (the most common trade fraud is a fake
    "our bank has changed" email). Marking an invoice paid is NEVER automatic (P-BANK-001: mark_payment_received).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.agents.state import PendingAction
from app.db.models import Approval, Invoice, Run
from app.db.session import session_scope
from app.governance.audit import append_audit
from app.governance.policy_engine import PolicyContext, get_policy_engine
from app.profile import get_business_profile

TIERS = [(7, "gentle"), (30, "firm"), (10_000, "final")]          # days overdue -> tone
TEXT = {
    "en": {
        "gentle": "Dear {buyer}, a friendly reminder that invoice {inv} for AED {amount:,.2f} was due on {due}. "
                  "If it is already paid, thank you and please ignore this message.",
        "firm": "Dear {buyer}, invoice {inv} for AED {amount:,.2f} is now {days} days overdue (due {due}). "
                "Please let us know the payment date.",
        "final": "Dear {buyer}, invoice {inv} for AED {amount:,.2f} is {days} days overdue (due {due}). "
                 "Please contact us today to agree a payment date.",
        "safety": "Please pay only to the account printed on the original invoice. We never change bank details "
                  "by email or WhatsApp; if you receive such a request, call us first.",
    },
    "ar": {
        "gentle": "السادة {buyer}، تذكير ودي بأن الفاتورة {inv} بمبلغ {amount:,.2f} درهم استحقت في {due}. "
                  "إذا تم الدفع بالفعل فشكراً لكم ونرجو تجاهل هذه الرسالة.",
        "firm": "السادة {buyer}، الفاتورة {inv} بمبلغ {amount:,.2f} درهم متأخرة {days} يوماً (تاريخ الاستحقاق {due}). "
                "نرجو إعلامنا بموعد الدفع.",
        "final": "السادة {buyer}، الفاتورة {inv} بمبلغ {amount:,.2f} درهم متأخرة {days} يوماً (تاريخ الاستحقاق {due}). "
                 "نرجو التواصل معنا اليوم للاتفاق على موعد الدفع.",
        "safety": "يرجى الدفع فقط إلى الحساب المذكور في الفاتورة الأصلية. نحن لا نغيّر بيانات الحساب البنكي أبداً عبر "
                  "البريد الإلكتروني أو واتساب؛ وإذا وصلكم طلب كهذا فاتصلوا بنا أولاً.",
    },
}
REMIND_EVERY = timedelta(days=7)


def tone_for(days_overdue: int) -> str:
    """Tone by lateness."""
    return next(tone for limit, tone in TIERS if days_overdue <= limit)


def reminder_text(invoice: Invoice, days_overdue: int) -> str:
    """The reminder in the buyer's language, always with the bank-safety line, never with bank details."""
    t = TEXT.get(invoice.language, TEXT["en"])
    body = t[tone_for(days_overdue)].format(buyer=invoice.buyer_name, inv=invoice.id, amount=invoice.amount_aed,
                                            due=invoice.due_on.date().isoformat(), days=days_overdue)
    return f"{body}\n\n{t['safety']}\n— {get_business_profile().seller_name}"


async def seed_demo_invoices(org_id: str = "demo", today: datetime | None = None) -> int:
    """Three SYNTHETIC open invoices for the demo organisation (idempotent)."""
    today = today or datetime.now(UTC)
    demo = [("INV-2026-031", "Bayt Al Hadaya Trading LLC", "en", 14712.50, 40, 10),
            ("INV-2026-034", "مؤسسة الواحة للهدايا", "ar", 22180.00, 75, 45),
            ("INV-2026-040", "Marina Home Decor LLC", "en", 9850.00, 10, -20)]       # not yet due
    added = 0
    async with session_scope() as db:
        for inv_id, buyer, lang, amount, issued_ago, overdue in demo:
            if await db.get(Invoice, inv_id) is None:
                db.add(Invoice(id=inv_id, org_id=org_id, buyer_name=buyer, language=lang, amount_aed=amount,
                               issued_on=today - timedelta(days=issued_ago), due_on=today - timedelta(days=overdue)))
                added += 1
    return added


async def run_collections(org_id: str, today: datetime | None = None, actor: str = "collections") -> list[dict]:
    """Draft reminders for overdue open invoices and queue them for approval through the policy engine."""
    today = today or datetime.now(UTC)
    engine = get_policy_engine()
    created = []
    async with session_scope() as db:
        invoices = (await db.scalars(select(Invoice).where(Invoice.org_id == org_id, Invoice.status == "open")
                                     .order_by(Invoice.due_on))).all()
        for inv in invoices:
            days = (today.date() - inv.due_on.date()).days
            if days <= 0 or (inv.last_reminder_at and today - inv.last_reminder_at < REMIND_EVERY):
                continue
            text = reminder_text(inv, days)
            title = f"Payment reminder {inv.id} ({days} days overdue, {inv.language.upper()})"
            action = PendingAction(
                action_type="send_message", title=title,
                payload={"text": text, "language": inv.language, "channel": "whatsapp",
                         "kind": "collection_reminder", "invoice_id": inv.id, "days_overdue": days,
                         "tone": tone_for(days)},
                requested_by="collections", reason=f"Invoice {inv.id} is {days} days overdue.",
                evidence=[f"due {inv.due_on.date().isoformat()}", f"AED {inv.amount_aed:,.2f}",
                          "no bank details in text"])
            decision = engine.evaluate(action, PolicyContext())
            risk = "high" if tone_for(days) == "final" else decision.risk      # over 30 days: owner should call
            run_id = f"run_{uuid.uuid4().hex[:12]}"
            note = f"[collections check] {inv.id}"
            db.add(Run(id=run_id, org_id=org_id, status="needs_approval", channel="whatsapp",
                       sample_id="collections", raw_redacted=note, contact_key=inv.contact_key,
                       state={"run_id": run_id, "org_id": org_id, "raw_message_redacted": note,
                              "status": "needs_approval", "plan": ["collections", "governance"]}))
            approval = Approval(id=f"apr_{uuid.uuid4().hex[:12]}", run_id=run_id, org_id=org_id,
                                action_type=action.action_type, title=action.title, payload=action.payload,
                                reason=action.reason, evidence=action.evidence, risk=risk,
                                rule_id=",".join(decision.rule_ids))
            db.add(approval)
            inv.last_reminder_at = today
            await append_audit(db, org_id=org_id, actor=actor, action="collections.reminder_drafted", run_id=run_id,
                               details={"invoice_id": inv.id, "days_overdue": days, "approval_id": approval.id,
                                        "rule_ids": decision.rule_ids, "effect": decision.effect})
            created.append({"invoice_id": inv.id, "days_overdue": days, "tone": tone_for(days), "run_id": run_id,
                            "approval_id": approval.id, "effect": decision.effect, "risk": risk})
    return created
