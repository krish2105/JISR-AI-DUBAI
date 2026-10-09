"""
download_sanctions.py — Fetch the UN Security Council Consolidated List (XML) for the Buyer Trust signal.

Why this file exists:
    The Buyer Trust tool compares the buyer's name with the official UN list and raises a "possible match, for
    review" signal. The list changes often, so it is fetched on demand, never committed, and stored with its
    SHA-256 and fetch time. Only the official UN host is used.

Usage (from the repo root):   make sanctions      or      python3 scripts/download_sanctions.py
Output: data/sanctions_public/un_consolidated.xml + un_consolidated.status.json (git-ignored)
"""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "sanctions_public"
OUT = OUT_DIR / "un_consolidated.xml"


def main() -> int:
    """Download, check it is the UN XML, and record provenance."""
    request = Request(URL, headers={"User-Agent": "Jisr-AI/0.1 (sanctions signal; contact: owner)"})
    with urlopen(request, timeout=120) as response:          # TLS certificate verification stays on
        body = response.read()
        final_url = response.geturl()
    if b"<CONSOLIDATED_LIST" not in body[:2000]:
        print("Unexpected content: not the UN consolidated list XML", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(body)
    status = {"url": URL, "final_url": final_url, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
              "fetched_at_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    (OUT_DIR / "un_consolidated.status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(f"Saved {OUT} ({len(body):,} bytes, sha256 {status['sha256'][:12]}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
