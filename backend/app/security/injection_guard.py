"""
injection_guard.py — Screen untrusted inbound messages for injection and fraud (v0).

Why this file exists:
    Every buyer message is UNTRUSTED DATA. Before agents plan anything, the guard looks for
    attempts to override instructions, extract the system prompt, change bank details or
    rush a payment. It returns flag codes; it never edits or executes the message.

    Flags inform the supervisor and the policy engine. Even if a flag is missed, the policy
    engine still blocks dangerous actions (defence in depth).

v0 scope: English and Arabic keyword patterns. Phase 3 adds a classifier prompt, more
languages/obfuscations (spacing, homoglyphs) and the 30-sample adversarial evaluation.
"""

import re

# flag code -> list of patterns (case-insensitive). Arabic patterns sit next to English ones.
PATTERNS: dict[str, list[str]] = {
    "instruction_override": [
        r"\bignore\b.{0,20}\b(previous|prior|above|all)\b.{0,15}\binstructions?\b",
        r"\bdisregard\b.{0,30}\b(instructions?|rules)\b",
        r"\byou are now\b",
        r"تجاهل.{0,20}التعليمات",
    ],
    "prompt_exfiltration": [
        r"\b(reveal|show|print|repeat)\b.{0,25}\b(system prompt|your instructions|hidden instructions)\b",
    ],
    "bank_change": [
        r"\b(change|changed|update|updated|new)\b.{0,40}\b(bank|account|iban|beneficiary)\b",
        r"\b(bank|account|beneficiary)\b.{0,30}\b(has changed|have changed|is now)\b",
        r"تغيير.{0,20}(الحساب|البنك)",
        r"حساب.{0,10}جديد",
    ],
    "payment_pressure": [
        r"\b(urgent|immediately|today)\b.{0,60}\b(payment|transfer|wire|pay)\b",
        r"\b(payment|transfer|wire)\b.{0,40}\b(urgent|immediately|today)\b",
    ],
}

_COMPILED = {code: [re.compile(p, re.IGNORECASE | re.DOTALL) for p in pats] for code, pats in PATTERNS.items()}


def scan(text: str) -> list[str]:
    """Return the sorted list of flag codes found in the (redacted) message text."""
    return sorted(code for code, patterns in _COMPILED.items() if any(p.search(text) for p in patterns))
