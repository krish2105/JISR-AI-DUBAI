"""
extraction.py — Suite: how well does the Quote agent turn an enquiry into a structured RFQ?

Method (field-level, micro-averaged; written down so the number is reproducible):
    * The enquiry is redacted exactly as in production, then passed to app.tools.rfq.extract_rfq.
    * ITEMS: a predicted item matches a gold item when the quantity is equal AND the description
      covers >= 60% of the gold English or Arabic words. Each matched item = 1 TP; extra predicted
      items = FP; missed gold items = FN.
    * FIELDS buyer_country, incoterm, deadline (structured, EN/AR parsed), language: TP when the gold
      value exists and the prediction equals it; FP when a prediction is wrong or invented; FN when
      a gold value is missed or wrong.
    * extraction_f1 = micro F1 over items + fields. Phase 4 target: >= 0.90 on the test split.
    * extraction_f1_handwritten = the same on 30 hand-written enquiries in styles the templates never produce
      (test only, never used for tuning): the honest estimate of how the extractor generalises.
"""

import asyncio
from collections import defaultdict

from app.security.redactor import redact
from app.tools.rfq import extract_rfq
from eval.common import EvalContext, SuiteResult, description_match, f1, load, parse_deadline

FIELDS = ("buyer_country", "incoterm", "deadline", "language")


def score_one(gold: dict, rfq) -> dict[str, list[int]]:
    """Return {component: [tp, fp, fn]} for one enquiry."""
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    # Items: greedy one-to-one matching.
    unmatched = list(gold["items"])
    for item in rfq.items:
        hit = next((g for g in unmatched if float(item.quantity) == float(g["quantity"])
                    and description_match(g, item.description)), None)
        if hit:
            counts["items"][0] += 1
            unmatched.remove(hit)
        else:
            counts["items"][1] += 1
    counts["items"][2] += len(unmatched)
    # Scalar fields.
    predicted = {
        "buyer_country": rfq.buyer_country if rfq.buyer_country not in ("", "unknown") else None,
        "incoterm": (rfq.incoterm or None) and rfq.incoterm.upper(),
        "deadline": parse_deadline(rfq.deadline),
        "language": rfq.language,
    }
    for name in FIELDS:
        g, p = gold[name], predicted[name]
        if g is not None and p == g:
            counts[name][0] += 1
        else:
            if p is not None:
                counts[name][1] += 1
            if g is not None:
                counts[name][2] += 1
    return counts


def _summary(totals: dict[str, list[int]]) -> dict[str, float]:
    """Micro F1 over everything plus per-component F1."""
    out = {}
    all_tp = sum(v[0] for v in totals.values())
    all_fp = sum(v[1] for v in totals.values())
    all_fn = sum(v[2] for v in totals.values())
    p, r, score = f1(all_tp, all_fp, all_fn)
    out.update(extraction_f1=score, extraction_precision=p, extraction_recall=r)
    for name, (tp, fp, fn) in totals.items():
        out[f"{name}_f1"] = f1(tp, fp, fn)[2]
    return out


async def _score_rows(rows: list[dict], ctx: EvalContext) -> tuple[dict, dict, list, int, dict]:
    """Extract and score rows; returns (totals, slices, failures, errors, sources)."""
    sem = asyncio.Semaphore(ctx.concurrency)
    sources: dict[str, int] = defaultdict(int)

    async def one(row: dict) -> tuple[dict, dict | None, str | None]:
        async with sem:
            try:
                rfq, _, report = await extract_rfq(redact(row["text"]).text)
                sources[report.source] += 1
                return row, score_one(row["labels"], rfq), None
            except Exception as exc:
                return row, None, f"{type(exc).__name__}: {exc}"

    results = await asyncio.gather(*(one(r) for r in rows))
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    by_slice: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    failures, errors = [], 0
    for row, counts, error in results:
        if counts is None:
            errors += 1
            counts = {"items": [0, 0, len(row["labels"]["items"])]}
            counts.update({f: [0, 0, int(row["labels"][f] is not None)] for f in FIELDS})
        row_errors = sum(v[1] + v[2] for v in counts.values())
        for key in ("all", f"lang={row['language']}", f"difficulty={row['difficulty']}", f"split={row['split']}"):
            target = totals if key == "all" else by_slice[key]
            for comp, (tp, fp, fn) in counts.items():
                target[comp][0] += tp
                target[comp][1] += fp
                target[comp][2] += fn
        if row_errors:
            failures.append({"id": row["id"], "language": row["language"], "difficulty": row["difficulty"],
                             "errors": row_errors, "wrong": [k for k, v in counts.items() if v[1] or v[2]],
                             "error": error, "text": row["text"][:220]})
    failures.sort(key=lambda f: -f["errors"])
    return totals, by_slice, failures, errors, dict(sources)


async def run(ctx: EvalContext) -> SuiteResult:
    """Extract every enquiry in scope (+ the hand-written set) and score it."""
    rows = [r for r in load("enquiries", ctx)]
    totals, by_slice, failures, errors, sources = await _score_rows(rows, ctx)
    hand_rows = load("enquiries_handwritten", EvalContext(split="test", concurrency=ctx.concurrency))
    h_totals, h_slices, h_failures, h_errors, _ = await _score_rows(hand_rows, ctx)

    metrics = _summary(totals) | {"crash_rate": errors / len(rows) if rows else 0.0}
    metrics["extraction_f1_handwritten"] = _summary(h_totals)["extraction_f1"]
    metrics["items_f1_handwritten"] = _summary(h_totals).get("items_f1", 0.0)
    slices = {k: {"extraction_f1": _summary(v)["extraction_f1"]} for k, v in sorted(by_slice.items())}
    slices |= {f"handwritten/{k}": {"extraction_f1": _summary(v)["extraction_f1"]}
               for k, v in sorted(h_slices.items()) if k.startswith("lang=")}
    hand_fail = [f | {"set": "handwritten"} for f in h_failures[:3]]
    return SuiteResult("extraction", len(rows) + len(hand_rows), metrics, slices, hand_fail + failures,
                       notes=[f"Extraction sources: {sources}. Hybrid tool app.tools.rfq.extract_rfq with the active "
                              "LLM profile (fake = deterministic parser only).",
                              "The parser was developed on the TRAIN split only; dev/test and the 30 hand-written "
                              "enquiries were not used for tuning."])
