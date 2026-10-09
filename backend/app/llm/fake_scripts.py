"""
fake_scripts.py — Deterministic answers for the offline `fake` model profile.

Why this file exists:
    With LLM_PROFILE=fake the whole demo must still work offline and give sensible output.
    These scripts imitate what a real model would answer for each `purpose`, using simple,
    predictable rules (regexes and templates). They read the same prompt a real model gets,
    so the agent code path is identical in fake, dev and prod.

    RFQ extraction offline is answered by the deterministic parser (app/tools/rfq_rules.py), which is also the
    grounding layer for real models. Drafting and classification use simple, clearly-labelled templates.
"""

import json
import re

from app.llm.router import LLMRequest


def _between(text: str, tag: str) -> str:
    """Return the text inside <tag>...</tag> (the agents wrap untrusted data in tags)."""
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1).strip() if match else text


def fake_rfq_extract(req: LLMRequest) -> dict:
    """Offline 'model': the deterministic bilingual parser (app/tools/rfq_rules.py) answers the extraction."""
    from app.tools.rfq_rules import parse_rfq  # local import: rfq_rules imports app.agents.state

    return parse_rfq(_between(req.prompt, "message")).model_dump()


def fake_outreach_draft(req: LLMRequest) -> str:
    """Fill a polite quotation-reply template in the requested language."""
    quote = json.loads(_between(req.prompt, "quote"))
    language = _between(req.prompt, "language")
    buyer = _between(req.prompt, "buyer")
    seller = _between(req.prompt, "seller")
    lines = quote["lines"]
    incoterm = quote.get("incoterm") or "FOB"
    validity = quote.get("validity_days", 15)
    charges = quote.get("charges", [])

    if language == "ar":
        body = "\n".join(
            f"- {ln['quantity']:g} × {ln['description']}: {ln['unit_price_aed']:.2f} درهم للوحدة "
            f"(الإجمالي {ln['total_aed']:.2f} درهم)"
            for ln in lines
        )
        extra = "\n".join(f"- {c['description']}: {c['total_aed']:.2f} درهم" for c in charges)
        return (
            f"السادة {buyer} المحترمين،\n"
            "شكراً لاستفساركم. يسعدنا تقديم عرض السعر التالي:\n"
            f"{body}\n" + (f"{extra}\n" if extra else "") +
            f"الإجمالي: {quote['total_aed']:.2f} درهم. الشروط: {incoterm}، والأسعار سارية لمدة {validity} يوماً.\n"
            f"مع خالص التحية،\n{seller}"
        )
    body = "\n".join(
        f"- {ln['quantity']:g} × {ln['description']}: AED {ln['unit_price_aed']:.2f}/unit "
        f"(total AED {ln['total_aed']:.2f})"
        for ln in lines
    )
    extra = "\n".join(f"- {c['description']}: AED {c['total_aed']:.2f}" for c in charges)
    return (
        f"Dear {buyer},\n"
        "Thank you for your enquiry. Please find our quotation below:\n"
        f"{body}\n" + (f"{extra}\n" if extra else "") +
        f"Total: AED {quote['total_aed']:.2f}. Terms: {incoterm}, prices valid for {validity} days.\n"
        f"Best regards,\n{seller}"
    )


def fake_injection_classify(req: LLMRequest) -> dict:
    """The fake model cannot judge intent: it always says 'not an attack' so offline numbers measure
    the deterministic rule layer only (no pretend second layer)."""
    return {"is_attack": False, "categories": [], "confidence": 0.0, "rationale": "fake model: no classification"}


# purpose -> script. The router's default FakeBackend loads these.
DEMO_SCRIPTS = {
    "rfq_extract": fake_rfq_extract,
    "outreach_draft": fake_outreach_draft,
    "injection_classify": fake_injection_classify,
}
