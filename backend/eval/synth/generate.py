"""
generate.py — Write the synthetic evaluation datasets to data/synthetic/ (deterministic).

Usage (from the repo root):  make data
                       or:  uv --directory backend run python -m eval.synth.generate

Outputs:
    data/synthetic/enquiries.jsonl    300 labelled buyer enquiries (EN / AR / mixed)
    data/synthetic/adversarial.jsonl  30 hand-written attacks (red-team)
    data/synthetic/docsets.jsonl      40 export document sets, 20 with planted mistakes
    data/synthetic/adversarial_dev.jsonl  40 dev attacks + 20 benign lookalikes (guard development only)
    data/synthetic/pii.jsonl          90 messages labelled with personal data to hide and business data to keep
    data/synthetic/enquiries_handwritten.jsonl  30 hand-written enquiries (test only; never used for tuning)
    data/synthetic/MANIFEST.json      dataset version, seed, counts and SHA-256 of each file

Same seed -> byte-identical files, so every eval run is comparable.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

from eval.synth.adversarial import generate_adversarial
from eval.synth.adversarial_dev import generate_adversarial_dev
from eval.synth.docsets import generate_docsets
from eval.synth.enquiries import generate_enquiries
from eval.synth.enquiries_handwritten import generate_handwritten
from eval.synth.pii import generate_pii

# v2 (Phase 3): + adversarial_dev, + pii. v3 (Phase 4): + enquiries_handwritten; enquiry country labels set to
# None where no place is written (46 rows; labels must be answerable from the text).
DATASET_VERSION = "synthetic-v3"
SEED = 20261009
OUT = Path(__file__).resolve().parents[3] / "data" / "synthetic"


def write_jsonl(path: Path, rows: list[dict]) -> str:
    """Write one JSON object per line (UTF-8, Arabic kept readable); return the file's SHA-256."""
    text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    """Generate all datasets and the manifest; print a short summary."""
    OUT.mkdir(parents=True, exist_ok=True)
    datasets = {
        "enquiries": generate_enquiries(SEED),
        "adversarial": generate_adversarial(),
        "docsets": generate_docsets(SEED),
        "adversarial_dev": generate_adversarial_dev(),
        "pii": generate_pii(SEED),
        "enquiries_handwritten": generate_handwritten(),
    }
    manifest = {"version": DATASET_VERSION, "seed": SEED, "files": {}}
    for name, rows in datasets.items():
        sha = write_jsonl(OUT / f"{name}.jsonl", rows)
        manifest["files"][f"{name}.jsonl"] = {
            "rows": len(rows),
            "sha256": sha,
            "by_split": dict(Counter(r["split"] for r in rows)),
            "by_language": dict(Counter(r.get("language", "n/a") for r in rows)),
        }
        print(f"{name:<12} {len(rows):>4} rows  splits={manifest['files'][f'{name}.jsonl']['by_split']}")
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({DATASET_VERSION})")


if __name__ == "__main__":
    main()
