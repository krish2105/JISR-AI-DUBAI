"""
nodes.py — The agents (LangGraph nodes) of the Phase 1 vertical slice.

Why this file exists:
    Phase 1 proves the whole path works end to end: enquiry -> agents -> governance ->
    approval inbox -> audit. Each node here is deliberately THIN. Nodes marked `stub: True`
    in their event payload return placeholder results and are replaced in later phases:
        quote  -> Phase 4 (real extraction, pricing rules, live FX)
        duty   -> Phase 5 (cited CEPA analysis)
        docs   -> Phase 5/6 (document pack + consistency checker)
        trust  -> Phase 6 (sanctions-list signals)
    The guard and redactor are real but basic (v0); Phase 3 hardens them.

How a node works (beginner notes):
    LangGraph calls each node with the current RunState and a `config` dict. The node
    returns a dict of the state fields it changed; LangGraph merges that into the state.
    `agent_step` wraps every node so it always emits `agent_started` / `agent_finished`.
"""

import json
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from langchain_core.runnables import RunnableConfig

from app.agents.state import PendingAction, RunState
from app.db.models import Approval
from app.db.session import session_scope
from app.governance.audit import append_audit
from app.governance.policy_engine import PolicyContext, get_policy_engine
from app.llm.router import LLMRequest, get_router
from app.profile import get_business_profile
from app.runs.emitter import RunEmitter
from app.security.injection_guard import scan
from app.tools.pricing import price_lines
from app.tools.rfq import extract_rfq

FREE_MAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "proton.me"}


@dataclass
class StepResult:
    """What a node body returns: state updates, a short summary for the timeline, a risk level."""

    updates: dict
    summary: dict
    risk: str | None = None
    extra_events: list[dict] = field(default_factory=list)


NodeBody = Callable[[RunState, RunEmitter, RunnableConfig], Awaitable[StepResult]]


def agent_step(name: str) -> Callable[[NodeBody], Callable]:
    """Decorator: wrap a node body with started/finished events and demo pacing."""

    def decorate(body: NodeBody) -> Callable:
        # The wrapper's parameters are literally named (state, config): LangGraph looks for
        # a parameter called `config` to decide whether to pass the run configuration.
        async def node(state: RunState, config: RunnableConfig) -> dict:
            emitter: RunEmitter = config["configurable"]["emitter"]
            await emitter.emit(name, "agent_started")
            await emitter.pace()
            result = await body(state, emitter, config)
            await emitter.emit(name, "agent_finished", result.summary, risk=result.risk)
            return result.updates

        node.__name__ = name
        return node

    return decorate


# --------------------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------------------


@agent_step("ingest")
async def ingest(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Receive the message. Redaction already happened before the run was stored."""
    counts = config["configurable"].get("redaction_counts", {})
    return StepResult(
        updates={"status": "planning"},
        summary={
            "why": "Message received; personal data was masked before any model could see it.",
            "channel": state.channel,
            "masked": counts,
            "chars": len(state.raw_message_redacted),
        },
    )


@agent_step("guard")
async def guard(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Screen the untrusted message for injection and fraud patterns (v0 patterns)."""
    flags = scan(state.raw_message_redacted)
    impact = dict(state.impact)
    impact["risks_caught"] = impact.get("risks_caught", 0) + len(flags)
    return StepResult(
        updates={"injection_flags": flags, "impact": impact},
        summary={
            "why": "Flags found: the message is treated as hostile data." if flags
            else "No injection or fraud patterns found.",
            "flags": flags,
        },
        risk="high" if flags else "low",
    )


@agent_step("supervisor")
async def supervisor(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Decide which agents run. Phase 1: rule-based plan; Phase 9: LLM planner with re-planning."""
    pending: list[PendingAction] = []
    if "bank_change" in state.injection_flags:
        # Simulate the worst case: a fooled agent proposes the change. Governance must block it.
        plan = ["governance"]
        iban = re.search(r"\[IBAN_\d+\]", state.raw_message_redacted)
        pending.append(PendingAction(
            action_type="update_bank_details",
            title="Change buyer/beneficiary bank account",
            payload={"new_account": iban.group(0) if iban else "(unspecified)"},
            requested_by="supervisor",
            reason="The inbound message asks to change bank details and confirm a payment.",
            evidence=[f"guard flag: {f}" for f in state.injection_flags],
        ))
        why = "Message asks to change bank details: routed straight to governance."
    else:
        plan = ["quote", "duty", "docs", "trust", "outreach", "governance"]
        why = "Standard enquiry: quote, duty check, documents, trust signals, reply draft, then governance."
    await em.emit("supervisor", "plan", {"plan": plan, "why": why})
    return StepResult(
        updates={"plan": plan, "pending_actions": state.pending_actions + pending},
        summary={"why": why, "plan": plan, "stub_planner": True},
    )


@agent_step("quote")
async def quote(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Extract the RFQ with the LLM router, then price each line (stub pricing until Phase 4)."""
    await em.emit("quote", "tool_call", {"tool": "llm.rfq_extract", "role": "worker"})
    rfq, reply = await extract_rfq(state.raw_message_redacted)
    await em.emit("quote", "tool_result", {"tool": "llm.rfq_extract", "model": reply.model,
                                           "items": len(rfq.items), "language": rfq.language})

    profile = get_business_profile()
    quote_doc = price_lines(rfq.items, profile, incoterm=rfq.incoterm)
    await em.emit("quote", "tool_call", {"tool": "pricing", "lines": len(quote_doc["lines"])})
    lines = quote_doc["lines"]
    unmatched = sum(1 for ln in lines if not ln["catalogue_match"])
    return StepResult(
        updates={"rfq": rfq, "quote": quote_doc,
                 "confidence": {**state.confidence, "quote": 0.5 if unmatched or not lines else 0.8}},
        summary={"why": f"Priced {len(lines)} line(s) at {profile.default_margin_pct}% margin.",
                 "total_aed": quote_doc["total_aed"], "total_inr": quote_doc["total_inr"],
                 "unmatched_lines": unmatched, "stub": True},
        risk="medium" if unmatched or not lines else "low",
    )


@agent_step("duty")
async def duty(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Placeholder: the cited CEPA Duty Optimiser arrives in Phase 5. It never guesses rates."""
    analysis = {
        "status": "not_implemented",
        "needs_human_check": True,
        "indicative_saving_aed": None,
        "note": "CEPA analysis with official citations arrives in Phase 5. No rate is guessed.",
    }
    return StepResult(updates={"duty": analysis},
                      summary={"why": analysis["note"], "stub": True, "needs_human_check": True})


@agent_step("docs")
async def docs(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Placeholder document pack: lists the documents; HS codes are unverified hints only."""
    profile = get_business_profile()
    hints = []
    for item in (state.rfq.items if state.rfq else []):
        entry = profile.match(item.description)
        hints.append({"item": item.description, "hs_hint": entry.hs_hint if entry else None,
                      "verified": False})
    pack = {
        "documents": ["Commercial invoice", "Packing list", "Certificate of origin (CEPA) checklist",
                      "Import requirements checklist (Dubai Customs)"],
        "hs_hints": hints,
        "note": "HS codes are unverified catalogue hints until cited classification (Phase 5).",
    }
    return StepResult(updates={"docs": pack, "doc_issues": []},
                      summary={"why": "Document list prepared; consistency checks arrive in Phase 6.",
                               "documents": len(pack["documents"]), "stub": True})


@agent_step("trust")
async def trust(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Buyer trust SIGNALS for human review (never a verdict). Phase 6 adds sanctions-list matching."""
    signals = []
    for domain in re.findall(r"\[EMAIL_\d+\]@([\w.-]+)", state.raw_message_redacted):
        if domain.lower() in FREE_MAIL_DOMAINS:
            signals.append({"signal": "free_mail_domain", "evidence": domain, "risk": "medium"})
    if not re.search(r"\[EMAIL_\d+\]@", state.raw_message_redacted):
        signals.append({"signal": "no_business_email", "evidence": "no email address given", "risk": "low"})
    impact = dict(state.impact)
    impact["risks_caught"] = impact.get("risks_caught", 0) + sum(1 for s in signals if s["risk"] != "low")
    return StepResult(
        updates={"buyer_signals": signals, "impact": impact},
        summary={"why": "Signals are for human review, not verdicts.", "signals": signals, "stub": True},
        risk="medium" if any(s["risk"] == "medium" for s in signals) else "low",
    )


@agent_step("outreach")
async def outreach(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Draft the reply in the buyer's language via the LLM router; queue it for approval."""
    if not state.quote or not state.rfq:
        return StepResult(updates={}, summary={"why": "No quote to send; nothing drafted."}, risk="medium")
    language = state.rfq.language if state.rfq.language in ("en", "ar") else "en"
    seller = get_business_profile().seller_name
    await em.emit("outreach", "tool_call", {"tool": "llm.outreach_draft", "role": "worker", "language": language})
    reply = await get_router().complete(LLMRequest(
        role="worker",
        purpose="outreach_draft",
        system="Write a short, polite quotation reply. Use only the figures given. Do not add facts.",
        prompt=(f"<language>{language}</language><buyer>{state.rfq.buyer_name}</buyer>"
                f"<seller>{seller}</seller><quote>{json.dumps(state.quote, ensure_ascii=False)}</quote>"),
    ))
    draft = {"language": language, "channel": state.channel, "text": reply.text, "model": reply.model}
    action = PendingAction(
        action_type="send_message",
        title=f"Send quotation reply ({language.upper()}, {state.channel})",
        payload=draft,
        requested_by="outreach",
        reason="Reply to the buyer's enquiry with the quotation.",
        evidence=[f"quote total AED {state.quote['total_aed']:.2f}"],
    )
    return StepResult(
        updates={"drafts": state.drafts + [draft], "pending_actions": state.pending_actions + [action]},
        summary={"why": f"Drafted a reply in {language.upper()} (buyer's language); queued for approval.",
                 "language": language, "model": reply.model},
    )


@agent_step("governance")
async def governance(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Run every pending action through the deterministic policy engine.

    Order matters: we first commit approvals and audit entries in one transaction, and only
    then emit events. Emitting while a write transaction is open would make the event writer
    wait for our own lock (SQLite allows one writer at a time).
    """
    engine = get_policy_engine()
    ctx = PolicyContext(injection_flags=state.injection_flags)
    events: list[tuple[str, dict, str]] = []          # (kind, payload, risk) to emit after commit
    held, blocked = 0, 0
    async with session_scope() as db:
        for action in state.pending_actions:
            decision = engine.evaluate(action, ctx)
            events.append(("policy_decision",
                           {"action_type": action.action_type, "title": action.title, **decision.model_dump()},
                           decision.risk))
            if decision.effect == "block":
                blocked += 1
                await append_audit(db, org_id=state.org_id, actor="governance", action="policy.blocked",
                                   run_id=state.run_id,
                                   details={"action_type": action.action_type, "rule_ids": decision.rule_ids,
                                            "requested_by": action.requested_by})
                events.append(("blocked", {"action_type": action.action_type, "title": action.title,
                                           "rule_ids": decision.rule_ids, "reasons": decision.reasons}, "high"))
            elif decision.effect == "require_approval":
                held += 1
                approval = Approval(
                    id=f"apr_{uuid.uuid4().hex[:12]}", run_id=state.run_id, org_id=state.org_id,
                    action_type=action.action_type, title=action.title, payload=action.payload,
                    reason=action.reason, evidence=action.evidence, risk=decision.risk,
                    rule_id=",".join(decision.rule_ids),
                )
                db.add(approval)
                await append_audit(db, org_id=state.org_id, actor="governance", action="approval.requested",
                                   run_id=state.run_id,
                                   details={"approval_id": approval.id, "action_type": action.action_type,
                                            "rule_ids": decision.rule_ids})
                events.append(("approval_needed", {"approval_id": approval.id, "title": action.title,
                                                   "rule_ids": decision.rule_ids}, decision.risk))
    for kind, payload, risk in events:                # transaction committed: now tell the world
        await em.emit("governance", kind, payload, risk=risk)

    status = "needs_approval" if held else ("blocked" if blocked else "done")
    return StepResult(
        updates={"status": status},
        summary={"why": f"{held} action(s) held for approval, {blocked} blocked by policy.",
                 "held": held, "blocked": blocked},
        risk="high" if blocked else ("medium" if held else "low"),
    )
