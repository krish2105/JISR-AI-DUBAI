"""
buyer_trust.py — Tool: buyer trust SIGNALS for a human to weigh (never a verdict, never a score).

Why this file exists:
    A small exporter cannot run a credit bureau check on every WhatsApp enquiry, but some patterns are worth a
    second look before quoting or shipping on credit: a free-mail address for a "company", a request to pay
    after delivery on a first order, pressure to change bank details, or a name that resembles an entry on the
    UN Security Council sanctions list. Each signal comes with its evidence and why it matters; positive signals
    (a business domain, a UAE trade licence number) are shown too, so the picture is balanced.

    Deterministic code, so the same enquiry always gives the same signals (testable, auditable). Wording rules:
    "possible match" and "for review", never "fraud" or "sanctioned".

Sanctions list: the official UN consolidated list (XML) in data/sanctions_public/ (git-ignored; fetch with
`make sanctions`). Without it the signal says the list is not loaded, so nobody mistakes silence for screening.
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree

SANCTIONS_DIR = Path(__file__).resolve().parents[3] / "data" / "sanctions_public"
SANCTIONS_FILE = SANCTIONS_DIR / "un_consolidated.xml"
FREE_MAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "proton.me",
                     "protonmail.com", "live.com", "aol.com", "mail.com", "yandex.com", "rediffmail.com"}
LEGAL_SUFFIXES = re.compile(r"\b(llc|l\.l\.c|fze|fzco|fzc|fz llc|dmcc|trading|general trading|co|company|ltd|"
                            r"limited|pvt|private|inc|est|establishment|group|international|ذ\.م\.م|ش\.ذ\.م\.م)\b\.?",
                            re.I)
GCC = {"AE", "SA", "OM", "QA", "KW", "BH"}
MATCH_THRESHOLD = 0.92                       # name similarity for a "possible match" (high on purpose: few, precise)

PATTERNS: dict[str, tuple[re.Pattern, str, str]] = {
    # signal: (pattern, risk, why)
    "credit_terms_request": (
        re.compile(r"pay(ment)? after (delivery|arrival|receipt)|open account|on credit|\b(60|90|120|180) days? "
                   r"(credit|payment|terms)|بعد (الاستلام|التسليم|الوصول)|آجل|ائتمان", re.I),
        "medium", "Credit on a first order is the most common way small exporters lose money; consider LC or advance."),
    "bank_change_request": (
        re.compile(r"(change|update|new|different)\s+(our\s+|the\s+)?(bank|account|iban|beneficiary)|"
                   r"(تغيير|تحديث)\s+(الحساب|البنك|بيانات البنك)|حساب (بنكي )?جديد", re.I),
        "high", "Requests to change bank details are the classic invoice-fraud pattern; confirm by phone on a "
                "known number."),
    "pressure_urgency": (
        re.compile(r"\b(urgent(ly)?|immediately|asap|right now|today only|within (1|one|2|two) hours?)\b|"
                   r"عاجل|فورا|فوراً|حالا", re.I),
        "low", "Pressure is common in genuine trade too; it matters when combined with payment or bank changes."),
    "third_party_payment": (
        re.compile(r"(payment|pay|paid)(\s+\w+){0,3}?\s+(from|by|through)\s+(a |an |our )?(third|another|different)"
                   r"[- ](party|company)|"
                   r"(sister|partner) company will pay|طرف ثالث|شركة أخرى ستدفع", re.I),
        "medium", "Payment from a party other than the buyer complicates KYC and chargebacks."),
}
TRADE_LICENCE = re.compile(r"(trade )?licen[cs]e\s*(no\.?|number|#)?\s*[:\-]?\s*\d{5,}|"
                           r"رخصة تجارية\s*(رقم)?\s*[:\-]?\s*\d{5,}", re.I)


@dataclass(frozen=True)
class SanctionsEntry:
    """One name (or alias) from the UN consolidated list."""

    name: str
    reference: str                               # UN reference number, e.g. "QDe.001"
    listed_on: str


def normalise_name(name: str) -> str:
    """Lower case, accents removed, legal suffixes and punctuation dropped, tokens sorted (word order ignored)."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = LEGAL_SUFFIXES.sub(" ", text)
    tokens = re.findall(r"[\w؀-ۿ]+", text)
    return " ".join(sorted(t for t in tokens if len(t) > 1))


@lru_cache
def load_sanctions(path: Path = SANCTIONS_FILE) -> tuple[SanctionsEntry, ...] | None:
    """Entities and individuals (with aliases) from the UN XML; None when the file is not present."""
    if not path.exists():
        return None
    root = ElementTree.parse(path).getroot()
    entries: list[SanctionsEntry] = []
    for node in list(root.iter("INDIVIDUAL")) + list(root.iter("ENTITY")):
        ref = (node.findtext("REFERENCE_NUMBER") or "").strip()
        listed = (node.findtext("LISTED_ON") or "").strip()
        parts = [node.findtext(tag) or "" for tag in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME")]
        names = [" ".join(p.strip() for p in parts if p.strip())]
        for alias_tag in ("INDIVIDUAL_ALIAS", "ENTITY_ALIAS"):
            names += [(a.findtext("ALIAS_NAME") or "").strip() for a in node.iter(alias_tag)]
        entries += [SanctionsEntry(n, ref, listed) for n in names if n]
    return tuple(entries)


def sanctions_signal(buyer_name: str, entries: tuple[SanctionsEntry, ...] | None) -> dict:
    """A 'possible match' signal for the closest listed name, or a 'not loaded' / 'no close match' note."""
    if entries is None:
        return {"signal": "sanctions_list_not_loaded", "risk": "info", "evidence": "UN consolidated list not loaded",
                "why": "Screening did not run here; run `make sanctions` to load the official list."}
    target = normalise_name(buyer_name)
    if not target:
        return {"signal": "sanctions_no_name", "risk": "info", "evidence": "no buyer name in the enquiry",
                "why": "Nothing to screen; ask for the registered company name."}
    best, best_score = None, 0.0
    for entry in entries:
        score = SequenceMatcher(None, target, normalise_name(entry.name)).ratio()
        if score > best_score:
            best, best_score = entry, score
    if best and best_score >= MATCH_THRESHOLD:
        return {"signal": "possible_sanctions_match", "risk": "high",
                "evidence": f"'{buyer_name}' ~ '{best.name}' (UN ref {best.reference}, listed {best.listed_on}, "
                            f"similarity {best_score:.2f})",
                "why": "Name similarity only, not an identity match: a compliance check is required before trading.",
                "source": "UN Security Council Consolidated List"}
    return {"signal": "sanctions_no_close_match", "risk": "positive",
            "evidence": f"closest similarity {best_score:.2f} (< {MATCH_THRESHOLD})",
            "why": "No close name match on the UN consolidated list (not a legal clearance).",
            "source": "UN Security Council Consolidated List"}


def assess(message: str, buyer_name: str = "", buyer_country: str = "", quote_total_aed: float | None = None,
           injection_flags: list[str] | None = None, entries: tuple[SanctionsEntry, ...] | None = None,
           use_list: bool = True) -> list[dict]:
    """All trust signals for one enquiry (the message is the REDACTED text; emails keep their domain)."""
    signals: list[dict] = []
    domains = [d.lower() for d in re.findall(r"@([\w-]+(?:\.[\w-]+)+)", message)]
    free = [d for d in domains if d in FREE_MAIL_DOMAINS]
    if free:
        signals.append({"signal": "free_mail_domain", "risk": "medium", "evidence": free[0],
                        "why": "A company writing from a free-mail address is harder to verify; ask for a company "
                               "email or trade licence."})
    elif domains:
        signals.append({"signal": "business_email_domain", "risk": "positive", "evidence": domains[0],
                        "why": "A company domain can be checked (website, registration)."})
    else:
        signals.append({"signal": "no_email_given", "risk": "low", "evidence": "no email address in the enquiry",
                        "why": "Common on WhatsApp; ask for a company email before sending documents."})
    for name, (rx, risk, why) in PATTERNS.items():
        m = rx.search(message)
        if m:
            signals.append({"signal": name, "risk": risk, "evidence": m.group(0).strip(), "why": why})
    if "bank_change_request" not in {s["signal"] for s in signals} and any("bank" in f for f in injection_flags or []):
        signals.append({"signal": "bank_change_request", "risk": "high", "evidence": "flagged by the injection guard",
                        "why": PATTERNS["bank_change_request"][2]})
    licence = TRADE_LICENCE.search(message)
    if licence:
        signals.append({"signal": "trade_licence_given", "risk": "positive", "evidence": licence.group(0).strip(),
                        "why": "A licence number can be checked on the emirate's business registry."})
    if buyer_country and buyer_country.upper() not in GCC:
        signals.append({"signal": "destination_outside_gcc", "risk": "low", "evidence": buyer_country,
                        "why": "CEPA preference applies to imports into the UAE only; check the final destination."})
    if quote_total_aed is not None and quote_total_aed >= 200_000:
        signals.append({"signal": "large_first_order", "risk": "low", "evidence": f"AED {quote_total_aed:,.0f}",
                        "why": "Large first orders deserve secured payment (LC or advance)."})
    if use_list:
        signals.append(sanctions_signal(buyer_name, entries if entries is not None else load_sanctions()))
    return signals


def needs_review(signals: list[dict]) -> bool:
    """True when any signal is medium or high risk (the run then shows 'review buyer' to the human)."""
    return any(s["risk"] in ("medium", "high") for s in signals)
