"""
trajectory.py — Suite: do the agents take the right PATH and the right ACTIONS, every time? (v3 §9a)

Scenarios: data/gold/trajectories.yaml (50: clean EN/AR/mixed, attacks, kill switch, risky buyers, missing details,
non-UAE destinations, returning buyers, voice notes, duplicate delivery). Every scenario enters through the signed
WhatsApp inbound path (simulator secret) with its own sender, and runs REPEATS times with a fresh sender each time.

Checked per run: status, agent path (order) and skipped agents, approvals held, autonomous sends, policy rules that
fired (or must not), quote lines, draft kind, pricing flags, buyer signals, language, duplicate handling.
Metrics:
    trajectory_pass_rate     passing runs / all runs
    trajectory_pass_all_k    scenarios passing in ALL repeats (pass^k)
    path_consistency         scenarios whose agent path is identical across repeats
"""

import json
import time
import uuid
from collections import defaultdict

import yaml
from sqlalchemy import select

from app.channels.whatsapp import sign
from app.db.models import Approval, AuditEntry, Run, RunEventRow
from app.db.session import session_scope
from eval.common import DATA, REPO, EvalContext, SuiteResult

REPEATS = 3


def _payload(sender: str, text: str | None = None, voice: dict | None = None) -> bytes:
    msg = {"from": sender, "id": f"wamid.TRAJ.{uuid.uuid4().hex}", "timestamp": str(int(time.time()))}
    if voice:
        msg |= {"type": "audio", "audio": {"id": "media.traj", "mime_type": voice["mime_type"], "voice": True}}
    else:
        msg |= {"type": "text", "text": {"body": text}}
    return json.dumps({"entry": [{"changes": [{"value": {"contacts": [{"wa_id": sender, "profile": {"name": "T"}}],
                                                       "messages": [msg]}}]}]}).encode()


async def _deliver(raw: bytes, voice: dict | None = None) -> dict:
    from app.api.channels import VOICE_DIR, process_payload
    from app.config import get_settings

    secret = get_settings().simulator_secret
    audio = (VOICE_DIR / voice["file"]).read_bytes() if voice else None
    [res] = await process_payload(raw, sign(raw, secret), secret, source="simulator", audio=audio,
                                  mime_type=voice["mime_type"] if voice else None, wait=True, run_in_background=False)
    return res


async def _observe(run_id: str) -> dict:
    """Everything the expectations look at, read back from the database."""
    async with session_scope() as db:
        run = await db.get(Run, run_id)
        events = (await db.scalars(select(RunEventRow).where(RunEventRow.run_id == run_id)
                                   .order_by(RunEventRow.seq))).all()
        approvals = (await db.scalars(select(Approval).where(Approval.run_id == run_id))).all()
        audit = (await db.scalars(select(AuditEntry).where(AuditEntry.run_id == run_id))).all()
    state = run.state
    return {
        "status": run.status,
        "path": [e.agent for e in events if e.kind == "agent_finished"],
        "approvals": len(approvals),
        "autonomous": sum(a.action == "action.autonomous_sent" for a in audit),
        "rules": {r for e in events if e.kind == "policy_decision" for r in e.payload.get("rule_ids", [])},
        "quote_lines": len((state.get("quote") or {}).get("lines", [])),
        "drafts": [d.get("kind", "quote") for d in state.get("drafts", [])],
        "flags": set((state.get("quote") or {}).get("pricing_flags", [])),
        "signals": {s["signal"] for s in state.get("buyer_signals", [])},
        "language": (state.get("rfq") or {}).get("language"),
    }


def _check(expect: dict, got: dict) -> list[str]:
    """Human-readable list of failed expectations (empty = pass)."""
    bad = []
    if "status" in expect and got["status"] != expect["status"]:
        bad.append(f"status {got['status']} != {expect['status']}")
    if "path" in expect:
        it = iter(got["path"])
        if not all(step in it for step in expect["path"]):          # in order, gaps allowed
            bad.append(f"path {got['path']} lacks {expect['path']}")
    bad += [f"{a} ran" for a in expect.get("skip", []) if a in got["path"]]
    for key in ("approvals", "autonomous", "quote_lines", "language"):
        if key in expect and got[key] != expect[key]:
            bad.append(f"{key} {got[key]} != {expect[key]}")
    bad += [f"rule {r} did not fire" for r in expect.get("rules_any", []) if r not in got["rules"]]
    bad += [f"rule {r} fired" for r in expect.get("rules_none", []) if r in got["rules"]]
    bad += [f"flag {f} missing" for f in expect.get("flags_any", []) if f not in got["flags"]]
    bad += [f"signal {s} missing" for s in expect.get("signals_any", []) if s not in got["signals"]]
    if "draft" in expect and expect["draft"] not in got["drafts"]:
        bad.append(f"draft {expect['draft']} not in {got['drafts']}")
    return bad


async def run(ctx: EvalContext) -> SuiteResult:
    """Run every scenario REPEATS times."""
    from app.channels.outbox import set_kill_switch
    from app.config import get_settings

    scenarios = yaml.safe_load((REPO / "data" / "gold" / "trajectories.yaml").read_text(encoding="utf-8"))
    if ctx.fast:
        scenarios = scenarios[::5]
    texts = {r["id"]: r["text"] for name in ("enquiries", "adversarial")
             for r in map(json.loads, (DATA / f"{name}.jsonl").read_text(encoding="utf-8").splitlines())}
    voices = {v["file"].rsplit(".", 1)[0]: v for v in json.loads(
        (REPO / "replay" / "voice" / "manifest.json").read_text(encoding="utf-8")).values()}
    org = get_settings().whatsapp_org_id
    passed_runs = total_runs = 0
    all_k = consistent = 0
    by_group: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    failures = []
    for sc in scenarios:
        setup, expect = sc.get("setup", {}), sc["expect"]
        paths, oks = [], []
        for rep in range(REPEATS):
            sender = f"9715{abs(hash((sc['id'], rep, time.time_ns()))) % 10**8:08d}"
            if setup.get("kill_switch"):
                async with session_scope() as db:
                    await set_kill_switch(db, org, True, actor="eval", reason="trajectory scenario")
            try:
                if setup.get("prior"):
                    await _deliver(_payload(sender, setup["prior"]))
                voice = voices.get(sc.get("voice", ""))
                text = sc.get("text") or texts.get(sc.get("enquiry") or sc.get("attack"))
                raw = _payload(sender, text=text, voice=voice)
                res = await _deliver(raw, voice)
                dup = await _deliver(raw, voice) if setup.get("duplicate_delivery") else None
            finally:
                if setup.get("kill_switch"):
                    async with session_scope() as db:
                        await set_kill_switch(db, org, False, actor="eval", reason=None)
            if not res.get("run_id"):
                problems, got = [f"no run: {res}"], {"path": []}
            else:
                got = await _observe(res["run_id"])
                problems = _check(expect, got)
                if expect.get("duplicate_ignored") and (dup or {}).get("status") != "duplicate":
                    problems.append(f"duplicate not ignored: {dup}")
            ok = not problems
            oks.append(ok)
            paths.append(tuple(got["path"]))
            passed_runs += ok
            total_runs += 1
            group = "attack" if "attack" in sc else ("voice" if "voice" in sc else sc["id"][:2])
            by_group[group][0] += ok
            by_group[group][1] += 1
            if not ok and len(failures) < 30:
                failures.append({"id": sc["id"], "rep": rep, "problems": problems[:4]})
        all_k += all(oks)
        consistent += len(set(paths)) == 1
    n = len(scenarios)
    metrics = {"trajectory_pass_rate": passed_runs / total_runs if total_runs else 0.0,
               "trajectory_pass_all_k": all_k / n if n else 0.0,
               "path_consistency": consistent / n if n else 0.0}
    notes = [f"{n} scenarios x {REPEATS} runs, profile-dependent: with the fake/replay profile runs are deterministic, "
             "so consistency is expected to be 1.0; with Claude (prod) this measures run-to-run variance."]
    return SuiteResult("trajectory", n, metrics, {}, failures, notes)
