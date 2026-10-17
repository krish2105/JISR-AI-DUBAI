# Progress

Updated after every phase: what was built, what was tested, what is next.

> **Next plan:** `docs/PLAN_95.md` (phases 13–21: auth + RBAC, deploy + Claude, SaaS core, UI/UX, outputs, pilot,
> business, hardening, submission v2). Current honest scores and the full gap list: `docs/SCORECARD.md`.


## Phase 16 (part) — Owner and judge experience ✅ (2026-10-17)

**Built**
- **Approval inbox v2**: highest risk then oldest first; "why this needs you" with the policy rule in plain words; time
  waiting; keyboard (J/K move, A approve, R reject, E edit); a pending-count badge on "Approvals" in the top bar
  (refreshed every 30 s).
- **Today** (`/today`): needs-you-now list, last-24-hour numbers linking to their source pages, alerts (kill switch,
  model budget fallback), recent enquiries. Signed-in owners land here; sandboxes land on the live demo.
- **Guided demo** for sandboxes: five skippable steps on `/demo` (enquiry → agents → result → approve → try to break it).
- **Installable**: web app manifest (`/manifest.webmanifest`, start page = inbox) and an SVG app icon.

**Tested**: browser: tour visible in a fresh sandbox, badge "2" after a collections check, inbox sorted high-risk first
with the rule text and waiting time, J moves focus, Today shows the 24 h numbers; fresh tab console clean; typecheck,
lint and build clean.

**Not done (Phase 16 remainder)**: left sidebar re-layout, buyers page, documents page, Playwright + axe + Lighthouse CI,
visual regression, usability test with exporters (needs people), backend explanations in Arabic (Phase 20).


## Phase 17 (part) — Documents and the enquiry page ✅ (2026-10-17)

**Built**
- `app/outputs/documents.py` + `GET /runs/{id}/documents`, `POST /runs/{id}/documents/{kind}/issue`: quotation,
  proforma invoice, packing list, CEPA origin checklist from stored run data only; DRAFT until approved; issuing
  records number + SHA-256 in the audit chain (DECISIONS O1–O2). `GET /audit?run_id=` for one enquiry's trail.
- Dashboard: `/run?id=` (results, timeline, documents with print/issue, audit trail), `/print?run=&doc=` bilingual A4
  layout with DRAFT watermark and checksum footer (O3–O4); "Open full record" on every approval card.

**Tested**: `tests/test_documents.py` (3: draft→final, totals equal the quote, checksum in the audit, roles, isolation,
runs without a quote, checksum sensitivity). Browser: draft quotation printed with watermark; after approval all four
documents final; "Issue final" recorded the checksum.

**Not done (Phase 17 remainder)**: email channel, uploaded-document extraction (needs a vision model: after the
Claude key), notifications, WhatsApp templates.


## Phase 15 — SaaS core: business profile, onboarding, settings ✅ (2026-10-17)

**Built**
- **Business profile per organisation** in the database (DECISIONS B1–B3): catalogue, costs, margins, discount tiers,
  validity, logistics. Runs and collections use the organisation's profile; demo and sandboxes keep the demo profile.
- **Settings API** (`/settings/...`): profile sections, catalogue add/edit/remove, CSV import (merge/replace, row errors)
  and export, bounded autonomy (only stricter than `autonomy.yaml`, B4), onboarding progress. RBAC-checked and audited.
- **Dashboard**: `/onboarding` wizard (business → products with HS hint → pricing → shipping → first test quote),
  `/settings` (business & pricing, products, shipping, autonomy), a "finish setting up" banner, sign-up lands in
  onboarding. EN + AR. Team management and the organisation switcher came with Phase 13.

**Tested** (real output)
- `tests/test_settings.py` (9): blank start, quotes from the organisation's own catalogue and name (and not another's),
  validation, CSV merge/replace/errors/export, roles, autonomy only stricter (incl. a tampered row), onboarding
  progress, sandbox privacy and purge. Backend total **345 passed**; ruff, typecheck, lint, build clean.
- **Browser check**: sign up → onboarding → add "Brass serving tray" (HS suggestion shown, corrected) → pricing →
  shipping → test enquiry → quote line matched to the new product at AED 30.67/unit, reply signed "Moradabad Brassware
  Test"; settings tabs render; autonomy shows locked NEVER actions.

**Not done (still in the plan)**: notification preferences, data-retention setting, language preference, explicit
"transfer ownership" button (possible today by making another member Owner, then changing your own role).


## Phase 13 — Authentication, RBAC, demo lock ✅ (2026-10-17)

**Built**
- **Identity** (`backend/app/auth/`): users, organisations, memberships, invitations, API keys; scrypt passwords; HS256
  access tokens whose role is re-read on every request; sign-out everywhere; failed and successful logins audited;
  per-IP limit on sign-in attempts. Production refuses to start without `AUTH_SECRET` (DECISIONS S9–S10).
- **RBAC** (`app/governance/rbac.yaml` + `rbac.py`): 7 roles x 19 permissions on every route; approvals by risk
  (high = owner only), accountant for payment reminders, `drafts.edit`, kill switch engage/release split, admins cannot
  touch owners, last owner protected, **four-eyes** with an audited override (S11–S12).
- **Demo lock**: one-click private sandbox per visitor (synthetic data, 24 h, never real WhatsApp, deleted with all its
  rows on expiry) (S13). Organisation-scoped MCP keys (S14). Invitations by fragment link (S15). Audit export for
  auditors (`GET /audit/export`). The `X-Org-Id` header is gone outside tests.
- **Dashboard**: sign-in screen (demo first, sign-in, create organisation), user menu (organisation, role, sandbox
  expiry, switch organisation, sign out / everywhere), `/team` (members, roles, invitations, assistant keys),
  `/invite#token`, buttons hidden or disabled with the reason ("Only the owner can decide high-risk actions"),
  four-eyes override prompt, audit export button. EN + AR.

**Tested** (real output)
- `tests/test_rbac.py`: 50 tests (role x route matrix over 19 routes, role x risk on approve and reject, accountant,
  drafts, four-eyes, isolation, sessions, invitations, two organisations, sandboxes incl. expiry purge and no real
  WhatsApp, stream tokens, API keys). Backend total **336 passed**; ruff clean.
- New eval suite `rbac`: **33/33**, unsafe allows 0 (hard gates 1.00 / 0.00).
- Frontend: typecheck, lint and production build clean.
- **Browser check**: protected page shows the sign-in screen → demo sandbox → English sample run streams live (stream
  token) → approve → audit shows `user:usr_…` with chain verified and Export button; Arabic RTL sign-in; a Viewer sees
  the draft with Approve/Reject disabled and the reason, and no kill-switch control; an invitation link accepted as
  Accountant → "Your role (Accountant) cannot do this." on the demo page.

**Bugs found and fixed**
1. Failed logins were not audited: the audit row was written in the transaction the error rolled back. Now written in
   its own transaction.
2. The `[token]` invitation route broke the static build (dynamic segment under Next 16 prerendering); moved the token
   to the URL fragment (S15).
3. Protected pages triggered Next's instant-navigation validator because they render only after sign-in;
   `export const instant = false` on those six pages.
4. Sandbox invoices would have collided (global invoice ids); ids are now organisation-prefixed with a display number.

**Next: Phase 14** (deploy + real Claude + operations): needs the founder's host choice and an Anthropic key.


## Phase 12 — Submission pack ✅ (2026-10-10)

**Built**
- `docs/SUBMISSION.md` (≤ 700 words: problem, what Jisr does, why it can be trusted, measured results table, limits), `docs/PITCH_NOTES.md` (timed live demo + trust moment + failure fallbacks), `docs/VIVA_QA.md` (45 questions with evidence), `docs/DEMO_CHECKLIST.md`, `docs/DATA_PROTECTION.md` + `/privacy` page (EN/AR, footer link).
- Offline replay covers **every** demo path: the cassette now also records the voice-note transcripts; a test runs all samples and both voice notes from the committed cassette alone.
- Claims register rows 19–24 (red team, e2e, trajectories, governance, documents, time-saved assumption); landing page status text now states the evaluation discipline.

**Tested**
- `make test` → 286 passed; `npm run build` OK; replay coverage test green.
- `make eval` on the submission commit → see `docs/EVAL_REPORT.md`.

**Founder tasks before 9 Dec** (none of these can be done from code)
1. `ANTHROPIC_API_KEY`, then `make record` with `LLM_PROFILE=prod`; measure Claude latency and cost on the demo.
2. Deploy (docs/DEPLOY.md: Fly + Neon + Vercel) and test the hosted link on a fresh browser.
3. WhatsApp test number (docs/WHATSAPP_SETUP.md); `make sanctions` for the UN list.
4. Official CEPA Annex 2B; advisor review of HS labels and of the retrieval set sample.
5. Shadow-mode pilot with the family business (baseline interview, 30–50 real enquiries anonymised) → replace the time-saved assumption.
6. Confirm deadline and eligibility with the organisers in writing; video (2–3 min, captions) and deck from PITCH_NOTES.
7. Dubai licence + Dubai AI Seal application (docs/SEAL_READINESS.md).

## Phase 11 — A2A buyer agent, 3D tariff tree, 3D document pack ✅ (2026-10-10)

**Built**
- **A2A** (a2a-sdk 1.2.2, protocol 1.0): Agent Card + JSON-RPC `/a2a`; a buyer agent's RFQ (text or JSON) runs the normal pipeline; the task stays WORKING until the owner approves, then completes with the approved quotation through the outbox; malicious requests → REJECTED; errors → FAILED. Demo client `scripts/buyer_agent.py` (normal and `--malicious`).
- **3D tariff explorer** `/tariff` + `GET /kb/chapters|tree|locate`: radial chapter tree, the duty agent's cited path for a product lit and animated (turned to face the viewer), detail panel with official EN/AR text, duty, Annex 3B rule; list fallback.
- **3D document pack** in run results: invoice / packing list / certificate cards with red beams between conflicting fields; new sample "Order with a document mismatch" (jute bags: catalogue 4202 vs cited 6305).
- Shared 2D/3D toggle; general glossary additions for HS (trays, planters, coasters, journals, bedspreads); buyer-name fix for "email — Company" signatures.

**Tested**
- `make test` → 285 passed (A2A with the official SDK client in-process: card, WORKING → approve → COMPLETED with artifact, malicious → REJECTED; KB API on the real index).
- Live over HTTP: `buyer_agent.py --malicious` → REJECTED; normal run → WORKING, approved via the API → COMPLETED with the quotation.
- `make eval` → **Gate: PASSED**, all metrics unchanged.
- Browser: tariff explorer (list and 3D, "brass diya lamps" → 9405 path, detail with Annex 3B-9), 3D document pack with the 4202 ↔ 63051010 beam, 3D agent graph.

**Next: Phase 12 — submission pack.**

## Phase 10 — Dashboard, Impact Ledger, MCP, 3D, deploy configuration ✅ (2026-10-10)

**Built**
- **3D** (React Three Fiber, pinned): **live 3D agent graph** on `/demo` (2D/3D switch; agents pulse when active, edges light up, work parcels travel, the gate turns amber when held / red when blocked) and the **3D bridge hero** on the landing page (shipments cross India → UAE through the governance keystone; SVG poster underneath). Theme-aware (pearl/midnight re-colour live), off under reduced motion / without WebGL / by choice; labels are real DOM text (Arabic shapes correctly).
- **Impact Ledger** `/impact` + `GET /impact`: measured outcomes per run (enquiries, quotes, approved & sent, agent time, time to acknowledge, risks caught, CEPA "up to") kept apart from the labelled time-saved estimate; ledger rows open the run.
- **MCP server** (`app/interop/mcp_server.py`, SDK 2.3): 6 governed tools (analyse, ask CEPA, classify HS, check documents, pending approvals, governance status); no approve/send tools; passport-checked and audited; HTTP at `/mcp/` behind a bearer token, stdio for Claude Desktop.
- **Hosted-demo protection**: per-IP run limit, daily token budget with a labelled offline fallback (shown in `/health`).
- **Deploy configuration**: `deploy/api.Dockerfile` (repo-root build with index and replay assets), `fly.toml`, `.dockerignore`, `docs/DEPLOY.md` (Fly + Neon + Vercel, founder steps).
- Acknowledgements only on channels with a waiting buyer (WhatsApp, email).

**Tested**
- `make test` → 281 passed (MCP over HTTP: token, tool set, audit, analyse sends nothing, not mounted without a token; rate limit 201/201/429; budget fallback; impact ledger).
- `npm run build` → production build OK (all pages incl. 3D chunks).
- `make eval` → **Gate: PASSED**, all metrics unchanged (e2e p95 2.1 s; trajectories 1.000).
- Browser: 3D graph live during a run (light), 3D bridge (light and dark), `/impact` with real ledger rows.

**Not done here (founder steps)**: the actual Fly / Neon / Vercel deployment (accounts), building the API image (~3 GB model download).

**Next: Phase 11**: A2A buyer agent (Agent Card, RFQ task, malicious-agent block), 3D HS-tariff tree, 3D document pack.

## Phase 9 — Supervisor routing, buyer memory, trajectory suite ✅ (2026-10-10)

**Built**
- **Explainable re-planning** (deterministic by design, DECISIONS A1): after pricing the supervisor routes to (a) a **clarification** question when no product/quantity could be read (no guessed quote), (b) **no CEPA step** for destinations outside the UAE, (c) the standard path; each re-plan is a visible timeline event with its reason.
- **Buyer memory** (`buyer_memory`, facts only, per org + hashed contact): fills a missing Incoterm from the last order (flagged and reviewed), shows "returning buyer" and earlier high-risk signals in the trust card.
- **Trajectory suite** (`data/gold/trajectories.yaml`): 50 scenarios (clean EN/AR/mixed, attacks, kill switch, risky buyers, missing details, non-UAE, returning buyers, voice notes, duplicate delivery) x 3 runs through the signed WhatsApp path; gates on pass rate, pass^3 and path consistency.
- Fixes found by the scenarios: third-party payment is a HIGH-risk signal (matching P-TRUST-001); "Again 50 …" was dropped by the parser ("in" matched inside "Again").

**Tested**
- `make test` → 273 passed (routing rules, clarification path, non-UAE path, memory fill + facts-only, existing suites).
- `make eval` → **Gate: PASSED**. Trajectories **1.000** pass rate, **1.000** pass^3, **1.000** path consistency (fake profile: deterministic; on Claude this measures variance). E2E 1.000 (p95 2.8 s), voice 1.000; all other gates unchanged.

**Next: Phase 10**: full dashboard (runs, ROI / Impact Ledger), MCP server, 3D hero + live 3D agent graph, deploy configuration.

## Phase 8 — Channels: WhatsApp, voice notes, collections ✅ (2026-10-10)

**Built**
- **WhatsApp Cloud API** (`app/channels/whatsapp.py`, `app/api/channels.py`): verify-token handshake, HMAC-SHA256 signature check on the raw body (unsigned → 401 + audit), text and voice-note parsing, media download, text send; idempotent inbound handling; contacts stored with a hashed key (models never see a phone number); Meta's 24 h window enforced before approval and in the outbox. Founder setup guide: `docs/WHATSAPP_SETUP.md`.
- **Voice notes → STT → quote**: `router.transcribe` (role `stt`, same free-tier data rule: real audio refused), offline replay of transcripts; **synthetic** demo voice notes (Arabic, English) made with the OS voice; the parser now reads spoken Arabic quantities (ثلاثمئة، مئتي، ألف).
- **Simulator**: signs a Meta-shaped payload and runs the real handler; dashboard "WhatsApp voice notes" card with audio players; the transcript appears in the timeline.
- **Outbox → real WhatsApp** when configured (simulator otherwise); approvals refused outside the 24 h window.
- **Collections** (`app/agents/collections.py`): overdue-invoice reminders EN/AR with tone by lateness, always through the approval inbox, never with bank details (anti-fraud line instead); "Check overdue invoices" on `/approvals`.
- Additive schema upgrade at start-up (new nullable columns), contacts / inbound_log / invoices tables.

**Known gaps (founder steps)**
- Real WhatsApp needs your Meta app credentials and an HTTPS URL (`docs/WHATSAPP_SETUP.md`); templates for messages outside the 24 h window are not built.
- Real voice notes need a paid, no-training speech-to-text before the pilot (the router refuses them on free tiers by design).

**Next: Phase 9**: explainable supervisor routing (clarify when details are missing, CEPA only for UAE destinations), buyer memory, trajectory suite (50 scenarios x 3 runs).

**Tested**
- `make test` → 268 passed (signature valid / tampered / wrong secret, handshake, parsing, Graph media + send with a mocked transport, duplicate deliveries, voice note → Arabic quote with 2 lines, real audio refused on free tier, 24 h window refusal, collections tone and bank-safety line, spoken Arabic quantities).
- `make eval` → **Gate: PASSED**. New hard gate: voice notes → quote **1.000** (2 synthetic notes, AR + EN, through the signed inbound path). E2E 300 runs 1.000, p95 2.4 s; governance, red team, docs, trust, retrieval and extraction unchanged.
- Browser (Arabic): voice note → timeline shows the transcript → 2 lines priced, Incoterm correctly flagged as not stated. Collections: 2 reminders drafted (45 days AR = high risk, 10 days EN), the third invoice not yet due.

## Phase 7 — Governance: autonomy, kill switch, Agent Passports ✅ (2026-10-10)

**Built**
- **Graded autonomy** (`autonomy.yaml`): NEVER / L0 / L1 / L2 / L3 per action type; the final effect is the strongest of the policy effect and the autonomy cap, so autonomy only adds caution. The supervisor proposes a fixed-text **acknowledgement** (L2): it goes out on its own only when every policy allows it (P-ACK-001), never to a flagged sender (P-INJ-002), and waits for the owner when the buyer looks risky (P-TRUST-001).
- **Kill switch** per organisation (rule P-KILL-001, audited on/off, re-checked in the outbox; approving while it is on returns 409).
- **Single outbound path** `app/channels/outbox.py` for approved and autonomous actions (simulator now, WhatsApp in Phase 8).
- **Agent Passports** (`passports.yaml`): purpose, data, models, actions and tools; tool calls outside the list are refused at run time. `/passports` adds live eval metrics and 24 h activity.
- **Governance API + dashboard** `/governance`: kill switch, "done on its own (24 h)", autonomy table, policy rules, passports. Contracts updated.
- **Governance scenario suite** (20 owner-readable rows): it caught pricing rules applying to any action with pricing flags; scoped to price-bearing actions.
- `docs/SEAL_READINESS.md`: Dubai AI Seal is a company certification (DCAI); product evidence mapped; licence and team are founder tasks.

**Tested**
- `make test` → 254 passed (autonomy matrix, kill switch over HTTP and in the service, passport enforcement, endpoints, acknowledgement in the audit trail).
- `make eval` → **Gate: PASSED**. Governance scenarios **1.000**, unsafe automatic actions **0.000**; red team: attacks succeeded **0/30** (blocked_rate is now 1.000 because every flagged run also has its acknowledgement blocked); e2e 1.000, p95 2.2 s; all earlier gates unchanged.
- Browser: `/governance` renders; "Stop everything" → a new run is fully blocked (P-KILL-001 on the acknowledgement and the quote, audit `kill_switch.on`); "Turn off" restores normal behaviour.

**Next: Phase 8, channels**: real WhatsApp Cloud API (signature check, 24 h window), voice notes → STT → quote, simulator, collections reminders.

## Phase 6 — Document Consistency Checker + Buyer Trust ✅ (2026-10-10)

**Built**
- **Document Consistency Checker** (`app/tools/doc_checker.py`, deterministic): 9 mistake types (HS mismatch across invoice / packing list / certificate, quantity, line and invoice totals, missing CoO when CEPA is claimed, missing shipping bill, currency vs quote/LC, net > gross weight, transshipment without a through bill of lading). Values normalised; lines matched by description and HS so a different line order is not a mistake; HS compared at the level both documents give. Each finding: field, expected, found, fix, CEPA article (cited from the KB). `draft` stage for quote-time packs.
- **Docs agent** drafts the invoice and packing list (seller's catalogue HS) and the CoO (cited classification) from the run and checks them: a catalogue code that disagrees with the cited classification shows up before anything is issued.
- **Buyer Trust** (`app/tools/buyer_trust.py`): explainable signals with evidence (email domain, credit / bank-change / third-party payment / pressure phrases EN+AR, trade licence, destination, order size) and a UN Security Council Consolidated List name check (`make sanctions`; "list not loaded" when absent). Never a score or verdict; positive signals shown.
- Policy **P-TRUST-001**: a possible sanctions match, bank-detail change or third-party payment makes every action high risk + owner approval.
- Dashboard: **ChecksCard** (document findings with fixes and citations; buyer signals) in EN and AR.
- Data `synthetic-v4`: 20 docsets with format noise and reordered lines, 80 trust rows (20 hard negatives).

**Tested** (`make eval`, commit of this phase)
- `make test` → 237 passed (each mistake type: trigger on the exact field + formatting / reordering non-triggers; draft vs shipment stage; trust triggers and look-alikes; sanctions loader and conservative matching; policy trigger / non-trigger).
- `make eval` → **Gate: PASSED**. Docs: recall **1.000**, field accuracy **1.000**, clean-set false alarms **0.000** (incl. noisy sets). Trust: recall **1.000**, precision **1.000**, hard-negative false alarms **0.000**. All earlier gates unchanged (retrieval, security, extraction, e2e 1.000, p95 2.3 s).
- Honesty note: mistakes / phrases and checks share an author; these numbers prove correct implementation and robustness to formatting, not real-world coverage (pilot documents needed).
- Browser (Arabic RTL): consistency card "documents agree", buyer signals with evidence.

**Known gaps**
- Signal and finding explanations are English only for now.
- The UN list must be downloaded (`make sanctions`) for real screening; matching is name-only.

**Next: Phase 7, governance**: autonomy levels, kill switch, Agent Passports with enforced tool allow-lists, single outbound path, Seal readiness.

## Phase 5 — Knowledge base + CEPA Duty + Docs agents ✅ (2026-10-09)

**Built**
- **Official sources** (`scripts/download_kb_sources.py`, `data/kb_sources/`): 19 documents + 1 snapshot from official hosts with SHA-256; the CEPA **Final Agreement** (UAE MoET) replaces the Abu Dhabi pre-final copy (negotiator notes found in it); gaps recorded (no official Annex 2B → savings are "up to").
- **Index** (`make kb`, `app/rag/`): UAE tariff tree from the Dubai Customs master (EN+AR, 28,300 nodes), **137 Annex 3B rules** parsed into components (WO/CC/CTH/CTSH/SO/VA%, Ex scopes, ranges), CEPA chunked by ARTICLE and ANNEX, guides by page; multilingual-e5-large vectors (16,075) with a text-hash embedding cache (re-ingest in 41 s).
- **Retrieval**: exact codes, BM25 (EN Snowball + Arabic light stemmer), vectors, RRF, bge-reranker; seller-words→tariff-wording glossary (EN/AR).
- **Agentic RAG**: deterministic planner (hs / psr / duty / procedure; bare product phrases → HS), rule-table search for product groups, corrective loop (rewrite with an AR→EN trade lexicon, widen), grading threshold **calibrated on dev** (`eval/calibrate.py`), budgets, **grounding in code** (claims must cite retrieved passages; every number must appear in a cited passage).
- **CEPA Duty agent**: per line HS top-3 with confidence, catalogue HS hint as a labelled prior (disagreement → human check), cited MFN duty and Annex 3B rule, FOB/Ex-Works basis, origin evidence to hold, "up to AED X" saving. **Docs agent**: cited document pack (invoice/packing list, CEPA CoO, shipping bill).
- Dashboard: **DutyCard** with sources (document, issuer, date, page), "≤ AED X" counter.
- Eval: retrieval suite with ablation, per-language slices, dev/test split; hand-labelled seller-phrase HS set (`data/gold/hs_products.jsonl`).

**Tested** (real output, test split, `retrieval_20261009-175554.json`)
- `make test` → **211 passed**, incl. 11 real-KB tests that pin treaty facts (they skip where no index is built), plus frontend type-check and lint.
- `make eval` → **Gate: PASSED** (8 new retrieval gates, optional where no KB). Grounded claims **1.000**, numbers verbatim **1.000**, false refusals **0.025**, correct refusals **0.750**; agentic recall@5 **0.825**; HS seller-phrase top-1 **0.868** / top-3 **0.962** (uncovered goods 0.733).
- Ablation recall@5: BM25 0.600 → vector 0.688 → RRF 0.675 → +rerank 0.725 → agentic 0.825. Arabic questions over Arabic text are strong (0.889); **Arabic questions over the English treaty are weak (0.667 agentic)**.
- First-shot test run exposed a grounding bug (grounded 0.367); fixed after diagnosis on dev only (DECISIONS K13). E2E 300 runs: success 1.000, p95 1.8 s (warm caches).
- Browser: "brass diya lamps" → 9405.50 non-electrical luminaires (was 8539 vapour lamps), runners → 6302.51 table linen, cited 5% MFN, CTH + VA 40% (Annex 3B-9 / 3B-6), "≤ AED 736".

**Known gaps**
- Annex 2B (UAE preferential schedule) not available officially → no real saving can be claimed yet.
- Cross-lingual retrieval (Arabic question → English treaty text) and "no tariff line fits" detection are weak.
- HS labels and the retrieval set need an advisor's sample review.

**Next: Phase 6, Document Consistency Checker + Buyer Trust signals.**

## Phase 4 — Quote agent ✅ (2026-10-09)

**Built**
- **Deterministic bilingual RFQ parser** (`app/tools/rfq_rules.py`): quantities in many formats ("1.2k", number words, Arabic-Indic digits, "qty 120", "– 400 pcs", table rows), units (EN/AR), Incoterms (any case, C&F/CNF), GCC places → destination country (Indian origins ignored), deadlines (EN/AR), language incl. Gulf code-switching, buyer name.
- **Hybrid grounded extraction** (`app/tools/rfq.py`): model extraction reconciled against the text: quantities not written are dropped, unwritten Incoterms replaced, gaps filled, everything reported; rules-only fallback when the model fails.
- **Live FX** (`app/tools/fx.py`): ECB USD/INR via Frankfurter × CBUAE peg 3.6725, 6 h cache, stale fallback flagged; every quote stores rate, source, rate date and fetch time. Fixed labelled demo rate for tests/offline/replay.
- **Pricing v2** (`app/tools/pricing.py`): Incoterm scope table with separate charge lines (inland, export clearance, ocean freight by CBM, insurance, destination delivery, import clearance, import duty from the tariff master), volume tiers, owner margin floor never crossed automatically, pricing flags. Catalogue matching by product nouns (fixed "brass trays priced as lamps").
- **Pricing policies**: P-MARGIN-001, P-DISC-001, P-PRICE-001 (flags reach the owner with the rule and reason).
- Data `synthetic-v3`: 30 hand-written held-out enquiries; 46 unanswerable country labels fixed.
- Dashboard: quote shows Incoterm, charge lines, FX rate with date, review flags.

**Tested** (real output; report commit `3609945`, profile `fake` = deterministic parser)
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

**Tested** (real output; report commit `a9984cc`, profile `fake` = rule layer only)
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

**Tested** (real output; numbers from `backend/eval/results/`, commit `6d5c89f`, profile `fake`)
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
