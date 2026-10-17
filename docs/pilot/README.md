# Pilot kit (Phase 18)

The pilot turns "up to" and "estimated" into measured numbers. It runs in **shadow mode** first: every real enquiry
also goes through Jisr, the owner compares, and nothing Jisr drafts is ever sent.

| Step | Who | What | Output |
|---|---|---|---|
| 1 | Founder + owner | Baseline interview (30 min) | `BASELINE.md` filled in |
| 2 | Owner | Export 30–50 past enquiries to `data/pilot_raw/enquiries.csv` and label them (`LABEL_SHEET.md`) | the CSV (never committed) |
| 3 | Founder | `make pilot` — anonymise with the Jisr redactor, split dev/test, run the `pilot` eval in shadow mode | `data/pilot/enquiries.jsonl`, `backend/eval/results/pilot_*.json` |
| 4 | Adviser | Review 50 HS labels, 30 retrieval gold items and the CEPA rule mapping | `ADVISOR_REVIEW.md` signed |
| 5 | Founder | 5 interviews (exporters, Dubai buyers/forwarders); ask for letters of intent | `INTERVIEWS.md`, LOIs (`LOI_TEMPLATE.md`) |
| 6 | Founder | Write the report from the result files only | `PILOT_REPORT.md` |

Rules: real data stays in `data/pilot_raw/` and `data/pilot/` (both git-ignored); only anonymised text ever reaches a
model, and only a paid no-training provider (DECISIONS C1/C3); tune only on the `dev` split; report the `test` split.
