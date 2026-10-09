# Progress

Updated after every phase: what was built, what was tested, what is next.

## Phase 2 — Data and evaluation first ✅ (2026-10-09)

**Built**
- **Synthetic datasets** (`data/synthetic/`, `synthetic-v1`, seeded and byte-reproducible, labels by construction, datasheet in its README):
  300 enquiries (150 EN / 105 AR / 45 mixed; easy / medium / hard incl. "1.2k", number words, Arabic-Indic digits; 10 hard negatives; 180/60/60 stratified splits),
  30 hand-written attacks (override, exfiltration, bank change, payment pressure, approval bypass, hidden instructions in attachments / file names / metadata; obfuscated, Arabic, code-switched),
  40 export document sets (20 clean, 20 with planted mistakes, 9 mistake types).
- **Evaluation harness** (`backend/eval/`): six suites (extraction, security, redteam, docs, pricing, e2e), a results contract (git SHA, profile, models, dataset version, split), a generated `docs/EVAL_REPORT.md` with slices and error analysis, `thresholds.yaml` (hard gates + phase targets), a regression gate vs `baseline.json`.
- `make data`, `make eval`, `make eval-fast`, `make eval-gate`, `make eval-baseline`, `make test-postgres`.
- **CI workflow** `.github/workflows/ci.yml`: backend lint + tests on SQLite and Postgres 17/pgvector, frontend tsc/lint/build, eval-fast on PRs and full eval nightly, then the gate.
- Refactor: `app/tools/rfq.py`, `app/tools/pricing.py` (used by the Quote agent AND the eval), `app/tools/doc_checker.py` (frozen contract, stub).

**Tested** (real output; numbers from `backend/eval/results/`, commit `372e353`, profile `fake`)
- `make test` → **65 passed** (11 new harness tests: dataset reproducibility and integrity, bilingual deadline parsing, matching, scoring, gate logic). `make test-postgres` → **65 passed on Postgres 17 + pgvector**.
- `make eval` → **GATE: PASSED**. Hard gates: PII redaction 1.000 · quantity preservation 1.000 · **attack success rate 0.000** · pricing invariants 1.000 · clean-set FPR 0.000 · crash rate 0.000 · p95 latency 0.03 s.
- Honest baseline (targets, not yet met): extraction F1 **0.766** (target 0.90, P4) · injection detection recall **0.533** (target 1.0, P3) · hard-negative FPR 0.200 · unflagged attacks reaching the inbox 0.467 · doc-issue recall **0.000** (stub, P6) · e2e task success **0.757** (P9).
- **Gate proven**: breaking the redactor and the Arabic extractor made `make eval-gate` exit 2 ("FAIL + REGRESSED"); restoring them made it pass.

**Found and fixed while building**
1. Label bug: Arabic deadline months were chosen independently of the gold label → deadlines are now structured labels generated from the same values as the EN and AR text.
2. Metric bug: `quantity_preservation` read 0.858 because "1.2k", number words and Arabic-Indic digits were compared as plain strings; rewritten on normalised standalone numbers → 1.000 (the redactor was fine).
3. Two local Postgres servers on this Mac occupy ports 5432 and 5433 → Docker DB moved to 55432.

**Known gaps (planned)**
- Main extraction errors (see report): bulleted item lists, GCC destinations outside the UAE, deadline formats → Phase 4 replaces the fake extractor with a real model and must reach F1 ≥ 0.90 on the test split.
- 14/30 attacks reach the inbox unflagged (obfuscation, approval bypass, hidden instructions, Arabic) → Phase 3. None succeeds: every outbound action still waits for a human.
- The adversarial set needs a founder review; the retrieval gold set (tariff/CEPA) is built by hand in Phase 5f.
- CI workflow is written but not yet running: the repo has no GitHub remote yet.

**Next: Phase 3, security core**
- Harden the redactor (names, addresses, Arabic-Indic digits, more account formats) with a captured-call test proving no PII reaches any model.
- Injection guard v1: normalisation against obfuscation, approval-bypass and hidden-instruction detectors, plus a classifier prompt on the `fast` role → targets: detection recall 1.0 on the 30 attacks, FPR ≤ 0.02, hard-negative FPR ≤ 0.10; then flip those thresholds to hard.

## Phase 1 — Vertical slice ✅ (2026-10-09)

**Built**
- **Contracts frozen** (`docs/CONTRACTS.md`): `RunEvent` (13 kinds), REST routes, `RunState`.
- **Agent graph** (LangGraph): ingest → guard → supervisor → quote → duty → docs → trust → outreach → governance, with a conditional shortcut to governance for bank-change attacks. Quote does RFQ extraction through the LLM router plus stub pricing. Outreach drafts EN/AR through the router. Duty, docs and trust are honest placeholders marked `stub`.
- **Governance v0**: `policies.yaml` + deterministic `policy_engine.py` (P-BANK-001 block, P-OUT-001 approval, P-INJ-001 high risk; strongest effect wins; safe default). Approval queue with approve/edit/reject. **Hash-chained audit log** per org with `verify_chain`. A simulated channel "sends" approved messages.
- **Security v0**: redactor (email/phone/IBAN tokens; raw messages never stored) and injection guard (EN + AR patterns). Hardened in Phase 3.
- **Live events**: persisted events, an in-process bus, an SSE endpoint with resume (`?after=` and `Last-Event-ID`).
- **Offline replay**: `replay` LLM profile + `make record` cassette. The whole pipeline (governance, approvals, audit) still runs for real; only model answers are replayed.
- **Dashboard** (Next.js 16): pearl light / midnight dark tokens with a no-flash theme toggle, `/en` + `/ar` static routes with true RTL, the live 2D agent graph (mirrors in Arabic), timeline with stub badges, counters, quote table, inline approval card, `/approvals` inbox, `/audit` with chain-verified badge, landing page with the bridge illustration (static fallback for the Phase 7 3D hero).
- `make demo`, `make replay`, `make record`, `make build`.

**Tested** (real output)
- `make test` → backend `54 passed` (policy trigger/non-trigger per rule, audit tamper + delete detection, per-org chains, UTC timestamps, redaction, guard on EN/AR/hostile samples, full slice EN/AR/hostile, approve/reject/edit, no double decision, cross-org 404s, SSE incl. resume, replay identical outputs, real data never recorded). Clean with `-W error::ResourceWarning`. Frontend `tsc` and `eslint` clean.
- `npm run build` → all pages prerendered statically for `en` and `ar`.
- **Browser check** (in-app browser): English run → graph lights up → quote → approve → "sent via simulator" → `done`. Arabic + dark theme hostile run → governance node red, attack shortcut highlighted, "3 risks caught", blocked. Audit page "Chain verified · 8 entries". Theme persists across reloads via cookie.
- Offline: API with `LLM_PROFILE=replay` ran all three samples from the cassette (`replay:fake-worker`), hostile still blocked.

**Bugs found and fixed in the browser check**
1. Timeline showed "+19800s": SQLite returned naive datetimes, read by the browser as IST. Fixed with a `UTCDateTime` column type (+ test).
2. Quote line total ≠ unit × qty (11,968.20 vs 23.94 × 500). Fixed: round the unit price first (+ to-the-cent test). Exactly the kind of error the Phase 6 consistency checker must catch.
3. SQLite "database is locked" when governance emitted events inside its own write transaction. Fixed: commit first, then emit; WAL mode.
4. React dev warning for the theme script. Fixed: Client Component `InlineScript` per the Next 16 docs.

**Known gaps (planned)**
- Agent "why" explanations are English even in the Arabic UI (rendered with `dir="auto"`). Bilingual explanations come with the real agents (Phases 4–9).
- The cassette currently holds `fake` answers. Run `LLM_PROFILE=prod make record` once an Anthropic key is in `.env`.
- No auth yet (demo org via `X-Org-Id`); real auth before the pilot (Phase 10).
- Postgres path tested in Phase 0 (`make up`), not yet with the Phase 1 tables; it is exercised in Phase 2.

**Next: Phase 2, data and eval first**
- Synthetic generator: 300 enquiries (EN/AR/mixed), 30 adversarial, 40 document sets with seeded mistakes, labels.
- Golden set + `make eval` harness printing a metrics table (and the CI regression gate skeleton).
