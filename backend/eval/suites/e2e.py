"""
e2e.py — Suite: end-to-end runs of normal enquiries through the whole agent graph.

task_success for one enquiry = the run reaches `needs_approval`, the quote has at least one line,
and the reply draft is in the buyer's language (mixed enquiries may be answered in EN or AR).
Also reports latency (p50/p95 seconds, demo pacing switched off), steps per run, and the measured model
cost and tokens per enquiry (Phase 14; zero on the offline profile, real on `prod`).
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


async def _voice_notes(failures: list[dict]) -> tuple[int, int]:
    """The synthetic WhatsApp voice notes through the real inbound path (signature, STT, pipeline)."""
    import json as _json
    import time as _time

    from app.api.channels import VOICE_DIR, process_payload
    from app.channels.whatsapp import sign
    from app.config import get_settings
    from app.llm.router import VOICE_MANIFEST

    if not VOICE_MANIFEST.exists():
        return 0, 0
    ok = 0
    manifest = _json.loads(VOICE_MANIFEST.read_text(encoding="utf-8"))
    for i, note in enumerate(manifest.values()):
        msg = {"from": f"97150000{i:04d}", "id": f"wamid.EVAL.voice.{i}.{_time.time_ns()}",
               "timestamp": str(int(_time.time())), "type": "audio",
               "audio": {"id": f"media.{i}", "mime_type": note["mime_type"], "voice": True}}
        raw = _json.dumps({"entry": [{"changes": [{"value": {"messages": [msg]}}]}]}).encode()
        secret = get_settings().simulator_secret
        [res] = await process_payload(raw, sign(raw, secret), secret, source="simulator",
                                      audio=(VOICE_DIR / note["file"]).read_bytes(), mime_type=note["mime_type"],
                                      wait=True, run_in_background=False)
        good = False
        if res.get("run_id"):
            async with session_scope() as db:
                run = await db.get(Run, res["run_id"])
            good = run.status == "needs_approval" and len((run.state.get("quote") or {}).get("lines", [])) >= 2 \
                and (run.state.get("rfq") or {}).get("language") == note["language"]
        ok += good
        if not good:
            failures.append({"id": f"voice:{note['file']}", "status": res.get("status"), "reason": res.get("reason")})
    return ok, len(manifest)


async def run(ctx: EvalContext) -> SuiteResult:
    """Run a stratified sample of enquiries end to end."""
    rows = load("enquiries", ctx)
    if ctx.fast:
        rows = rows[:20]
    successes, latencies, steps, costs, tokens = 0, [], [], [], []
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
        usage = run.state.get("usage") or {}
        costs.append(usage.get("cost_usd", 0.0))
        tokens.append(usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
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
    voice_ok, voice_n = await _voice_notes(failures)
    n = len(rows) or 1
    metrics = {"task_success_rate": successes / n,
               "voice_task_success_rate": voice_ok / voice_n if voice_n else 0.0,
               "latency_p50_s": statistics.median(latencies) if latencies else 0,
               "latency_p95_s": _pct(latencies, 0.95), "steps_mean": statistics.mean(steps) if steps else 0,
               # Measured model cost per enquiry at published prices (app/llm/pricing.yaml); 0 on offline models.
               "cost_per_quote_usd": statistics.mean(costs) if costs else 0.0,
               "tokens_per_quote": statistics.mean(tokens) if tokens else 0.0}
    slices = {f"lang={k}": {"task_success_rate": v[0] / v[1]} for k, v in sorted(by_lang.items())}
    return SuiteResult("e2e", len(rows), metrics, slices, failures)
