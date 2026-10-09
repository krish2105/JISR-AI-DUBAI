"""
trust.py — Suite: does the Buyer Trust tool raise the planted signals and stay quiet on look-alikes?

Metrics (exact: the planted phrases are the labels, data/synthetic/trust.jsonl):
    trust_signal_recall       planted signals raised / planted signals
    trust_signal_precision    raised signals that were planted / raised signals (of the labelled signal types)
    trust_hard_negative_fpr   hard-negative rows where the look-alike signal fired anyway
Sanctions matching is tested in unit tests with a fixture list (the official list is not in the repo).
"""

from collections import defaultdict

from app.tools.buyer_trust import assess
from eval.common import EvalContext, SuiteResult, f1, load

LABELLED = {"free_mail_domain", "business_email_domain", "credit_terms_request", "bank_change_request",
            "pressure_urgency", "third_party_payment", "trade_licence_given"}


async def run(ctx: EvalContext) -> SuiteResult:
    """Score every row in scope."""
    rows = load("trust", ctx)
    tp = fp = fn = 0
    hard_total = hard_fired = 0
    per_signal: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    per_lang: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    failures = []
    for row in rows:
        got = {s["signal"] for s in assess(row["text"], use_list=False)} & LABELLED
        expected = set(row["signals"])
        tp += len(got & expected)
        fn += len(expected - got)
        fp += len(got - expected)
        for name in expected:
            per_signal[name][1] += 1
            per_signal[name][0] += name in got
            per_lang[row["language"]][1] += 1
            per_lang[row["language"]][0] += name in got
        if row["absent"]:
            hard_total += 1
            hard_fired += bool(set(row["absent"]) & got)
        if got != expected:
            failures.append({"id": row["id"], "language": row["language"], "text": row["text"][:160],
                             "missed": sorted(expected - got), "extra": sorted(got - expected)})
    precision, recall, score = f1(tp, fp, fn)
    metrics = {"trust_signal_recall": recall, "trust_signal_precision": precision, "trust_signal_f1": score,
               "trust_hard_negative_fpr": hard_fired / hard_total if hard_total else 0.0}
    slices = {f"signal={k}": {"recall": v[0] / v[1]} for k, v in sorted(per_signal.items())}
    slices |= {f"lang={k}": {"recall": v[0] / v[1]} for k, v in sorted(per_lang.items())}
    notes = ["Phrases and detector share an author: this measures correctness and look-alike false alarms, "
             "not coverage of real fraud wording (needs pilot data)."]
    return SuiteResult("trust", len(rows), metrics, slices, failures, notes)
