"""
test_pilot.py — Phase 18 pilot kit: past enquiries are anonymised with the Jisr redactor, split dev/test, and scored
against the owner's labels in shadow mode (nothing is sent).
"""

import csv
import importlib.util
import json
from pathlib import Path

from sqlalchemy import select

from app.db.models import AuditEntry
from app.db.session import session_scope

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pilot_prepare.py"
spec = importlib.util.spec_from_file_location("pilot_prepare", SCRIPT)
pilot_prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot_prepare)

ROWS = [
    {
        "id": "001",
        "received_at": "2026-09-02",
        "channel": "whatsapp",
        "language": "en",
        "text": "Hi, Ahmed here from Bayt Al Hadaya (ahmed@baytalhadaya.ae, +971 50 123 4567). We need 500 brass diya "
        "lamps and 200 cotton table runners CIF Jebel Ali.",
        "owner_items": "brass diya lamps:500|cotton table runners:200",
        "owner_incoterm": "CIF",
        "owner_quote_total_aed": "14800",
        "owner_minutes": "40",
    },
    {
        "id": "002",
        "received_at": "2026-09-05",
        "channel": "whatsapp",
        "language": "en",
        "text": "Please quote 300 jute shopping bags FOB Mundra. Call 0501234567.",
        "owner_items": "jute shopping bags:300",
        "owner_incoterm": "FOB",
        "owner_quote_total_aed": "",
        "owner_minutes": "25",
    },
]


def write_raw(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ROWS[0]))
        writer.writeheader()
        writer.writerows(ROWS)


def test_prepare_anonymises_and_splits(tmp_path):
    raw, out = tmp_path / "raw.csv", tmp_path / "pilot.jsonl"
    write_raw(raw)
    report = pilot_prepare.prepare(raw, out)
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert report["rows"] == 2 and report["dev"] + report["test"] == 2 and not report["refused_rows_with_leaks"]
    text = rows[0]["text"]
    assert "ahmed@baytalhadaya.ae" not in text and "123 4567" not in text and "[EMAIL" in text
    assert "0501234567" not in rows[1]["text"]
    assert rows[0]["labels"]["items"][0] == {"description_en": "brass diya lamps", "quantity": 500.0, "unit": "pcs"}
    assert rows[0]["owner_quote_total_aed"] == 14800.0 and rows[1]["owner_quote_total_aed"] is None
    assert pilot_prepare.split_for("001") == pilot_prepare.split_for("001")  # stable split


async def test_pilot_suite_scores_in_shadow_mode(db_ready, tmp_path, monkeypatch):
    from eval.common import EvalContext
    from eval.suites import pilot

    raw, out = tmp_path / "raw.csv", tmp_path / "pilot.jsonl"
    write_raw(raw)
    pilot_prepare.prepare(raw, out)
    monkeypatch.setattr(pilot, "PILOT_FILE", out)
    result = await pilot.run(EvalContext(fast=False))
    m = result.metrics
    assert result.n == 2 and m["pilot_task_success_rate"] == 1.0
    assert m["pilot_items_f1"] >= 0.8 and m["pilot_incoterm_accuracy"] == 1.0
    assert "pilot_quote_delta_median_pct" in m and m["pilot_owner_minutes_median"] == 32.5
    async with session_scope() as db:
        sent = (
            await db.scalars(
                select(AuditEntry).where(AuditEntry.org_id == "pilot", AuditEntry.action.like("message.sent%"))
            )
        ).all()
    assert sent == []  # shadow mode: nothing sent
    monkeypatch.setattr(pilot, "PILOT_FILE", tmp_path / "missing.jsonl")
    empty = await pilot.run(EvalContext())
    assert empty.n == 0 and "No pilot data" in empty.notes[0]
