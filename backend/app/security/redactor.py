"""
redactor.py — Mask personal and sensitive data before any model sees a message (v1).

Why this file exists:
    Rule: models only ever see redacted text. Personal and sensitive values are replaced by consistent
    tokens such as [PHONE_1]; the same value always gets the same token within one message, so agents can
    still reason ("the buyer gave one phone number").

    Masked (v1): EMAIL (personal part only; the business domain is kept as a trust signal), IBAN, CARD
    (Luhn-checked), EID (Emirates ID), TRN (UAE tax number), GSTIN and PAN (India tax IDs), ACCOUNT
    (bank account numbers after "account no", "A/C", "acct"), PHONE (incl. Arabic-Indic digits and
    brackets), POBOX, PERSON (names after an honorific such as Mr / Ms / Dr / السيد / السيدة).

    Kept on purpose: company names, quantities, HS codes, Incoterms, dates, invoice numbers.

    The token -> original mapping is returned in memory only (`mapping`, excluded from serialisation) so a
    later, human-approved outbound message can be personalised. It is never stored or logged.
"""

import re

from pydantic import BaseModel, Field

DIGIT = r"[0-9٠-٩]"                                  # Western or Arabic-Indic digit
SEP = r"[\s\-.()]"

EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,4})?\b")
CARD_RE = re.compile(r"(?<![\w])(?:\d[ -]?){12,18}\d(?![\w])")
EID_RE = re.compile(r"\b784-?\d{4}-?\d{7}-?\d\b")
TRN_RE = re.compile(r"\b100\d{12}\b")
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
ACCOUNT_RE = re.compile(r"(?i)\b(account\s*(?:no\.?|number|#)?|a/c\s*(?:no\.?)?|acct\.?\s*(?:no\.?)?)\s*[:\-]?\s*"
                        r"(\d[\d\s-]{4,22}\d)")
PHONE_RE = re.compile(rf"(?<![\w])\+?{DIGIT}(?:{SEP}{{0,2}}{DIGIT}){{8,14}}(?![\w])")
POBOX_RE = re.compile(r"(?i)(p\.?\s?o\.?\s*box|post box|ص\.?\s?ب\.?|صندوق بريد)\s*:?\s*(" + DIGIT + r"{3,7})")
PERSON_RE = re.compile(
    r"\b(Mr\.?|Mrs\.?|Ms\.?|Miss|Dr\.?|Sheikh|Eng\.?)\s+([A-Z][a-z]+(?:\s+(?:Al\s+|al-|bin\s+)?[A-Z][a-z]+){0,2})"
    r"|(السيد|السيدة|الأستاذ|الأستاذة|الدكتور|الدكتورة|المهندس)\s+([ء-ي]+(?:\s+[ء-ي]+)?)"
)
# A long digit run right after "HS code" / "tariff" is a tariff code, not a phone number.
HS_CONTEXT = re.compile(r"(?i)\b(hs|h\.s\.|tariff|hscode|commodity)\s*(code)?\s*(no\.?)?\s*[:#]?\s*$")


def luhn_ok(number: str) -> bool:
    """True if the digits pass the Luhn checksum used by payment cards."""
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        total += sum(divmod(d * 2, 10)) if i % 2 == 1 else d
    return total % 10 == 0


class RedactionResult(BaseModel):
    """Redacted text, counts per category, and an in-memory-only token map."""

    text: str
    counts: dict[str, int] = Field(default_factory=dict)
    mapping: dict[str, str] = Field(default_factory=dict, exclude=True, repr=False)


def redact(text: str) -> RedactionResult:
    """Replace sensitive values with consistent tokens (most specific patterns first)."""
    seen: dict[tuple[str, str], str] = {}
    counts: dict[str, int] = {}
    mapping: dict[str, str] = {}

    def token_for(category: str, value: str) -> str:
        """Existing token for this value, or the next one for the category."""
        key = (category, re.sub(r"[\s\-.()]", "", value))
        if key not in seen:
            counts[category] = counts.get(category, 0) + 1
            seen[key] = f"[{category}_{counts[category]}]"
            mapping[seen[key]] = value
        return seen[key]

    out = EMAIL_RE.sub(lambda m: f"{token_for('EMAIL', m.group(1))}@{m.group(2)}", text)
    out = IBAN_RE.sub(lambda m: token_for("IBAN", m.group(0)), out)
    out = EID_RE.sub(lambda m: token_for("EID", m.group(0)), out)
    out = CARD_RE.sub(lambda m: token_for("CARD", m.group(0)) if luhn_ok(m.group(0)) else m.group(0), out)
    out = TRN_RE.sub(lambda m: token_for("TRN", m.group(0)), out)
    out = GSTIN_RE.sub(lambda m: token_for("GSTIN", m.group(0)), out)
    out = PAN_RE.sub(lambda m: token_for("PAN", m.group(0)), out)
    out = ACCOUNT_RE.sub(lambda m: f"{m.group(1)} {token_for('ACCOUNT', m.group(2))}", out)
    out = POBOX_RE.sub(lambda m: f"{m.group(1)} {token_for('POBOX', m.group(2))}", out)

    before_phones = out

    def phone(m: re.Match) -> str:
        """Mask a phone number, except a long code that directly follows 'HS code' / 'tariff'."""
        if HS_CONTEXT.search(before_phones[: m.start()][-30:]):
            return m.group(0)
        return token_for("PHONE", m.group(0))

    out = PHONE_RE.sub(phone, out)
    out = PERSON_RE.sub(lambda m: (f"{m.group(1)} {token_for('PERSON', m.group(2))}" if m.group(1)
                                   else f"{m.group(3)} {token_for('PERSON', m.group(4))}"), out)
    return RedactionResult(text=out, counts=counts, mapping=mapping)


# Types precise enough to act as a last-line tripwire on everything sent to a model (see router).
TRIPWIRE = {"EMAIL": EMAIL_RE, "IBAN": IBAN_RE, "EID": EID_RE, "TRN": TRN_RE, "GSTIN": GSTIN_RE}


def find_high_risk_pii(text: str) -> list[str]:
    """Categories of unmistakable personal/financial identifiers still present in a text."""
    found = [name for name, rx in TRIPWIRE.items() if rx.search(text)]
    if any(luhn_ok(m.group(0)) for m in CARD_RE.finditer(text)):
        found.append("CARD")
    return found
