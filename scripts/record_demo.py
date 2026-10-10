"""
record_demo.py — Record the demo scenarios for offline replay.

Why this file exists:
    The finals need a demo that runs with no network. This script runs every built-in demo
    sample through the real agent pipeline with recording switched on, producing:
      replay/demo.cassette.jsonl         every model answer (used by LLM_PROFILE=replay)
      replay/<sample_id>.events.jsonl    the event stream of each run (handy for frontend/3D work)

Usage (from the repo root):
    make record                          # records with the current LLM_PROFILE (fake by default)
    LLM_PROFILE=prod make record         # record real Claude answers once you have a key

The cassette is rewritten from scratch each time so stale answers never linger.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPLAY_DIR = REPO / "replay"
CASSETTE = REPLAY_DIR / "demo.cassette.jsonl"

# Settings are read from the environment, so set them BEFORE importing the app.
os.environ["LLM_RECORD"] = "true"
os.environ["LLM_CASSETTE"] = str(CASSETTE)
os.environ["DEMO_STEP_DELAY_MS"] = "0"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp()) / 'record.db'}")
sys.path.insert(0, str(REPO / "backend"))

from sqlalchemy import select  # noqa: E402  (imports must follow the environment setup above)

from app.config import get_settings  # noqa: E402
from app.db.models import RunEventRow  # noqa: E402
from app.db.session import init_db, session_scope  # noqa: E402
from app.demo.samples import SAMPLES  # noqa: E402
from app.runs.service import create_run  # noqa: E402


async def main() -> None:
    """Run each sample once and save the cassette plus per-sample event streams."""
    REPLAY_DIR.mkdir(exist_ok=True)
    CASSETTE.unlink(missing_ok=True)
    await init_db()
    print(f"Recording with LLM_PROFILE={get_settings().llm_profile} -> {CASSETTE.relative_to(REPO)}")
    for sample in SAMPLES:
        run_id = await create_run(message=sample.message, channel=sample.channel,
                                  sample_id=sample.id, background=False)
        async with session_scope() as db:
            rows = (await db.scalars(select(RunEventRow).where(RunEventRow.run_id == run_id)
                                     .order_by(RunEventRow.seq))).all()
        out = REPLAY_DIR / f"{sample.id}.events.jsonl"
        with out.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps({"seq": r.seq, "ts": r.ts.isoformat(), "agent": r.agent, "kind": r.kind,
                                     "payload": r.payload, "risk": r.risk}, ensure_ascii=False) + "\n")
        print(f"  {sample.id:<22} {len(rows):>3} events -> {out.relative_to(REPO)}")
    # Voice notes: run each synthetic note through the same signed inbound path, so the cassette also holds the
    # transcripts (offline speech-to-text) and every model answer of those runs.
    from app.api.channels import VOICE_DIR, process_payload  # noqa: E402
    from app.channels.whatsapp import sign  # noqa: E402
    from app.llm.router import VOICE_MANIFEST  # noqa: E402

    secret = get_settings().simulator_secret
    for i, note in enumerate(json.loads(VOICE_MANIFEST.read_text(encoding="utf-8")).values()):
        msg = {"from": f"97150000{i:04d}", "id": f"wamid.REC.{i}", "timestamp": "1760000000", "type": "audio",
               "audio": {"id": f"media.{i}", "mime_type": note["mime_type"], "voice": True}}
        raw = json.dumps({"entry": [{"changes": [{"value": {"messages": [msg]}}]}]}).encode()
        [res] = await process_payload(raw, sign(raw, secret), secret, source="simulator",
                                      audio=(VOICE_DIR / note["file"]).read_bytes(), mime_type=note["mime_type"],
                                      wait=True, run_in_background=False)
        print(f"  voice:{note['file']:<17} {res['status']}")
    entries = sum(1 for _ in CASSETTE.open(encoding="utf-8")) if CASSETTE.exists() else 0
    print(f"Cassette: {entries} recorded model answers.")


if __name__ == "__main__":
    asyncio.run(main())
