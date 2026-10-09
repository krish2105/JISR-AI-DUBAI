# Knowledge-base sources (official documents only)

- **Manifest:** `sources.csv` (title, issuing body, official URL, document date, local file, download mode, notes)
- **Download / refresh:** `python3 scripts/download_kb_sources.py` (add `--force` to refetch everything)
- **Provenance report:** `download_status.csv` (bytes, SHA-256, final URL, fetch time for every file)
- **Review and corrections:** `SOURCES_REVIEW.md` (read this before using a source)

Originals live in `downloads/` and `references/` and are git-ignored. Only the metadata above is committed.

Rules:
- Only official sources (government, treaty text, ICC). Vendor blogs may be used to *find* a document, never as a source.
- The CEPA **Final Agreement** (UAE Ministry of Economy and Tourism, 2022-03-28) is the primary treaty text.
  The Abu Dhabi Customs copy is pre-final and must never be cited.
- Every fact Jisr states cites the document and its date, or is flagged "needs human check".
