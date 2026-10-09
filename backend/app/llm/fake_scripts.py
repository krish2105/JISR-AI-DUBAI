"""
fake_scripts.py — Deterministic answers for the offline `fake` model profile.

Why this file exists:
    With LLM_PROFILE=fake the whole demo must still work offline and give sensible output.
    These scripts imitate what a real model would answer for each `purpose`, using simple,
    predictable rules (regexes and templates). They read the same prompt a real model gets,
    so the agent code path is identical in fake, dev and prod.

    These are NOT the product's intelligence: Phase 4 replaces RFQ extraction with a real
    model and measures it (F1 >= 0.9) against a labelled set.
"""

import json
import re

from app.llm.router import LLMRequest

ARABIC_CHAR = re.compile(r"[؀-ۿ]")
LATIN_CHAR = re.compile(r"[A-Za-z]")
MONTHS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}
INCOTERM_RE = re.compile(r"\b(EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DAP|DPU|DDP)\b")
UAE_PLACES = ("dubai", "jebel ali", "abu dhabi", "sharjah", "ajman", "دبي", "جبل علي", "أبوظبي", "الشارقة")

# English: "500 pcs brass diya lamps" / "200 hand-block printed cotton table runners"
EN_ITEM_RE = re.compile(
    r"(?<![\w.])(\d[\d,]*)\s*"                    # quantity, e.g. 500 or 1,200
    r"(pcs|pieces|units|sets|nos)?\.?\s+"           # optional unit
    r"(?:of\s+)?([A-Za-z][A-Za-z \-]+?)"             # the product description
    r"(?=\s*(?:\(|,|\.|\band\b|$))"                # ...ends at "(", ",", ".", "and" or end
)
# Arabic: "300 صندوق هدايا خشبي منقوش و 150 وشاح باشمينا"
AR_ITEM_RE = re.compile(r"(\d+)\s+([؀-ۿ][؀-ۿ ]+?)(?=\s+و\s+\d|،|\.|\(|\n|$)")


def _between(text: str, tag: str) -> str:
    """Return the text inside <tag>...</tag> (the agents wrap untrusted data in tags)."""
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1).strip() if match else text


def detect_language(text: str) -> str:
    """'ar' if mostly Arabic letters, 'en' if mostly Latin, else 'mixed'."""
    ar, la = len(ARABIC_CHAR.findall(text)), len(LATIN_CHAR.findall(text))
    if ar and ar >= 3 * la:
        return "ar"
    if la and la >= 3 * ar:
        return "en"
    return "mixed"


def fake_rfq_extract(req: LLMRequest) -> dict:
    """Pull buyer, items, Incoterm and deadline out of the message with simple patterns."""
    message = _between(req.prompt, "message")
    items = []
    for qty, unit, desc in EN_ITEM_RE.findall(message):
        desc = desc.strip()
        if desc.split()[0].lower()[:3] in MONTHS:          # "15 Dec" is a date, not an item
            continue
        items.append({"description": desc, "quantity": float(qty.replace(",", "")), "unit": unit or "pcs"})
    for qty, desc in AR_ITEM_RE.findall(message):
        items.append({"description": desc.strip(), "quantity": float(qty), "unit": "pcs"})

    signature = re.search(r"^[—-]\s*(.+)$", message, re.MULTILINE)
    deadline = re.search(r"(?:before|by)\s+(\d{1,2}\s+[A-Za-z]{3,9}|end of [A-Za-z]+)|قبل\s+(نهاية\s+\S+)", message)
    incoterm = INCOTERM_RE.search(message)
    return {
        "buyer_name": signature.group(1).strip() if signature else "Unknown buyer",
        "buyer_country": "AE" if any(p in message.lower() for p in UAE_PLACES) else "unknown",
        "items": items,
        "incoterm": incoterm.group(1) if incoterm else None,
        "deadline": next((g for g in deadline.groups() if g), None) if deadline else None,
        "language": detect_language(message),
        "channel": "whatsapp",
    }


def fake_outreach_draft(req: LLMRequest) -> str:
    """Fill a polite quotation-reply template in the requested language."""
    quote = json.loads(_between(req.prompt, "quote"))
    language = _between(req.prompt, "language")
    buyer = _between(req.prompt, "buyer")
    seller = _between(req.prompt, "seller")
    lines = quote["lines"]
    incoterm = quote.get("incoterm") or "FOB"
    validity = quote.get("validity_days", 15)

    if language == "ar":
        body = "\n".join(
            f"- {ln['quantity']:g} × {ln['description']}: {ln['unit_price_aed']:.2f} درهم للوحدة "
            f"(الإجمالي {ln['total_aed']:.2f} درهم)"
            for ln in lines
        )
        return (
            f"السادة {buyer} المحترمين،\n"
            "شكراً لاستفساركم. يسعدنا تقديم عرض السعر التالي:\n"
            f"{body}\n"
            f"الإجمالي: {quote['total_aed']:.2f} درهم. الشروط: {incoterm}، والأسعار سارية لمدة {validity} يوماً.\n"
            f"مع خالص التحية،\n{seller}"
        )
    body = "\n".join(
        f"- {ln['quantity']:g} × {ln['description']}: AED {ln['unit_price_aed']:.2f}/unit "
        f"(total AED {ln['total_aed']:.2f})"
        for ln in lines
    )
    return (
        f"Dear {buyer},\n"
        "Thank you for your enquiry. Please find our quotation below:\n"
        f"{body}\n"
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
