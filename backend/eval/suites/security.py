"""
security.py — Suite: redaction of personal data and injection/fraud screening.

Metrics:
    pii_redaction_recall      share of gold PII values (email local parts, phone numbers) that no longer
                              appear in the redacted text (digits compared without spaces/dashes). Target 1.0.
    quantity_preservation     over-redaction check: of the gold quantities written as numbers in the original
                              (after normalising Arabic-Indic digits, "1,200" and "1.2k"), the share still present
                              as standalone numbers after redaction. Number words ("five hundred") are excluded.
    injection_detection_recall share of the 30 attacks that raise at least one guard flag. Phase 3 target 1.0.
    injection_category_recall share of expected flag codes that were raised (finer-grained).
    false_positive_rate       share of the 300 normal enquiries that raise any flag (target <= 0.02).
    hard_negative_fpr         same, on the 10 enquiries that mention banks/accounts/urgency legitimately.
"""

import re
from collections import defaultdict

from app.security.injection_guard import scan
from app.security.redactor import redact
from eval.common import EvalContext, SuiteResult, load


def _digits(text: str) -> str:
    """Only the digits of a text (to compare phone numbers written in different formats)."""
    return re.sub(r"\D", "", text)


ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def standalone_numbers(text: str) -> list[int]:
    """Numbers as a buyer means them: Arabic-Indic digits, '1,200' and '1.2k' all become integers."""
    t = text.translate(ARABIC_INDIC)
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)                                  # 1,200 -> 1200
    t = re.sub(r"(\d+(?:\.\d+)?)k\b", lambda m: str(int(float(m.group(1)) * 1000)), t, flags=re.I)
    return [int(n) for n in re.findall(r"(?<![\d.])\d+(?![\d.])", t)]


async def run(ctx: EvalContext) -> SuiteResult:
    """Score the redactor on enquiries and the guard on attacks + normal traffic."""
    enquiries = load("enquiries", ctx)
    attacks = load("adversarial", ctx)
    failures: list[dict] = []

    # ----- redaction -----
    pii_total = pii_hidden = q_total = q_kept = 0
    by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in enquiries:
        redacted = redact(row["text"]).text
        compact = re.sub(r"[\s-]", "", redacted)
        for pii in row["labels"]["pii"]:
            leaked = (pii["value"] in redacted) if pii["type"] == "EMAIL" else (_digits(pii["value"]) in compact)
            pii_total += 1
            by_type[pii["type"]][1] += 1
            if not leaked:
                pii_hidden += 1
                by_type[pii["type"]][0] += 1
            else:
                failures.append({"id": row["id"], "kind": "pii_leak", "type": pii["type"], "value": "***"})
        before, after = standalone_numbers(row["text"]), standalone_numbers(redacted)
        for item in row["labels"]["items"]:
            if item["quantity"] in before:                     # only quantities written as numbers
                q_total += 1
                q_kept += item["quantity"] in after

    # ----- injection screening -----
    detected = cat_hit = cat_total = 0
    per_lang: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in attacks:
        flags = set(scan(redact(row["text"]).text))
        expected = set(row["labels"]["expected_flags"])
        per_lang[row["language"]][1] += 1
        if flags:
            detected += 1
            per_lang[row["language"]][0] += 1
        else:
            failures.append({"id": row["id"], "kind": "attack_missed", "category": row["category"],
                             "language": row["language"], "text": row["text"][:160]})
        cat_total += len(expected)
        cat_hit += len(expected & flags)

    false_pos = [r for r in enquiries if scan(redact(r["text"]).text)]
    hard_neg = [r for r in enquiries if r["hard_negative"]]
    hard_fp = [r for r in hard_neg if r in false_pos]
    for r in false_pos[:5]:
        failures.append({"id": r["id"], "kind": "false_positive", "flags": scan(redact(r["text"]).text),
                         "text": r["text"][:160]})

    metrics = {
        "pii_redaction_recall": pii_hidden / pii_total if pii_total else 1.0,
        "quantity_preservation": q_kept / q_total if q_total else 1.0,
        "injection_detection_recall": detected / len(attacks) if attacks else 1.0,
        "injection_category_recall": cat_hit / cat_total if cat_total else 1.0,
        "false_positive_rate": len(false_pos) / len(enquiries) if enquiries else 0.0,
        "hard_negative_fpr": len(hard_fp) / len(hard_neg) if hard_neg else 0.0,
    }
    slices = {f"pii={k}": {"redaction_recall": v[0] / v[1]} for k, v in by_type.items()}
    slices |= {f"attack_lang={k}": {"detection_recall": v[0] / v[1]} for k, v in sorted(per_lang.items())}
    return SuiteResult("security", len(enquiries) + len(attacks), metrics, slices, failures,
                       notes=["Guard and redactor are v0 (Phase 1); Phase 3 hardens both."])
