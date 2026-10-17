"""
pilot.py — Suite: real (anonymised) enquiries from the pilot business, scored against the owner's labels (Phase 18).

Data: data/pilot/enquiries.jsonl from scripts/pilot_prepare.py (git-ignored; PILOT_FILE overrides). Without it the
suite reports n=0 and says so. Always reported SEPARATELY from synthetic results, and only the declared dev split may
be used for tuning (fast mode = test split).

Shadow mode: every enquiry runs through the full agent graph in organisation "pilot"; nothing is ever approved or
sent. Metrics:
    pilot_items_f1              items (description + quantity) vs the owner's labels
    pilot_incoterm_accuracy     where the owner labelled an Incoterm
    pilot_language_accuracy     reply language
    pilot_task_success_rate     run reached the approval step with a priced quote
    pilot_quote_delta_median_pct  |Jisr total − owner's actual quote| / owner's quote (where the owner gave one)
    pilot_owner_minutes_median / pilot_agent_seconds_median / pilot_minutes_saved_median
                                the owner's baseline vs Jisr's time plus the review time assumption
"""

import os
import statistics
import time
from pathlib import Path

from app.db.models import Run
from app.db.session import session_scope
from app.profile import default_profile
from app.runs.service import create_run
from eval.common import REPO, EvalContext, SuiteResult, description_match, f1

PILOT_FILE = Path(os.environ.get("PILOT_FILE", REPO / "data" / "pilot" / "enquiries.jsonl"))


def _load(ctx: EvalContext) -> list[dict]:
    import json

    if not PILOT_FILE.exists():
        return []
    rows = [json.loads(line) for line in PILOT_FILE.read_text(encoding="utf-8").splitlines() if line]
    split = ctx.split or ("test" if ctx.fast else None)
    return [r for r in rows if split is None or r["split"] == split]


def _items_counts(gold: list[dict], predicted: list[dict]) -> tuple[int, int, int]:
    tp = fp = 0
    unmatched = list(gold)
    for item in predicted:
        hit = next((g for g in unmatched if float(item["quantity"]) == float(g["quantity"])
                    and description_match(g, item["description"])), None)
        if hit:
            tp += 1
            unmatched.remove(hit)
        else:
            fp += 1
    return tp, fp, len(unmatched)


async def run(ctx: EvalContext) -> SuiteResult:
    rows = _load(ctx)
    if not rows:
        return SuiteResult("pilot", 0, {}, {}, [], [f"No pilot data at {PILOT_FILE}: run scripts/pilot_prepare.py "
                                                     "(docs/pilot/LABEL_SHEET.md)."])
    review_minutes = default_profile().roi.review_minutes_per_quote
    tp = fp = fn = 0
    inc_ok = inc_n = lang_ok = success = 0
    deltas, owner_min, agent_sec, saved, failures = [], [], [], [], []
    for row in rows:
        started = time.perf_counter()
        run_id = await create_run(message=row["text"], channel=row.get("channel", "whatsapp"), org_id="pilot",
                                  background=False)
        seconds = time.perf_counter() - started
        async with session_scope() as db:
            state = (await db.get(Run, run_id)).state
        rfq, quote = state.get("rfq") or {}, state.get("quote") or {}
        a, b, c = _items_counts(row["labels"]["items"], rfq.get("items") or [])
        tp, fp, fn = tp + a, fp + b, fn + c
        if row["labels"].get("incoterm"):
            inc_n += 1
            inc_ok += (rfq.get("incoterm") or "").upper() == row["labels"]["incoterm"].upper()
        lang_ok += rfq.get("language") == row["labels"].get("language")
        ok = state.get("status") == "needs_approval" and bool(quote.get("lines"))
        success += ok
        if row.get("owner_quote_total_aed") and quote.get("total_aed"):
            deltas.append(abs(quote["total_aed"] - row["owner_quote_total_aed"]) / row["owner_quote_total_aed"] * 100)
        agent_sec.append(seconds)
        if row.get("owner_minutes"):
            owner_min.append(row["owner_minutes"])
            saved.append(row["owner_minutes"] - (seconds / 60 + review_minutes))
        if not ok or b or c:
            failures.append({"id": row["id"], "status": state.get("status"), "missed_items": c, "extra_items": b})
    n = len(rows)
    metrics = {"pilot_items_f1": f1(tp, fp, fn)[2], "pilot_language_accuracy": lang_ok / n,
               "pilot_task_success_rate": success / n, "pilot_agent_seconds_median": statistics.median(agent_sec)}
    if inc_n:
        metrics["pilot_incoterm_accuracy"] = inc_ok / inc_n
    if deltas:
        metrics["pilot_quote_delta_median_pct"] = statistics.median(deltas)
    if owner_min:
        metrics["pilot_owner_minutes_median"] = statistics.median(owner_min)
        metrics["pilot_minutes_saved_median"] = statistics.median(saved)
    return SuiteResult("pilot", n, metrics, {}, failures[:10],
                       ["Real enquiries, anonymised by the Jisr redactor; owner's labels; shadow mode (nothing sent).",
                        f"Minutes saved assume {review_minutes} review minutes per quote (business profile)."])
