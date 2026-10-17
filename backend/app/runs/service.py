"""
service.py — The life of a run, from "message received" to "approved and sent".

Why this file exists:
    The API layer stays thin; the actual steps live here so tests can call them directly:
      1. create_run   -> redact, store, emit run_started, start the graph in the background
      2. execute_run  -> run the LangGraph agents, save the final state
      3. decide       -> a human approves/edits/rejects a held action; governance-checked
                         "send" (simulator in Phase 1), audit entries, final `done` event

Nothing here sends directly: approved actions go through app/channels/outbox.py, the single door out
(simulator now; WhatsApp Cloud API in Phase 8), which also enforces the kill switch.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select

from app.agents.graph import build_graph
from app.agents.memory import remember_run, remember_sent
from app.agents.state import RunState
from app.channels.outbox import OutsideServiceWindow, kill_switch_on, send, service_window_open
from app.config import get_settings
from app.db.models import Approval, Run
from app.db.session import session_scope
from app.governance.audit import append_audit
from app.governance.rbac import Forbidden, check_approval, get_rbac
from app.llm.usage import tracking_run
from app.profile import load_org_profile, using_profile
from app.runs.emitter import RunEmitter, emit
from app.security.redactor import redact

# Keep references to background tasks so Python does not garbage-collect them mid-run.
_background: set[asyncio.Task] = set()


class ApprovalError(Exception):
    """Raised for invalid decisions (unknown id, other org, already decided)."""


async def create_run(*, message: str, channel: str = "form", org_id: str | None = None,
                     sample_id: str | None = None, background: bool = True, contact_key: str | None = None,
                     meta: dict | None = None, created_by: str | None = None) -> str:
    """Store a new run (redacted text only) and start its agents. Returns the run id.

    `created_by` is the user who started it (None for buyers, agents and channels); it powers the four-eyes rule.
    """
    settings = get_settings()
    org_id = org_id or settings.default_org_id
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    redaction = redact(message)                       # the raw message is never stored

    state = RunState(run_id=run_id, org_id=org_id, raw_message_redacted=redaction.text, channel=channel,
                     contact_key=contact_key)
    async with session_scope() as db:
        db.add(Run(id=run_id, org_id=org_id, status="new", channel=channel, sample_id=sample_id,
                   raw_redacted=redaction.text, state=state.model_dump(mode="json"), contact_key=contact_key,
                   created_by=created_by))
        await append_audit(db, org_id=org_id, actor="system", action="run.created", run_id=run_id,
                           details={"channel": channel, "sample_id": sample_id, "masked": redaction.counts,
                                    **(meta or {})})
    await emit(run_id, "system", "run_started",
               {"channel": channel, "sample_id": sample_id, "message_redacted": redaction.text, **(meta or {})})

    job = execute_run(run_id, redaction_counts=redaction.counts)
    if background:
        task = asyncio.create_task(job)
        _background.add(task)
        task.add_done_callback(_background.discard)
    else:
        await job
    return run_id


async def execute_run(run_id: str, redaction_counts: dict | None = None) -> RunState:
    """Run the agent graph for a stored run and save the final state."""
    settings = get_settings()
    async with session_scope() as db:
        run = await db.get(Run, run_id)
        state = RunState.model_validate(run.state)

    emitter = RunEmitter(run_id, delay_ms=settings.demo_step_delay_ms)
    config = {"configurable": {"emitter": emitter, "redaction_counts": redaction_counts or {}}}
    usage: dict = {}
    try:
        with using_profile(await load_org_profile(state.org_id)), tracking_run() as usage:
            result = await build_graph().ainvoke(state, config=config)     # the org's catalogue; tokens counted
        final = RunState.model_validate(result)
    except Exception as exc:  # no silent failure: record it, show it, escalate to a human
        await emit(run_id, "system", "error", {"message": f"{type(exc).__name__}: {exc}",
                                               "recovery": "escalated to a human"}, risk="high")
        final = state.model_copy(update={"status": "blocked"})

    async with session_scope() as db:
        run = await db.get(Run, run_id)
        run.state = {**final.model_dump(mode="json"), "usage": usage}
        run.status = final.status
    await remember_run(final.org_id, final.contact_key, final.model_dump(mode="json"))
    if final.status != "needs_approval":
        await emit(run_id, "system", "done", {"status": final.status, "impact": final.impact})
    return final


async def decide(approval_id: str, *, org_id: str, decision: Literal["approve", "reject"],
                 actor: str = "human:demo-user", note: str | None = None,
                 edited_text: str | None = None, role: str | None = None, user_id: str | None = None,
                 override_reason: str | None = None) -> Approval:
    """Apply a human decision to a held action and, when approved, perform it (simulated).

    RBAC (Phase 13): when `role` is given, the policy engine's risk decides the minimum role (rbac.yaml
    approval_by_risk: high risk -> Owner only); editing the draft needs `drafts.edit`. Four-eyes: the person who
    started a run cannot approve its HIGH-risk action, unless they give a written override reason (a solo exporter),
    which is audited. Raises Forbidden (403) or ApprovalError (404/409).
    """
    four_eyes_override = None
    async with session_scope() as db:
        approval = await db.get(Approval, approval_id)
        if approval is None or approval.org_id != org_id:
            raise ApprovalError("Approval not found")
        if approval.status != "pending":
            raise ApprovalError(f"Approval already {approval.status}")
        if role is not None:
            check_approval(role, approval.risk, approval.payload)
            if edited_text is not None and edited_text != approval.payload.get("text") and \
                    not get_rbac().can(role, "drafts.edit"):
                raise Forbidden("Your role cannot edit drafts: approve or reject the text as it is.")
            if decision == "approve" and approval.risk == "high" and user_id:
                started = await db.scalar(select(Run.created_by).where(Run.id == approval.run_id))
                if started == user_id:
                    reason = (override_reason or "").strip()
                    if len(reason) < 10:
                        raise Forbidden("Four-eyes rule: you started this enquiry, so another owner should approve "
                                        "this high-risk action. If you work alone, give a written reason "
                                        "(10+ characters) to override; it is recorded in the audit log.")
                    four_eyes_override = reason[:500]
        if decision == "approve" and await kill_switch_on(db, org_id):
            raise ApprovalError("Kill switch is on: nothing can be sent until it is turned off.")
        if decision == "approve" and approval.action_type.startswith("send_") and \
                not await service_window_open(db, approval.run_id):
            raise ApprovalError("More than 24 h since the buyer's last WhatsApp message: a template is required.")

        edited = edited_text is not None and edited_text != approval.payload.get("text")
        if edited:
            approval.payload = {**approval.payload, "text": edited_text, "edited_by_human": True}
        approval.status = "approved" if decision == "approve" else "rejected"
        approval.decided_by, approval.decided_at, approval.decision_note = actor, datetime.now(UTC), note

        await append_audit(db, org_id=org_id, actor=actor, action=f"approval.{approval.status}",
                           run_id=approval.run_id,
                           details={"approval_id": approval.id, "action_type": approval.action_type,
                                    "edited": edited, "note": note, "role": role, "risk": approval.risk,
                                    **({"four_eyes_override": four_eyes_override} if four_eyes_override else {})})
        sent = None
        if approval.status == "approved" and approval.action_type.startswith("send_"):
            try:
                sent = await send(db, org_id=org_id, run_id=approval.run_id, action_type=approval.action_type,
                                  payload=approval.payload, actor=actor, approval_id=approval.id)
            except OutsideServiceWindow as exc:          # window closed between the check and the send
                raise ApprovalError(str(exc)) from exc

        remaining = await db.scalar(
            select(Approval.id).where(Approval.run_id == approval.run_id, Approval.status == "pending",
                                      Approval.id != approval.id).limit(1)
        )
        run = await db.get(Run, approval.run_id)
        if remaining is None:
            any_approved = approval.status == "approved" or await db.scalar(
                select(Approval.id).where(Approval.run_id == run.id, Approval.status == "approved").limit(1)
            )
            run.status = "sent" if any_approved else "done"
            run.state = {**run.state, "status": run.status}

    await emit(approval.run_id, actor, "approval_decided",
               {"approval_id": approval.id, "decision": approval.status, "edited": edited, "note": note},
               risk=approval.risk)
    if sent:
        await emit(approval.run_id, "channel", "tool_result", {"tool": "send_message", **sent})
        if approval.action_type == "send_message" and run.contact_key:
            await remember_sent(org_id, run.contact_key)
    if remaining is None:
        await emit(approval.run_id, "system", "done", {"status": run.status, "impact": run.state.get("impact", {})})
    return approval
