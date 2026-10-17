"""
nodes.py — The agents (LangGraph nodes) of the Phase 1 vertical slice.

Why this file exists:
    Phase 1 proves the whole path works end to end: enquiry -> agents -> governance ->
    approval inbox -> audit. Each node here is deliberately THIN. Nodes marked `stub: True`
    in their event payload return placeholder results and are replaced in later phases:
        quote  -> Phase 4 (real extraction, pricing rules, live FX)
        duty   -> Phase 5 (cited CEPA analysis)
        docs   -> Phase 5/6 (cited document pack + deterministic consistency checker)
        trust  -> Phase 6 (buyer trust signals incl. a UN sanctions-list name check)
    The guard and redactor are real but basic (v0); Phase 3 hardens them.

How a node works (beginner notes):
    LangGraph calls each node with the current RunState and a `config` dict. The node
    returns a dict of the state fields it changed; LangGraph merges that into the state.
    `agent_step` wraps every node so it always emits `agent_started` / `agent_finished`.
"""

import asyncio
import json
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from langchain_core.runnables import RunnableConfig

from app.agents.memory import recall
from app.agents.state import PendingAction, RunState
from app.agents.trade_agents import analyse_duty, build_doc_pack, check_draft_documents
from app.channels.outbox import KillSwitchEngaged, OutsideServiceWindow, kill_switch_on, send
from app.db.models import Approval, OrgSettings
from app.db.session import session_scope
from app.governance.audit import append_audit
from app.governance.policy_engine import PolicyContext, get_policy_engine
from app.llm.router import LLMRequest, get_router
from app.profile import get_business_profile
from app.runs.emitter import RunEmitter
from app.security.classifier import classify, extra_flags
from app.security.injection_guard import scan_rules
from app.tools.buyer_trust import assess as assess_buyer
from app.tools.buyer_trust import needs_review
from app.tools.fx import get_inr_to_aed
from app.tools.pricing import price_quote
from app.tools.rfq import extract_rfq


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
    memory = await recall(state.org_id, state.contact_key)
    return StepResult(
        updates={"status": "planning", "memory": memory},
        summary={
            "why": "Message received; personal data was masked before any model could see it."
                   + (f" Returning buyer: {memory['runs']} earlier enquiry(ies), {memory['quotes_sent']} quote(s) sent."
                      if memory else ""),
            "channel": state.channel,
            "masked": counts,
            "chars": len(state.raw_message_redacted),
            "returning_buyer": bool(memory),
        },
    )


@agent_step("guard")
async def guard(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Screen the untrusted message: deterministic rules + LLM classifier (findings are added together)."""
    rules = scan_rules(state.raw_message_redacted)
    await em.emit("guard", "tool_call", {"tool": "llm.injection_classify", "role": "fast"})
    verdict, error = await classify(state.raw_message_redacted)
    added = [f for f in extra_flags(verdict) if f not in rules.flags]
    await em.emit("guard", "tool_result", {
        "tool": "llm.injection_classify",
        "verdict": verdict.model_dump() if verdict else None,
        "added_flags": added,
        "fallback": "rules only" if error else None,
    }, risk="medium" if error else None)
    flags = sorted(set(rules.flags) | set(added))
    evidence = rules.evidence + [{"flag": f, "snippet": f"classifier: {verdict.rationale[:80]}"} for f in added]
    impact = dict(state.impact)
    impact["risks_caught"] = impact.get("risks_caught", 0) + len(flags)
    return StepResult(
        updates={"injection_flags": flags, "impact": impact},
        summary={
            "why": f"Flags found ({', '.join(flags)}): the message is treated as hostile data." if flags
            else "No injection or fraud patterns found (rules + classifier).",
            "flags": flags,
            "evidence": evidence,
            "layers": {"rules": rules.flags, "classifier": added, "classifier_error": error},
        },
        risk="high" if flags else "low",
    )


ACK_TEXT = {
    "en": "Thank you for your enquiry. We have received it and are preparing your quotation; we will reply shortly.",
    "ar": "شكراً لاستفساركم. تم استلامه ونقوم بإعداد عرض السعر، وسنرد عليكم قريباً.",
}


def acknowledgement(state: RunState) -> PendingAction:
    """A fixed-text receipt in the buyer's script: no prices, no dates, no commitments (autonomy L2)."""
    arabic = len(re.findall(r"[\u0600-\u06ff]", state.raw_message_redacted))
    language = "ar" if arabic > 0.3 * max(1, len(re.findall(r"[A-Za-z\u0600-\u06ff]", state.raw_message_redacted))) \
        else "en"
    return PendingAction(action_type="send_acknowledgement", title=f"Acknowledge receipt ({language.upper()})",
                         payload={"text": ACK_TEXT[language], "language": language, "channel": state.channel},
                         requested_by="supervisor", reason="Buyers expect an answer within minutes.",
                         evidence=["fixed text: no prices, no commitments"])


@agent_step("supervisor")
async def supervisor(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Decide which agents run. Phase 1: rule-based plan; Phase 9: LLM planner with re-planning."""
    pending: list[PendingAction] = []
    flags = set(state.injection_flags)
    evidence = [f"guard flag: {f}" for f in state.injection_flags]
    if flags & {"bank_change", "payment_status"}:
        # Simulate the worst case: a fooled agent proposes the dangerous action. Governance must block it.
        plan = ["governance"]
        if "bank_change" in flags:
            iban = re.search(r"\[(IBAN|ACCOUNT)_\d+\]", state.raw_message_redacted)
            pending.append(PendingAction(
                action_type="update_bank_details", title="Change buyer/beneficiary bank account",
                payload={"new_account": iban.group(0) if iban else "(unspecified)"}, requested_by="supervisor",
                reason="The inbound message asks to change bank or beneficiary details.", evidence=evidence))
        if "payment_status" in flags:
            pending.append(PendingAction(
                action_type="mark_payment_received", title="Mark an invoice as paid",
                payload={}, requested_by="supervisor",
                reason="The inbound message asks to mark or confirm a payment as received.", evidence=evidence))
        why = "Message asks to change bank details or payment status: routed straight to governance."
    else:
        plan = ["quote", "duty", "docs", "trust", "outreach", "governance"]
        why = ("Flagged message: drafting continues, but every outbound action will be HIGH risk for a human."
               if flags else
               "Standard enquiry: quote, duty check, documents, trust signals, reply draft, then governance.")
    if state.channel in ("whatsapp", "email"):    # only where a buyer is waiting for an answer
        pending.append(acknowledgement(state))   # L2: sent automatically only if every policy allows it
    await em.emit("supervisor", "plan", {"plan": plan, "why": why})
    return StepResult(
        updates={"plan": plan, "pending_actions": state.pending_actions + pending},
        summary={"why": why, "plan": plan, "stub_planner": True},
    )


def route_after_pricing(quote_doc: dict) -> tuple[str, str]:
    """Explainable re-planning after the quote: ask for details, skip CEPA, or continue normally."""
    if not quote_doc.get("lines"):
        return "trust", "No product and quantity could be read: check the buyer, then ask for the missing details."
    country = quote_doc.get("destination_country")
    if country not in (None, "unknown", "AE"):
        return "docs", (f"Destination {country} is outside the UAE: the India-UAE CEPA does not apply; "
                        "duty step skipped.")
    return "duty", "Standard path: CEPA duty check next."


@agent_step("quote")
async def quote(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Extract the RFQ (model grounded by rules), fetch FX with provenance, price goods + Incoterm charges."""
    await em.emit("quote", "tool_call", {"tool": "rfq.extract", "role": "worker"})
    rfq, reply, report = await extract_rfq(state.raw_message_redacted, channel=state.channel)
    await em.emit("quote", "tool_result", {"tool": "rfq.extract", "model": reply.model if reply else None,
                                           "source": report.source, "corrections": report.corrections,
                                           "items": len(rfq.items), "language": rfq.language},
                  risk="medium" if report.corrections or report.error else None)

    remembered = None
    if not rfq.incoterm and state.memory and state.memory.get("last_incoterm"):
        remembered = state.memory["last_incoterm"]                   # buyer's last order; flagged for review
        rfq = rfq.model_copy(update={"incoterm": remembered})
    profile = get_business_profile()
    fx = await get_inr_to_aed(profile.fx_stub_inr_to_aed)
    await em.emit("quote", "tool_call", {"tool": "fx", "rate": fx.rate, "source": fx.source,
                                         "rate_date": fx.rate_date, "stale": fx.stale})
    quote_doc = price_quote(rfq.items, profile, fx, rfq.incoterm, rfq.buyer_country)
    quote_doc["extraction"] = report.model_dump()
    await em.emit("quote", "tool_call", {"tool": "pricing", "lines": len(quote_doc["lines"]),
                                         "charges": len(quote_doc["charges"]), "flags": quote_doc["pricing_flags"]})
    if remembered:
        quote_doc["pricing_flags"] = [*quote_doc["pricing_flags"], "incoterm_from_memory"]
        quote_doc["incoterm_source"] = "buyer memory (last order)"
    flags = quote_doc["pricing_flags"]
    review = bool(flags) or not quote_doc["lines"]
    nxt, why_next = route_after_pricing(quote_doc)
    if nxt != "duty":                                   # re-plan, shown on the timeline
        await em.emit("supervisor", "plan", {"replan": True, "next": nxt, "why": why_next})
    return StepResult(
        updates={"rfq": rfq, "quote": quote_doc,
                 "confidence": {**state.confidence, "quote": 0.5 if review else 0.85}},
        summary={"why": (f"Priced {len(quote_doc['lines'])} line(s) + {len(quote_doc['charges'])} "
                         f"{quote_doc['incoterm']} charge(s); total AED {quote_doc['total_aed']:,.2f}"
                         + (f"; needs review: {', '.join(flags)}." if flags else ".")),
                 "total_aed": quote_doc["total_aed"], "total_inr": quote_doc["total_inr"],
                 "incoterm": quote_doc["incoterm"], "fx_source": fx.source, "flags": flags},
        risk="medium" if review else "low",
    )


@agent_step("duty")
async def duty(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """CEPA Duty agent: HS candidates, cited MFN duty and Annex 3B rule, evidence needed, 'up to' saving."""
    if not state.rfq or not state.quote or not state.quote.get("lines"):
        return StepResult(updates={"duty": {"status": "no_lines", "needs_human_check": True}},
                          summary={"why": "No priced lines to analyse.", "needs_human_check": True}, risk="medium")
    await em.emit("duty", "tool_call", {"tool": "kb.classify_hs+rules", "lines": len(state.quote["lines"])})
    analysis = await analyse_duty(state.rfq, state.quote)
    for ln in analysis.get("lines", []):
        await em.emit("duty", "retrieval_attempt", {
            "line": ln["description"], "hs": [c["best_line"] for c in ln.get("hs_candidates", [])][:3],
            "confidence": ln.get("hs_confidence"), "rule": (ln.get("rule") or {}).get("text"),
            "removed_claims": len(ln.get("removed_claims", []))})
    impact = dict(state.impact)
    if analysis.get("max_potential_saving_aed") is not None:
        impact["duty_saving_upto_aed"] = analysis["max_potential_saving_aed"]
    citations = list(analysis.get("citations", {}).values())
    if analysis["status"] != "analysed":
        why = analysis["note"]
    else:
        rules = sorted({(ln.get("rule") or {}).get("text") for ln in analysis["lines"] if ln.get("rule")})
        why = (f"CEPA rules {', '.join(rules) or 'not found'}; up to AED {analysis['max_potential_saving_aed']:,.2f} "
               "MFN duty could be saved if the preferential rate is 0% (rate needs human check).")
    return StepResult(
        updates={"duty": analysis, "impact": impact, "citations": state.citations + citations},
        summary={"why": why, "needs_human_check": True, "citations": len(citations),
                 "saving_upto_aed": analysis.get("max_potential_saving_aed")},
        risk="medium",
    )


@agent_step("docs")
async def docs(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Docs agent: cited document pack, a draft document set, and the deterministic consistency check."""
    pack = await asyncio.to_thread(build_doc_pack, state.duty or {})
    findings: list[dict] = []
    if state.quote and state.quote.get("lines"):
        await em.emit("docs", "tool_call", {"tool": "doc_checker.check_document_set", "stage": "draft"})
        draft, findings = await asyncio.to_thread(check_draft_documents, state.rfq, state.quote, state.duty or {})
        pack["draft"] = draft
        await em.emit("docs", "tool_result", {"tool": "doc_checker.check_document_set", "findings": len(findings),
                                              "types": [f["type"] for f in findings]},
                      risk="high" if any(f["severity"] == "high" for f in findings) else "low")
    cited = sum(1 for d in pack.get("documents", []) if d.get("citation"))
    impact = dict(state.impact)
    impact["risks_caught"] = impact.get("risks_caught", 0) + len(findings)
    why = (f"Document pack: {len(pack.get('documents', []))} documents, {cited} with cited requirements. "
           + (f"{len(findings)} consistency issue(s) found before anything is issued."
              if findings else "Draft invoice, packing list and certificate are consistent."))
    high = any(f["severity"] == "high" for f in findings)
    return StepResult(updates={"docs": pack, "doc_issues": findings, "impact": impact},
                      summary={"why": why, "documents": len(pack.get("documents", [])), "issues": len(findings),
                               "needs_human_check": True},
                      risk="high" if high else ("medium" if findings or pack.get("status") != "prepared" else "low"))


@agent_step("trust")
async def trust(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Buyer trust SIGNALS for human review (never a verdict): email domain, payment and bank-change requests,
    pressure, licence, destination, order size and a UN sanctions-list name check."""
    await em.emit("trust", "tool_call", {"tool": "buyer_trust.assess"})
    signals = await asyncio.to_thread(
        assess_buyer, state.raw_message_redacted,
        buyer_name=state.rfq.buyer_name if state.rfq else "", buyer_country=(state.rfq.buyer_country or "")
        if state.rfq else "", quote_total_aed=(state.quote or {}).get("total_aed"),
        injection_flags=state.injection_flags)
    memory = state.memory or {}
    if memory:
        signals.append({"signal": "returning_buyer", "risk": "positive",
                        "evidence": f"{memory['runs']} earlier enquiry(ies), {memory['quotes_sent']} quote(s) sent",
                        "why": "A known buyer; history is kept as facts only (no message text)."})
        if memory.get("risk_signals"):
            signals.append({"signal": "earlier_high_risk_signal", "risk": "medium",
                            "evidence": ", ".join(memory["risk_signals"]),
                            "why": "This buyer triggered a high-risk signal before; check the history."})
    impact = dict(state.impact)
    impact["risks_caught"] = impact.get("risks_caught", 0) + sum(1 for s in signals if s["risk"] in ("medium", "high"))
    review = needs_review(signals)
    risk = "high" if any(s["risk"] == "high" for s in signals) else ("medium" if review else "low")
    return StepResult(
        updates={"buyer_signals": signals, "impact": impact},
        summary={"why": ("Review the buyer before quoting on credit or shipping." if review else
                         "No warning signals; signals are for human review, not verdicts."),
                 "signals": signals, "needs_review": review},
        risk=risk,
    )


def quote_for_prompt(quote: dict) -> dict:
    """Only what the reply drafter needs. Excludes timestamps and internal reports, so prompts stay small
    and identical for identical quotes (which also keeps offline replay deterministic)."""
    keep_line = ("description", "quantity", "unit", "unit_price_aed", "total_aed")
    return {
        "lines": [{k: ln[k] for k in keep_line} for ln in quote["lines"]],
        "charges": [{"description": c["description"], "total_aed": c["total_aed"]} for c in quote.get("charges", [])],
        "incoterm": quote.get("incoterm"), "total_aed": quote["total_aed"],
        "validity_days": quote.get("validity_days", 15),
    }


CLARIFY_TEXT = {
    "en": "Thank you for your enquiry. To prepare an accurate quotation, could you please confirm: the products and "
          "quantities, the delivery port or city, the Incoterm (for example CIF Jebel Ali) and the date you need them?",
    "ar": "شكراً لاستفساركم. لإعداد عرض سعر دقيق، نرجو تأكيد: المنتجات والكميات، وميناء أو مدينة التسليم، وشرط "
          "التسليم (مثل CIF جبل علي)، والتاريخ المطلوب.",
}


@agent_step("outreach")
async def outreach(state: RunState, em: RunEmitter, config: RunnableConfig) -> StepResult:
    """Draft the reply in the buyer's language via the LLM router; queue it for approval."""
    if not state.rfq:
        return StepResult(updates={}, summary={"why": "No enquiry could be read; nothing drafted."}, risk="medium")
    if not state.quote or not state.quote.get("lines"):
        language = state.rfq.language if state.rfq.language in ("en", "ar") else "en"
        draft = {"language": language, "channel": state.channel, "text": CLARIFY_TEXT[language],
                 "kind": "clarification"}
        action = PendingAction(action_type="send_message", title=f"Ask buyer for missing details ({language.upper()})",
                               payload=draft, requested_by="outreach",
                               reason="The enquiry has no product and quantity Jisr could price.",
                               evidence=["0 priced lines"])
        return StepResult(
            updates={"drafts": state.drafts + [draft], "pending_actions": state.pending_actions + [action]},
            summary={"why": "Missing details: drafted a short question to the buyer instead of guessing a quote.",
                     "language": language, "clarification": True},
            risk="medium",
        )
    language = state.rfq.language if state.rfq.language in ("en", "ar") else "en"
    seller = get_business_profile().seller_name
    await em.emit("outreach", "tool_call", {"tool": "llm.outreach_draft", "role": "worker", "language": language})
    reply = await get_router().complete(LLMRequest(
        role="worker",
        purpose="outreach_draft",
        system="Write a short, polite quotation reply. Use only the figures given. Do not add facts.",
        prompt=(f"<language>{language}</language><buyer>{state.rfq.buyer_name}</buyer><seller>{seller}</seller>"
                f"<quote>{json.dumps(quote_for_prompt(state.quote), ensure_ascii=False)}</quote>"),
    ))
    draft = {"language": language, "channel": state.channel, "text": reply.text, "model": reply.model,
             "pricing_flags": state.quote.get("pricing_flags", []),
             "min_effective_margin_pct": state.quote.get("min_effective_margin_pct"),
             "total_aed": state.quote["total_aed"], "incoterm": state.quote.get("incoterm")}
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
    events: list[tuple[str, dict, str]] = []          # (kind, payload, risk) to emit after commit
    held, blocked, done_alone = 0, 0, 0
    async with session_scope() as db:
        org_settings = await db.get(OrgSettings, state.org_id)
        ctx = PolicyContext(injection_flags=state.injection_flags,
                            buyer_signals=[s["signal"] for s in state.buyer_signals],
                            kill_switch=await kill_switch_on(db, state.org_id),
                            autonomy_overrides=(org_settings.autonomy or {}) if org_settings else {})
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
            elif decision.effect == "allow":
                # Allowed by every policy AND by the action's autonomy level: Jisr does it on its own (audited).
                try:
                    sent = await send(db, org_id=state.org_id, run_id=state.run_id, action_type=action.action_type,
                                      payload=action.payload, actor=action.requested_by, autonomous=True)
                    done_alone += 1
                    events.append(("tool_result", {"tool": action.action_type, "autonomous": True,
                                                   "title": action.title, **sent}, "low"))
                except (KillSwitchEngaged, OutsideServiceWindow):
                    blocked += 1
                    events.append(("blocked", {"action_type": action.action_type, "title": action.title,
                                               "rule_ids": ["P-KILL-001"], "reasons": ["Kill switch is on."]}, "high"))
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
        summary={"why": f"{held} action(s) held for approval, {blocked} blocked by policy, "
                        f"{done_alone} done automatically within policy.",
                 "held": held, "blocked": blocked, "autonomous": done_alone},
        risk="high" if blocked else ("medium" if held else "low"),
    )
