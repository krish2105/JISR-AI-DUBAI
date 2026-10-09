# Progress

Updated after every phase: what was built, what was tested, what is next.

## Phase 4 — Quote agent ✅ (2026-10-09)

**Built**
- **Deterministic bilingual RFQ parser** (`app/tools/rfq_rules.py`): quantities in many formats ("1.2k", number words, Arabic-Indic digits, "qty 120", "– 400 pcs", table rows), units (EN/AR), Incoterms (any case, C&F/CNF), GCC places → destination country (Indian origins ignored), deadlines (EN/AR), language incl. Gulf code-switching, buyer name.
- **Hybrid grounded extraction** (`app/tools/rfq.py`): model extraction reconciled against the text: quantities not written are dropped, unwritten Incoterms replaced, gaps filled, everything reported; rules-only fallback when the model fails.
- **Live FX** (`app/tools/fx.py`): ECB USD/INR via Frankfurter × CBUAE peg 3.6725, 6 h cache, stale fallback flagged; every quote stores rate, source, rate date and fetch time. Fixed labelled demo rate for tests/offline/replay.
- **Pricing v2** (`app/tools/pricing.py`): Incoterm scope table with separate charge lines (inland, export clearance, ocean freight by CBM, insurance, destination delivery, import clearance, import duty from the tariff master), volume tiers, owner margin floor never crossed automatically, pricing flags. Catalogue matching by product nouns (fixed "brass trays priced as lamps").
- **Pricing policies**: P-MARGIN-001, P-DISC-001, P-PRICE-001 (flags reach the owner with the rule and reason).
- Data `synthetic-v3`: 30 hand-written held-out enquiries; 46 unanswerable country labels fixed.
- Dashboard: quote shows Incoterm, charge lines, FX rate with date, review flags.

**Tested** (real output; report commit `dfd45fe`, profile `fake` = deterministic parser)
- `make test` → **179 passed** (parser formats/fields, buyer-facing description cleanliness, grounding drops hallucinated quantities, model-failure fallback, fixed and live FX incl. stale fallback (mocked network), every Incoterm's charges add up, margin floor and discount tiers, unpriced flag, pricing policy trigger/non-trigger).
- `make eval` → **Gate: PASSED**. Extraction F1 on **hand-written held-out: 0.976** (first shot 0.970, DECISIONS Q9); template test split 1.000 (overstates real accuracy). **E2E task success 1.000** (was 0.757). Pricing invariants across all Incoterms 1.000. Security gates unchanged (all pass).
- Browser: CIF quote with live ECB-based FX (1 INR = 0.037967 AED, 2026-10-09) and four charge lines; a dangling-bracket description bug was found there and fixed.

**Known gaps (planned)**
- Real-model extraction is untested until an API key is added (`--profile prod` / `dev`); the grounding layer is ready for it.
- Hand-written misses kept unfixed: numbered lists ("1) … – 400 pcs"), pipe tables, a single Arabic greeting word in an English message.
- Logistics costs are demo estimates; replace with forwarder quotes before quoting real buyers.
- Duty is shown before any CEPA preference: the CEPA analysis comes in Phase 5.

**Next: Phase 5, knowledge base + CEPA Duty + Docs agents** (5a–5f): tariff tree and rules-of-origin index from the official files, Arabic analyser, hybrid retrieval + RRF + reranker, agentic RAG with claim-level grounding, corrective loop, a hand-built retrieval evaluation set.

## Phase 3 — Security core ✅ (2026-10-09)

**Built**
- **Text normalisation** (`app/security/normalize.py`): detection views that undo "i g n o r e", "upd8 b@nk", zero-width and full-width characters, and canonicalise Arabic (alef/ya/ta marbuta, diacritics, Arabic-Indic digits). Reused by the Phase 5 Arabic analyser.
- **Injection guard v1** (`injection_guard.py`): bilingual rules for 7 categories (instruction override, prompt/secret exfiltration, bank change, payment pressure, payment status, approval bypass, hidden instructions in attachments / file names / metadata / HTML comments), with **evidence per flag** shown in the dashboard timeline.
- **LLM classifier layer** (`classifier.py`, `fast` role): confident findings are added to the rule flags; failure falls back to rules (recorded in the trace).
- **Redactor v1**: names after honorifics (EN/AR), PO box, Emirates ID, TRN, GSTIN, PAN, bank accounts, Luhn-checked cards, Arabic-Indic and bracketed phones; HS codes kept; token map in memory only.
- **Router PII tripwire**: requests still containing an email, IBAN, Emirates ID, TRN, GSTIN or card are refused (fail closed).
- Payment-status fraud ("mark as paid") → `mark_payment_received` → blocked by P-BANK-001.
- Datasets `synthetic-v2`: `adversarial_dev` (42 dev attacks + 22 benign lookalikes) and `pii` (90 labelled cases); optional founder hold-out scored separately.
- Demo cassette re-recorded (now includes the classifier call).

**Tested** (real output; report commit `70ee581`, profile `fake` = rule layer only)
- `make test` → **147 passed**; `make test-postgres` → **146 passed** (before the last harness test was added). New: every dev attack flagged with the right categories, every lookalike not flagged, every redaction type, business data kept, Luhn, tripwire per identifier type, **captured-call test (30 full runs, no PII in any model request)**, classifier adds/falls back, payment-status blocked.
- `make eval` → **Gate: PASSED**. Held-out attacks: **first shot 29/30 (0.967)**; after fixing the gap (secrets requested as a question) via new dev cases: **30/30**. FPR on 300 enquiries **0.000** (was 0.007) · hard negatives **0.000** (was 0.200) · unflagged attacks reaching the inbox **0.000** (was 0.467) · **attack success 0.000** · PII-case recall **1.000** · business data kept **1.000**.
- Phase 3 targets are now **hard gates** (DECISIONS S7). A false "Gate: FAILED" from latency timing noise (0.041 s → 0.095 s) was caught in the committed report and fixed: timings keep their absolute limit but are exempt from the regression rule (S8).
- Browser: the hostile demo shows flags with evidence ("ignore previous instructions", "update the beneficiary").

**Known gaps (planned)**
- Held-out independence is limited (same author; adv_008 now seen) → **founder hold-out recommended** (`data/synthetic/founder_holdout.jsonl`, see its README).
- The classifier layer has only run offline with scripted answers; its real behaviour (Haiku 5.5) is measured once an API key is added (`--profile prod`).
- Person names without an honorific (a bare signature "Rahul") are not masked; hard identifiers are still covered by the tripwire. Revisit with real pilot data.

**Next: Phase 4, Quote agent**
- Real RFQ extraction on the LLM router (Claude Sonnet 5.5 in prod; free tier on synthetic data in dev), Incoterm cost lines, live FX with source and timestamp, margin floors → target extraction F1 ≥ 0.90 on the test split (then a hard gate).

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
