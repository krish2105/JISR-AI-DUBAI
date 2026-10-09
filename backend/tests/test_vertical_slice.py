"""
test_vertical_slice.py — Phase 1 acceptance: enquiry -> agents -> governance -> approval -> audit.

These tests call the run service directly (no HTTP) with the fake model, so they are fast
and fully offline. test_api.py covers the same path over HTTP.
"""

import pytest
from sqlalchemy import select

from app.db.models import Approval, AuditEntry, Run, RunEventRow
from app.db.session import session_scope
from app.demo.samples import get_sample
from app.governance.audit import verify_chain
from app.runs.service import ApprovalError, create_run, decide


async def _run(sample_id: str) -> str:
    """Run a demo sample to completion (synchronously) and return its id."""
    sample = get_sample(sample_id)
    return await create_run(message=sample.message, channel=sample.channel, sample_id=sample_id, background=False)


async def _events(run_id: str) -> list[RunEventRow]:
    """All stored events of a run, in order."""
    async with session_scope() as db:
        return list((await db.scalars(select(RunEventRow).where(RunEventRow.run_id == run_id)
                                      .order_by(RunEventRow.seq))).all())


async def _approvals(run_id: str) -> list[Approval]:
    """All approvals of a run."""
    async with session_scope() as db:
        return list((await db.scalars(select(Approval).where(Approval.run_id == run_id))).all())


async def test_english_enquiry_reaches_the_approval_inbox(db_ready):
    """Every agent runs in order, a quote is priced, and one reply waits for approval."""
    run_id = await _run("en_brass_runners")
    events = await _events(run_id)

    started = [e.agent for e in events if e.kind == "agent_started"]
    assert started == ["ingest", "guard", "supervisor", "quote", "duty", "docs", "trust", "outreach", "governance"]
    assert [e.seq for e in events] == list(range(1, len(events) + 1))      # gap-free ordering
    # Governance commits the approval, announces it, then reports itself finished.
    assert [(e.agent, e.kind) for e in events[-2:]] == [("governance", "approval_needed"),
                                                         ("governance", "agent_finished")]

    async with session_scope() as db:
        run = await db.get(Run, run_id)
    assert run.status == "needs_approval"
    lines = run.state["quote"]["lines"]
    assert [ln["quantity"] for ln in lines] == [500, 200]
    # 450 INR cost + 22% margin = 549.00 INR; x 0.0436 = 23.94 AED per lamp (stub FX)
    assert lines[0]["unit_price_inr"] == 549.0 and lines[0]["unit_price_aed"] == 23.94
    # Invoice consistency to the cent: line total = unit price x qty; quote total = sum of lines.
    for ln in lines:
        assert round(ln["unit_price_aed"] * ln["quantity"], 2) == ln["total_aed"]
        assert round(ln["unit_price_inr"] * ln["quantity"], 2) == ln["total_inr"]
    assert round(sum(ln["total_aed"] for ln in lines), 2) == run.state["quote"]["total_aed"]
    assert lines[0]["total_aed"] == 11970.0                                # 23.94 x 500
    assert "ahmed.k" not in run.raw_redacted                               # PII never stored

    [approval] = await _approvals(run_id)
    assert approval.action_type == "send_message" and approval.rule_id == "P-OUT-001"
    assert "Bayt Al Hadaya Trading LLC" in approval.payload["text"]


async def test_approving_sends_via_simulator_and_audits(db_ready):
    """Approve -> simulated send, audit entries, run marked sent, terminal `done` event."""
    run_id = await _run("en_brass_runners")
    [approval] = await _approvals(run_id)
    await decide(approval.id, org_id="demo", decision="approve", edited_text="Edited by owner")

    async with session_scope() as db:
        run = await db.get(Run, run_id)
        actions = [a.action for a in (await db.scalars(select(AuditEntry).where(AuditEntry.run_id == run_id)
                                                       .order_by(AuditEntry.id))).all()]
        chain = await verify_chain(db, "demo")
    assert run.status == "sent"
    assert actions == ["run.created", "approval.requested", "approval.approved", "message.sent_simulated"]
    assert chain.ok
    events = await _events(run_id)
    assert events[-1].kind == "done" and events[-1].payload["status"] == "sent"
    [approval] = await _approvals(run_id)
    assert approval.payload["text"] == "Edited by owner" and approval.payload["edited_by_human"]


async def test_rejecting_sends_nothing(db_ready):
    """Reject -> no send audit entry, run done."""
    run_id = await _run("en_brass_runners")
    [approval] = await _approvals(run_id)
    await decide(approval.id, org_id="demo", decision="reject", note="price too low")
    async with session_scope() as db:
        run = await db.get(Run, run_id)
        sent = await db.scalar(select(AuditEntry).where(AuditEntry.action == "message.sent_simulated"))
    assert run.status == "done" and sent is None


async def test_hostile_message_is_blocked_by_policy(db_ready):
    """Bank-change attack: guard flags it, the policy engine blocks, nothing reaches the inbox."""
    run_id = await _run("hostile_bank_change")
    events = await _events(run_id)
    kinds = [e.kind for e in events]

    assert "blocked" in kinds and kinds[-1] == "done"
    blocked = next(e for e in events if e.kind == "blocked")
    assert blocked.payload["action_type"] == "update_bank_details"
    assert "P-BANK-001" in blocked.payload["rule_ids"]
    assert await _approvals(run_id) == []
    async with session_scope() as db:
        run = await db.get(Run, run_id)
        audit_actions = [a.action for a in (await db.scalars(select(AuditEntry).where(AuditEntry.run_id == run_id)))]
    assert run.status == "blocked"
    assert "policy.blocked" in audit_actions
    assert "AE07" not in run.raw_redacted                                  # the IBAN was masked


async def test_arabic_enquiry_gets_an_arabic_draft(db_ready):
    """The reply is drafted in the buyer's language."""
    run_id = await _run("ar_gift_boxes")
    [approval] = await _approvals(run_id)
    assert approval.payload["language"] == "ar"
    assert "درهم" in approval.payload["text"]
    async with session_scope() as db:
        run = await db.get(Run, run_id)
    assert [ln["quantity"] for ln in run.state["quote"]["lines"]] == [300, 150]


async def test_decisions_cannot_be_repeated_or_cross_organisations(db_ready):
    """An approval can be decided once, and only by its own organisation."""
    run_id = await _run("en_brass_runners")
    [approval] = await _approvals(run_id)
    with pytest.raises(ApprovalError, match="not found"):
        await decide(approval.id, org_id="other_org", decision="approve")
    await decide(approval.id, org_id="demo", decision="approve")
    with pytest.raises(ApprovalError, match="already approved"):
        await decide(approval.id, org_id="demo", decision="reject")
