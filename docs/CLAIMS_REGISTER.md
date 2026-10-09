# Claims register

Every number or fact used in the deck, video or report. **No claim goes into the pitch unless it has a
source or is our own measured data.** Status: `sourced` · `verify` · `own data` · `to collect`.

| # | Claim | Source | Date | Status |
|---|---|---|---|---|
| 1 | India–UAE bilateral trade USD 101.25B in FY 2025-26, about two-thirds non-oil | Times of Oman / ANI | 21 May 2026 | sourced |
| 2 | Target USD 200B bilateral trade by 2032 | Times of Oman / ANI | 21 May 2026 | sourced |
| 3 | India–UAE CEPA in force since 1 May 2022 | Times of Oman / ANI; PwC Middle East tax news | 21 May 2026 / 23 May 2022 | sourced |
| 4 | CEPA origin: wholly obtained, or the Annex 3B product-specific rule, typically CTH/CTSH + VA 40% on an FOB basis (= 35% on an Ex-Works basis; HS 71 FOB only); exceptions e.g. 7102 diamonds VA 6%, Ex Ch. 87 vehicles VA 45%, many agricultural chapters WO | CEPA Final Agreement, Art. 3.2 and Annex 3B Rule 1 + Table 1 (UAE MoET PDF) | 2022-03-28 (signed 2022-02-18, in force 2022-05-01) | **sourced** (treaty text). The playbook's 35% = Ex-Works equivalent. |
| 5 | UAE import duty 5% on the demo goods (HS 4420, 6214, 6302, 7419, 9405) without preference | Dubai Customs Integrated Customs Tariff master (12-digit XLSX), `DutyPercentage` | live master, fetched 2026-10-09 (see download_status.csv) | **sourced**; re-check per SKU before use |
| 6 | Common shipment-delaying document mistakes (HS mismatch, missing origin certificate, missing export-tax declaration, direct-consignment gaps) | Vendor guide (IncorpX) | n/a | **verify** with a customs broker |
| 7 | WhatsApp per-message pricing since July 2025; AED billing from April 2026 | Meta developer pricing page | ~Oct 2025 | **verify** current rates |
| 8 | Dubai AI Seal is free to apply; requires a Dubai licence | Dubai Media Office | May 2025 | sourced; re-check dub.ai |
| 9 | Championship: four categories, AED 550,000 per category winner, extra AED 1M for AI Agent of the Year; finalists must demo a working agent live | Dubai Chamber of Digital Economy coverage (tbreak, OB Gulf guide) | Oct 2026 | sourced; confirm on dubaichamberdigital.com |
| 10 | UAE dirham pegged to USD at 3.6725 AED/USD since 1997 (used for INR→AED) | The National (2024-11-22); Wikipedia (UAE dirham) | 2024 | **verify** on centralbank.ae |
| 11 | ECB reference rate USD/INR 96.78 on 2026-10-08 (via Frankfurter API) | api.frankfurter.dev | 2026-10-08 | sourced (live; each quote stores its own rate, source and date) |
| 12 | Logistics costs in the demo profile (freight AED/CBM, clearance, insurance %) | Demo estimates | n/a | **own estimate** — replace with forwarder quotes before any pitch use |
| 13 | RFQ extraction F1 0.970 on 30 hand-written held-out enquiries (fake profile = deterministic parser) | docs/EVAL_REPORT.md | 2026-10-09 | own data (synthetic, small n=30; not real buyers) |
| 15 | HS heading from a seller's phrase: top-1 0.868, top-3 0.962 (53 test phrases, EN+AR; 0.733 top-1 on goods the search glossary does not cover) | `backend/eval/results/retrieval_20261009-175554.json` | 2026-10-09 | own data; labels by Claude Code, **advisor review pending**; always shown with "needs human check" |
| 16 | Every claim in a CEPA answer cites an official passage and every number in it appears verbatim in that passage (grounded 1.000, numeric 1.000 on 92 test questions) | same | 2026-10-09 | own data (first-shot run before a grounding fix: 0.367; DECISIONS K13) |
| 17 | Says "I don't know / needs human check" on 75% of off-topic questions; refuses 2.5% of answerable ones | same | 2026-10-09 | own data; the weak side, do not overstate |
| 18 | Duty saving shown only as "up to" the MFN duty (5% on the demo goods), because the official UAE schedule (Annex 2B) is not available | data/kb_sources/SOURCES_REVIEW.md | 2026-10-09 | sourced gap; obtain Annex 2B before claiming a real saving |
| 14 | Pilot results (minutes per quote, follow-up rate, errors caught, duty savings identified) | Jisr Impact Ledger | after pilot | to collect |
