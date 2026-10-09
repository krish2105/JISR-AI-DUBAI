# Knowledge-base source review (2026-10-09)

Review of the source pack `india_uae_trade_kb.zip`. It contained a 20-row manifest, a downloader and a README.
Its own README says it was prepared **without network access**, so every URL, date and claim was checked here
against the live official sites. Files: `sources.csv` (manifest, now 21 rows), `download_status.csv`
(size, SHA-256, final URL and fetch time for every file). Originals are stored locally and git-ignored.

## Result

| Status | Count | Notes |
|---|---|---|
| Downloaded and type-checked | 19 | Each PDF's first page matches the manifest title and date; XLSX verified |
| Snapshot (browser) | 1 | UAE Cabinet Resolution 119/2024: the site returns 403 to all scripts, incl. its PDF download |
| Manual download needed | 1 | DGFT CoO "Relevant Documents" index: host unreachable from this network and the browser |

## Corrections to the source pack

1. **CEPA text: use the FINAL agreement, not the Abu Dhabi Customs copy.**
   - The manifest's CEPA PDF (adcustoms.gov.ae, created 2022-01-11, edited 2022-04-01) is a **pre-final text**.
     Annex 3B contains negotiator notes absent from the final text: p51 *"(UAE suggests to change the criteria for WO…)"* (Chapter 4)
     and p55 *"(UAE wants specific operations)"* (Chapter 62).
   - **Primary source now:** UAE Ministry of Economy and Tourism, *Final Agreement*,
     https://www.moet.gov.ae/documents/20121/1347101/Final+Agreement_UAE+India+CEPA.pdf (PDF dated 2022-03-28, 320 pp).
   - A normalised comparison of Annex 3B shows **identical rule values** in both copies; the differences are the two notes,
     punctuation and line wrapping. The pre-final copy is kept for cross-checking only and must never be cited.
2. **CEPA FAQ:** the commerce.gov.in URL in the pack returns 404 since the 2026 site redesign. The same Department of Commerce
   FAQ is used from the Noida SEZ (Ministry of Commerce) site: https://www.nsez.gov.in/Resources/Trade/FAQs%20on%20CEPA.pdf.
   It is secondary only; the treaty text prevails.
3. **ICEGATE (3 files):** the server omits its TLS intermediate certificate, so Python's TLS check failed. The files were fetched
   with curl using the macOS trust store, so **certificate verification stayed on**.

## What the sources establish (for Phase 5 and the claims register)

- **Annex 3B, Rule 1 (Final Agreement, p. 50):** value addition (VA) percentages are on an **FOB basis**. On an **Ex-Works basis they are
  5 percentage points lower** ("40% value addition on the basis of FOB value and 35% … Ex Works"). HS 71 must use FOB.
  The playbook's "35%" is therefore the Ex-Works equivalent, not an error. The duty optimiser must know the price basis.
- **Rule types (Annex 3B Table 1, chapters 1–97):** WO (wholly obtained), CC, CTH, CTSH, SO, VA x%, often combined
  (e.g. "CTH + VA 40%"). Notable exceptions: 7102 diamonds CTSH + VA 6%; Ex Ch. 87 vehicles CTH + VA 45%.
- **Demo product rules:** Ch. 44 wood articles CTSH + VA 40% · Ch. 62 apparel CTH + VA 40% · Ch. 63 made-up textiles
  CTH + VA 40% · Ch. 94 lamps CTH + VA 40%.
- **Article 3.2:** origin = wholly obtained (Art. 3.3) **or** sufficient working per the Annex 3B PSR. Two VA computation methods are allowed.
- **UAE tariff master (Dubai Customs XLSX):** 13,449 lines with old 8-digit → new 12-digit codes, **Arabic and English descriptions**,
  unit and `DutyPercentage`. The demo goods (4420, 6214, 6302, 7419, 9405) are at **5%**.
- **Data-quality note:** line 94052100 has an Arabic description of table/desk/bedside lamps but an English description copied
  from the chandelier line. Arabic prevails (Cabinet Resolution disclaimer). Retrieval must search both languages and show
  the original text.
- **Classification ambiguity worth demoing:** "brass diya lamps" could fall under 9405 (lamps, Ch. 94 CTH + VA 40%) or 7419
  (articles of copper, Ch. 74 rule). This is exactly the case for top-3 HS suggestions with citations and a human check.

## Still to do

- Download the DGFT CoO relevant-documents index from an Indian network (`download_mode=manual`).
- Optionally save the EN and AR PDFs of Cabinet Resolution 119/2024 manually from uaelegislation.gov.ae.
- Optional: India's Commerce Ministry chapter-by-chapter CEPA PDFs (dated 2022-03-27) as an Indian-side cross-check of Annex 3B.
- ICC Incoterms: only the landing pages were captured; the free PDFs sit behind ICC's download flow (manual).
