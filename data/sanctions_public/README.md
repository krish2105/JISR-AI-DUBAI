# Public sanctions lists

`make sanctions` downloads the **UN Security Council Consolidated List** (XML) from the official UN host into
`un_consolidated.xml`, with its SHA-256 and fetch time in `un_consolidated.status.json` (both git-ignored).

Used only for the Buyer Trust **signal** ("possible name match, for review"), never as a verdict or as legal
sanctions screening. Without the file the signal says "list not loaded", so silence is never mistaken for screening.
Matching: names normalised (accents, legal suffixes such as LLC/FZE removed, word order ignored), similarity
≥ 0.92 (`backend/app/tools/buyer_trust.py`). Re-download regularly; the list changes.
