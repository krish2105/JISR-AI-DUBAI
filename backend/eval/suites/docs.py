"""
docs.py — Suite: does the Document Consistency Checker find the planted mistakes?

Metrics (exact, because mistakes were planted by the generator):
    doc_issue_recall        share of planted mistakes found (same type; field optional). Phase 6 target >= 0.90.
    doc_issue_precision     share of reported findings that match a planted mistake.
    clean_set_fpr           share of clean document sets with ANY finding (target <= 0.05).
    doc_issue_field_accuracy  found mistakes reported on the exact planted field (e.g. packing_list.line[1].quantity)
Slices: format_noise=yes|no (v4 sets with dotted HS codes, "500 pcs", "52,840.00" ...).

Bias note: the planted mistakes and the checker share an author; 1.0 means the checks are implemented correctly
and robust to the listed formatting, not that every real-world document mistake is covered.
"""

from collections import defaultdict

from app.tools import doc_checker
from eval.common import EvalContext, SuiteResult, f1, load


async def run(ctx: EvalContext) -> SuiteResult:
    """Run the checker on every document set in scope."""
    rows = load("docsets", ctx)
    tp = fp = fn = clean_with_findings = clean_total = 0
    per_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])     # [found, planted]
    per_noise: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])  # [found, planted, clean_flagged, clean]
    field_ok = 0
    failures = []
    for row in rows:
        findings = doc_checker.check_document_set(row["documents"])
        planted = list(row["labels"]["issues"])
        noise = per_noise["yes" if row["labels"].get("format_noise") else "no"]
        if row["labels"]["clean"]:
            clean_total += 1
            clean_with_findings += bool(findings)
            noise[3] += 1
            noise[2] += bool(findings)
            if findings:
                failures.append({"id": row["id"], "false_alarm": [f["type"] for f in findings]})
        found_types = [f["type"] for f in findings]
        found_fields = {(f["type"], f["field"]) for f in findings}
        for issue in planted:
            per_type[issue["type"]][1] += 1
            noise[1] += 1
            if issue["type"] in found_types:
                tp += 1
                noise[0] += 1
                field_ok += (issue["type"], issue["field"]) in found_fields
                per_type[issue["type"]][0] += 1
                found_types.remove(issue["type"])
            else:
                fn += 1
                failures.append({"id": row["id"], "missed": issue["type"], "field": issue["field"]})
        fp += len(found_types)
    precision, recall, score = f1(tp, fp, fn)
    metrics = {"doc_issue_recall": recall, "doc_issue_precision": precision, "doc_issue_f1": score,
               "clean_set_fpr": clean_with_findings / clean_total if clean_total else 0.0,
               "doc_issue_field_accuracy": field_ok / tp if tp else 1.0}
    slices = {f"type={k}": {"recall": v[0] / v[1]} for k, v in sorted(per_type.items())}
    slices |= {f"format_noise={k}": {"recall": v[0] / v[1] if v[1] else 1.0, "clean_fpr": v[2] / v[3] if v[3] else 0.0}
               for k, v in sorted(per_noise.items())}
    notes = ["Planted mistakes and checker share an author: this measures correct implementation and robustness "
             "to formatting, not coverage of every real-world mistake."]
    return SuiteResult("docs", len(rows), metrics, slices, failures, notes)
