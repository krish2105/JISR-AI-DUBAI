"""
redactor.py — Mask personal data before any model sees a message (Phase 1 version, v0).

Why this file exists:
    Rule: models only ever see redacted text. Phone numbers, the personal part of email
    addresses and bank account numbers (IBANs) are replaced by consistent tokens such as
    [PHONE_1]. The same value always gets the same token inside one message, so the
    agents can still reason ("the buyer gave one phone number").

    The email *domain* is kept ([EMAIL_1]@company.ae) because a business domain is a useful,
    non-personal trust signal (free-mail vs company domain).

v0 scope: regex patterns for email, phone, IBAN. Phase 3 adds names, addresses, Arabic-Indic
digits, more account formats and a captured-call test proving PII never reaches a model.
"""

import re

from pydantic import BaseModel, Field

# IBAN: 2 letters, 2 check digits, then groups of letters/digits (spaces allowed).
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,4})?\b")
# Email: capture the personal part and the domain separately.
EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
# Phone: optional +, then 9-15 digits possibly separated by spaces or dashes.
PHONE_RE = re.compile(r"(?<![\w])\+?\d(?:[\s-]?\d){8,14}(?![\w])")


class RedactionResult(BaseModel):
    """Redacted text plus counts per category (the original values are never stored)."""

    text: str
    counts: dict[str, int] = Field(default_factory=dict)


def redact(text: str) -> RedactionResult:
    """Replace emails, IBANs and phone numbers with consistent tokens."""
    seen: dict[tuple[str, str], str] = {}      # (category, original value) -> token
    counts: dict[str, int] = {}

    def token_for(category: str, value: str) -> str:
        """Return the existing token for this value, or create the next one."""
        key = (category, value)
        if key not in seen:
            counts[category] = counts.get(category, 0) + 1
            seen[key] = f"[{category}_{counts[category]}]"
        return seen[key]

    # Order matters: IBANs contain long digit runs that would otherwise look like phones.
    out = IBAN_RE.sub(lambda m: token_for("IBAN", m.group(0).replace(" ", "")), text)
    out = EMAIL_RE.sub(lambda m: f"{token_for('EMAIL', m.group(1))}@{m.group(2)}", out)
    out = PHONE_RE.sub(lambda m: token_for("PHONE", re.sub(r"[\s-]", "", m.group(0))), out)
    return RedactionResult(text=out, counts=counts)
