"""
pii.py — 90 labelled messages for redaction evaluation (personal data to HIDE, business data to KEEP).

Why this file exists:
    The enquiry set only contains emails and phone numbers. Real messages also carry names, PO boxes,
    Emirates IDs, UAE tax numbers (TRN), Indian GSTIN/PAN, bank account and card numbers, sometimes with
    Arabic-Indic digits. Each message is built from templates so we know exactly which values must be
    hidden (labels.hide) and which business values must survive redaction (labels.keep: company names,
    quantities, HS codes, Incoterms, dates). All values are fictional; card numbers pass the Luhn check
    but are made up.
"""

import random

FIRST = ["Ahmed", "Fatima", "Omar", "Priya", "Rahul", "Aisha", "Khalid", "Meera", "Yousef", "Sara"]
LAST = ["Khan", "Al Mansoori", "Sharma", "Al Hashimi", "Patel", "Haddad", "Verma", "Al Suwaidi"]
AR_NAMES = ["أحمد المنصوري", "فاطمة الهاشمي", "خالد السويدي", "عائشة الحداد", "يوسف الكعبي"]
HONORIFICS = ["Mr.", "Mr", "Ms.", "Mrs.", "Dr."]
AR_HONORIFICS = ["السيد", "السيدة", "الأستاذ"]
COMPANIES = ["Bayt Al Hadaya Trading LLC", "Desert Rose Gifts FZE", "Gulf Star General Trading", "Pink City Exports (demo)"]
HS_CODES = ["44201900", "62142010", "94051900", "6302.21", "442011000000"]
ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def _luhn_card(rng: random.Random) -> str:
    """A made-up 16-digit number that passes the Luhn checksum, grouped 4-4-4-4."""
    digits = [4] + [rng.randint(0, 9) for _ in range(14)]
    total = 0
    for i, d in enumerate(reversed(digits)):          # positions from the right, check digit excluded
        total += sum(divmod(d * 2, 10)) if i % 2 == 0 else d
    digits.append((10 - total % 10) % 10)
    s = "".join(map(str, digits))
    return " ".join(s[i:i + 4] for i in range(0, 16, 4))


def _case(rng: random.Random, idx: int) -> dict:
    """One message with a mix of PII and business data."""
    hide, keep, parts = [], [], []
    company = rng.choice(COMPANIES)
    qty = rng.choice([150, 300, 1200, 2500])
    hs = rng.choice(HS_CODES)
    keep += [company, str(qty), hs, "CIF"]
    parts.append(f"Order from {company}: {qty} pcs, HS code {hs}, CIF Jebel Ali.")

    kinds = rng.sample(["person", "ar_person", "pobox", "eid", "trn", "gstin", "pan", "account", "card",
                        "phone_ar_digits", "phone_paren", "email"], k=3)
    for kind in kinds:
        if kind == "person":
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            parts.append(f"Please contact {rng.choice(HONORIFICS)} {name} for delivery.")
            hide.append({"type": "PERSON", "value": name})
        elif kind == "ar_person":
            name = rng.choice(AR_NAMES)
            parts.append(f"للتواصل مع {rng.choice(AR_HONORIFICS)} {name} بخصوص الشحنة.")
            hide.append({"type": "PERSON", "value": name})
        elif kind == "pobox":
            box = str(rng.randint(10000, 99999))
            parts.append(rng.choice([f"Address: P.O. Box {box}, Dubai.", f"العنوان: ص.ب {box} دبي."]))
            hide.append({"type": "POBOX", "value": box})
        elif kind == "eid":
            eid = f"784-{rng.randint(1970, 2002)}-{rng.randint(1000000, 9999999)}-{rng.randint(1, 9)}"
            parts.append(f"Emirates ID {eid} attached for KYC.")
            hide.append({"type": "EID", "value": eid})
        elif kind == "trn":
            trn = "100" + "".join(str(rng.randint(0, 9)) for _ in range(12))
            parts.append(f"Our TRN is {trn}.")
            hide.append({"type": "TRN", "value": trn})
        elif kind == "gstin":
            gstin = f"08{''.join(rng.choice('ABCDEFGHJK') for _ in range(5))}{rng.randint(1000, 9999)}{rng.choice('ABCDE')}1Z{rng.randint(1, 9)}"
            parts.append(f"Seller GSTIN {gstin}.")
            hide.append({"type": "GSTIN", "value": gstin})
        elif kind == "pan":
            pan = f"{''.join(rng.choice('ABCDEFGHJK') for _ in range(5))}{rng.randint(1000, 9999)}{rng.choice('ABCDE')}"
            parts.append(f"PAN: {pan}.")
            hide.append({"type": "PAN", "value": pan})
        elif kind == "account":
            acct = f"{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
            parts.append(rng.choice([f"Account No. {acct} at our bank.", f"A/C {acct}."]))
            hide.append({"type": "ACCOUNT", "value": acct})
        elif kind == "card":
            card = _luhn_card(rng)
            parts.append(f"Card for the sample fee: {card}.")
            hide.append({"type": "CARD", "value": card})
        elif kind == "phone_ar_digits":
            phone = f"05{rng.randint(0, 9)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}".translate(ARABIC_INDIC)
            parts.append(f"هاتف: {phone}")
            hide.append({"type": "PHONE", "value": phone})
        elif kind == "phone_paren":
            phone = f"+971 (4) {rng.randint(100, 999)}-{rng.randint(1000, 9999)}"
            parts.append(f"Office {phone}.")
            hide.append({"type": "PHONE", "value": phone})
        else:
            email = f"{rng.choice(['ops', 'k.sharma', 'buyer01'])}@{rng.choice(['gmail.com', 'gulfstar-demo.ae'])}"
            parts.append(f"Email {email}.")
            hide.append({"type": "EMAIL", "value": email.split('@')[0]})
    date = f"{rng.randint(1, 28)} Dec 2026"
    keep.append(date)
    parts.append(f"Delivery by {date}.")
    rng.shuffle(parts[1:-1]) if len(parts) > 3 else None
    return {"id": f"pii_{idx:03d}", "text": " ".join(parts), "labels": {"hide": hide, "keep": keep}}


def generate_pii(seed: int = 20261009) -> list[dict]:
    """90 cases, split 54 train / 18 dev / 18 test."""
    rng = random.Random(seed + 2)
    rows = [_case(rng, i) for i in range(1, 91)]
    for i, row in enumerate(rows):
        row["split"] = "train" if i < 54 else ("dev" if i < 72 else "test")
        row["language"] = "mixed" if any(h["type"] == "PERSON" and not h["value"].isascii() for h in row["labels"]["hide"]) else "en"
    return rows
