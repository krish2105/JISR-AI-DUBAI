"""
e2e.py — Suite: end-to-end runs of normal enquiries through the whole agent graph.

task_success for one enquiry = the run reaches `needs_approval`, the quote has at least one line,
and the reply draft is in the buyer's language (mixed enquiries may be answered in EN or AR).
Also reports latency (p50/p95 seconds, demo pacing switched off) and steps per run.
Phase 9 adds the trajectory suite (correct tools, recovery, expected key steps).
"""

import statistics
import time

from sqlalchemy import func, select

from app.db.models import Approval, Run, RunEventRow
from app.db.session import session_scope
from app.runs.service import create_run
from eval.common import EvalContext, SuiteResult, load


def _pct(values: list[float], q: float) -> float:
    """Simple percentile (nearest rank)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


async def run(ctx: EvalContext) -> SuiteResult:
    """Run a stratified sample of enquiries end to end."""
    rows = load("enquiries", ctx)
    if ctx.fast:
        rows = rows[:20]
    successes, latencies, steps = 0, [], []
    failures, by_lang = [], {}
    for row in rows:
        started = time.perf_counter()
        run_id = await create_run(message=row["text"], channel=row["channel"], org_id="eval", background=False)
        latencies.append(time.perf_counter() - started)
        async with session_scope() as db:
            run = await db.get(Run, run_id)
            approval = await db.scalar(select(Approval).where(Approval.run_id == run_id))
            steps.append(await db.scalar(select(func.count()).select_from(RunEventRow)
                                         .where(RunEventRow.run_id == run_id, RunEventRow.kind == "agent_finished")))
        lines = (run.state.get("quote") or {}).get("lines", [])
        draft_lang = approval.payload.get("language") if approval else None
        wanted = {"en", "ar"} if row["language"] == "mixed" else {row["language"]}
        ok = run.status == "needs_approval" and bool(lines) and draft_lang in wanted
        successes += ok
        stats = by_lang.setdefault(row["language"], [0, 0])
        stats[0] += ok
        stats[1] += 1
        if not ok:
            failures.append({"id": row["id"], "language": row["language"], "status": run.status,
                             "lines": len(lines), "draft_language": draft_lang})
    n = len(rows) or 1
    metrics = {"task_success_rate": successes / n, "latency_p50_s": statistics.median(latencies) if latencies else 0,
               "latency_p95_s": _pct(latencies, 0.95), "steps_mean": statistics.mean(steps) if steps else 0}
    slices = {f"lang={k}": {"task_success_rate": v[0] / v[1]} for k, v in sorted(by_lang.items())}
    return SuiteResult("e2e", len(rows), metrics, slices, failures)
