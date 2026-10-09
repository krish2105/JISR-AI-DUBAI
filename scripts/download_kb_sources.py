"""
download_kb_sources.py — Fetch the official knowledge-base sources listed in data/kb_sources/sources.csv.

Why this file exists:
    Jisr may only state tariff, origin and procedure facts that come from official documents,
    with the document's date. This script downloads exactly the URLs in the manifest (nothing
    else), checks each file really is what the manifest says (a PDF is a PDF, an XLSX is an
    XLSX, a page is HTML), and records provenance for every source:
        data/kb_sources/download_status.csv
            local_filename, status, http_status, content_type, bytes, sha256, final_url, fetched_at_utc, error
    The SHA-256 lets anyone prove later that the indexed document is the original, unchanged.

Usage (from the repo root):
    python3 scripts/download_kb_sources.py            # download everything missing
    python3 scripts/download_kb_sources.py --force    # re-download everything

Download modes in the manifest:
    file      a binary original (PDF/XLSX), downloaded and type-checked
    page      an official HTML page snapshot
    snapshot  captured by hand (e.g. via a browser) because the site blocks scripts; only checked for presence
    manual    must be downloaded by a person (e.g. host unreachable from this network); reported, not fetched

Downloaded originals are git-ignored; the manifest and the status report are committed.
"""

import argparse
import csv
import hashlib
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

KB_DIR = Path(__file__).resolve().parents[1] / "data" / "kb_sources"
MANIFEST = KB_DIR / "sources.csv"
STATUS = KB_DIR / "download_status.csv"

# Only official hosts may be fetched (defence against a tampered manifest).
ALLOWED_HOST_SUFFIXES = (".gov.ae", ".gov.in", "iccwbo.org")
USER_AGENT = "Mozilla/5.0 (JisrAI knowledge-base builder; official-sources only)"
TIMEOUT_SECONDS = 60
MAX_BYTES = 150 * 1024 * 1024        # refuse anything over 150 MB
STATUS_FIELDS = ["local_filename", "status", "http_status", "content_type", "bytes", "sha256",
                 "final_url", "fetched_at_utc", "error"]


def host_allowed(url: str) -> bool:
    """True if the URL is https and its host ends with an allowed official suffix."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(host == s.lstrip(".") or host.endswith(s) for s in ALLOWED_HOST_SUFFIXES)


def sniff_kind(data: bytes, content_type: str) -> str:
    """Identify the downloaded bytes from their first bytes (more reliable than the header)."""
    head = data[:1024].lstrip().lower()
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "zip/xlsx"
    if head.startswith((b"<!doctype html", b"<html")) or b"<html" in head or "html" in content_type.lower():
        return "html"
    return "unknown"


def expected_kind(local_filename: str, mode: str) -> str:
    """What the manifest says we should receive."""
    if mode == "page":
        return "html"
    suffix = Path(local_filename).suffix.lower()
    return {".pdf": "pdf", ".xlsx": "zip/xlsx"}.get(suffix, "unknown")


def fetch(url: str) -> tuple[bytes, int, str, str]:
    """GET a URL; returns (bytes, http status, content type, final URL after redirects)."""
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        final_url = response.geturl()
        if not host_allowed(final_url):
            raise ValueError(f"redirected to a non-official host: {final_url}")
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("file larger than the 150 MB safety limit")
        return data, getattr(response, "status", 200), response.headers.get("Content-Type", ""), final_url


def fetch_with_curl(url: str) -> tuple[bytes, int, str, str]:
    """Fallback for servers Python's TLS stack rejects (e.g. ICEGATE omits its intermediate
    certificate) or that block non-browser clients. curl on macOS verifies against the
    system trust store, so certificate checking stays ON. We never pass -k/--insecure."""
    proc = subprocess.run(
        ["curl", "-sSL", "--fail", "--max-time", "120", "--max-filesize", str(MAX_BYTES),
         "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/17.0",
         "-w", "\n%{http_code} %{url_effective} %{content_type}", url],
        capture_output=True, timeout=150,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed: {proc.stderr.decode(errors='replace').strip()}")
    body, _, meta = proc.stdout.rpartition(b"\n")
    code, final_url, *ctype = meta.decode().split(" ")
    if not host_allowed(final_url):
        raise ValueError(f"redirected to a non-official host: {final_url}")
    return body, int(code), " ".join(ctype), final_url


def download_row(row: dict, force: bool) -> dict:
    """Download one manifest row and return its status record (never raises)."""
    name, url, mode = row["local_filename"].strip(), row["url"].strip(), row["download_mode"].strip().lower()
    result = {f: "" for f in STATUS_FIELDS} | {"local_filename": name, "status": "FAILED"}
    try:
        target = (KB_DIR / name).resolve()
        if KB_DIR.resolve() not in target.parents:
            raise ValueError("output path escapes data/kb_sources")
        if mode in ("snapshot", "manual"):
            # Not fetched by this script: just report whether a person has put the file in place.
            if target.exists():
                data = target.read_bytes()
                result.update(status=f"{mode.upper()}_PRESENT", bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            else:
                result.update(status=f"{mode.upper()}_NEEDED", error=row.get("notes", "")[-160:])
            return result
        if not host_allowed(url):
            raise ValueError(f"URL is not an allowed official https host: {url}")
        if target.exists() and not force:
            data = target.read_bytes()
            result.update(status="ALREADY_PRESENT", bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            return result

        last_error: Exception | None = None
        for attempt in range(2):                        # one retry for flaky government servers
            try:
                data, http_status, content_type, final_url = fetch(url)
                break
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                last_error = exc
                time.sleep(2)
        else:
            # Python could not fetch it: retry once with curl (still certificate-verified).
            try:
                data, http_status, content_type, final_url = fetch_with_curl(url)
            except Exception as curl_exc:
                raise RuntimeError(f"{last_error}; curl fallback: {curl_exc}") from curl_exc

        got, want = sniff_kind(data, content_type), expected_kind(name, mode)
        if got != want:
            raise ValueError(f"expected {want} but received {got} ({content_type or 'no content type'}, "
                             f"{len(data)} bytes) - may need a manual download")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        result.update(status="DOWNLOADED", http_status=http_status, content_type=content_type, bytes=len(data),
                      sha256=hashlib.sha256(data).hexdigest(), final_url=final_url,
                      fetched_at_utc=datetime.now(UTC).isoformat(timespec="seconds"))
    except Exception as exc:                            # record and continue with the next source
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def previous_status() -> dict[str, dict]:
    """Last run's report, so files already present keep their original fetch provenance."""
    if not STATUS.exists():
        return {}
    return {r["local_filename"]: r for r in csv.DictReader(STATUS.open(encoding="utf-8", newline=""))}


def main() -> int:
    """Download every manifest row, print a summary, write the status CSV."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--force", action="store_true", help="re-download files that already exist")
    args = parser.parse_args()

    rows = list(csv.DictReader(MANIFEST.open(encoding="utf-8-sig", newline="")))
    before = previous_status()
    results = []
    for i, row in enumerate(rows, 1):
        res = download_row(row, args.force)
        old = before.get(res["local_filename"], {})
        if res["status"] == "ALREADY_PRESENT" and old.get("sha256") == res["sha256"]:
            # Same bytes as when we fetched them: keep the original provenance fields.
            res.update({k: old.get(k, "") for k in ("http_status", "content_type", "final_url", "fetched_at_utc")})
        results.append(res)
        detail = f"{int(res['bytes']):>11,} B" if res["bytes"] != "" else res["error"]
        print(f"[{i:02d}/{len(rows)}] {res['status']:<15} {res['local_filename']}  {detail}")

    with STATUS.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=STATUS_FIELDS)
        writer.writeheader()
        writer.writerows(results)
    ok = sum(r["status"] in ("DOWNLOADED", "ALREADY_PRESENT", "SNAPSHOT_PRESENT", "MANUAL_PRESENT") for r in results)
    print(f"\n{ok}/{len(rows)} sources available. Report: {STATUS.relative_to(KB_DIR.parents[1])}")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
