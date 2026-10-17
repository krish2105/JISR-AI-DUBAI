"""
pilot_prepare.py — Turn the exporter's past enquiries into an anonymised, labelled pilot set (Phase 18).

Input  (never committed):  data/pilot_raw/enquiries.csv   with columns
    id, received_at, channel, language, text,
    owner_items            "brass diya lamps:500|cotton table runners:200"   (what the owner says was asked)
    owner_incoterm         FOB / CIF / ... (optional)
    owner_quote_total_aed  what the owner actually quoted (optional)
    owner_minutes          how long the owner spent on this enquiry by hand (optional; the baseline)
Output (never committed):  data/pilot/enquiries.jsonl  in the same shape as data/synthetic/enquiries.jsonl, with the
    text replaced by the Jisr redactor's output (emails, phones, IBANs, IDs, names after honorifics...), split into
    dev (30 %) and test (70 %) by a hash of the id, so tuning on dev never touches test (DECISIONS K13 discipline).

Usage:  uv --directory backend run python ../scripts/pilot_prepare.py [--raw PATH] [--out PATH]
"""

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.security.redactor import find_high_risk_pii, redact  # noqa: E402


def items(spec: str) -> list[dict]:
    out = []
    for part in (spec or "").split("|"):
        if ":" in part:
            name, qty = part.rsplit(":", 1)
            try:
                out.append({"description_en": name.strip(), "quantity": float(qty), "unit": "pcs"})
            except ValueError:
                continue
    return out


def split_for(row_id: str) -> str:
    return "dev" if int(hashlib.sha256(row_id.encode()).hexdigest(), 16) % 10 < 3 else "test"


def prepare(raw: Path, out: Path) -> dict:
    counts: Counter = Counter()
    rows, leaks = [], []
    with raw.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            red = redact(row["text"])
            counts.update(red.counts)
            if find_high_risk_pii(red.text):  # fail closed: never write a leak
                leaks.append(row["id"])
                continue
            labels = {
                "items": items(row.get("owner_items", "")),
                "incoterm": (row.get("owner_incoterm") or None),
                "language": row.get("language") or "en",
                "buyer_country": "AE",
                "pii": [],
            }
            rows.append(
                {
                    "id": f"pilot_{row['id']}",
                    "split": split_for(row["id"]),
                    "channel": row.get("channel") or "whatsapp",
                    "language": labels["language"],
                    "text": red.text,
                    "labels": labels,
                    "received_at": row.get("received_at"),
                    "owner_minutes": float(row["owner_minutes"]) if row.get("owner_minutes") else None,
                    "owner_quote_total_aed": float(row["owner_quote_total_aed"])
                    if row.get("owner_quote_total_aed")
                    else None,
                }
            )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return {
        "rows": len(rows),
        "dev": sum(r["split"] == "dev" for r in rows),
        "test": sum(r["split"] == "test" for r in rows),
        "redactions": dict(counts),
        "refused_rows_with_leaks": leaks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "pilot_raw" / "enquiries.csv")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "pilot" / "enquiries.jsonl")
    args = parser.parse_args()
    if not args.raw.exists():
        sys.exit(f"Put the exported enquiries at {args.raw} (see docs/pilot/LABEL_SHEET.md).")
    print(json.dumps(prepare(args.raw, args.out), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
