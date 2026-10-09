# Decisions log

Each entry: date, decision, why, and what would make us revisit it.

---

## 2026-10-09 — Planning decisions (agreed with the founder)

| # | Decision | Why |
|---|---|---|
| D1 | Submit by **9 Dec 2026** (feature freeze 5 Dec) | Official sources conflict (press release/FAQ: Dec 2026; programme timeline: Jan 2027). Planning for the earlier date is safe. **Revisit** once the organisers confirm in writing. |
| D2 | Runtime LLMs: free tiers (Groq/Gemini/Cerebras) on **synthetic data only** in dev; **Claude** in `prod` (Opus 5.5 = `smart`/`judge`, Sonnet 5.5 = `worker`, Haiku 5.5 = `fast`); a deterministic `fake` profile for tests and replay | Cheap iteration in dev, best quality for demo/pilot/finals, and fully offline tests. |
| D3 | Hosting: Next.js on Vercel, FastAPI on Fly.io, Postgres+pgvector on Neon | Fastest path to a no-login public demo link, cheap. |
| D4 | Look: pearl light default + midnight dark, toggle everywhere, Arabic RTL | Projector-readable, premium, bilingual. |
| D5 | 3D in four places: landing bridge hero, live agent graph, HS-tariff tree explorer, document pack. All lazy-loaded with static fallbacks; never on approvals/audit/settings | "Wow" where it explains the system, speed where people work. |
| D6 | Core scope includes MCP server, A2A buyer agent, real WhatsApp Cloud API, voice-note enquiries. Cut order if late: 3D doc pack → 3D tariff tree → A2A → voice → real WhatsApp → MCP | Founder's choice; cut order protects the demo. |

## 2026-10-09 — Research corrections (web research during planning)

| # | Finding | Effect |
|---|---|---|
| R1 | **India–UAE CEPA default product-specific rule = ≥40% qualifying value content (FOB base) + change in tariff classification (CTH/CTSH)** for non-originating materials. Exceptions: gems and jewellery ~3–7% value addition, agriculture wholly obtained, steel "melt and pour", some sectors higher. Direct consignment required. Sources: NSEZ CEPA FAQ (nsez.gov.in), ATB Legal and PwC summaries. | The playbook's "35% RVC" figure is **wrong**: claims register updated to 40% (status: verify against the official Chapter 3 annex). `duty_origin` rules must be loaded from the official annex, never from blogs. |
| R2 | Deadline conflict (see D1). | Plan for December; confirm with organisers. |
| R3 | Press coverage says "open worldwide"; the playbook's T&C reading says UAE residents/licensed Dubai corporates. | Get written eligibility confirmation before heavy spend. |
| R4 | A2A protocol spec **1.0** is stable (2026) and now under the Linux Foundation's Agentic AI Foundation; Python package `a2a-sdk` 1.1.x implements 1.0. | Pin `a2a-sdk` 1.x in Phase 12a; re-check the spec page before building. |
| R5 | Finalists must demonstrate a **working agent live on stage**. | Offline replay and a second laptop are mandatory. |

## 2026-10-09 — Phase 0 engineering decisions

| # | Decision | Why |
|---|---|---|
| E1 | The LLM router has three backends behind one interface: `fake`, `anthropic` (official `anthropic` Python SDK), `litellm` (non-Claude free tiers only). | Anthropic's guidance is to call Claude through its official SDK rather than an OpenAI-compatible shim; that gives us structured outputs (`messages.parse`), adaptive thinking + `effort`, typed errors and server-side refusal fallbacks. LiteLLM stays for swapping free providers in dev. |
| E2 | Roles: `smart` (planner, grounding verifier), `worker` (agents), `fast` (classify/grade/rerank fallback), `judge` (eval; must differ from the worker model), `stt` (voice). | Matches v3 model routing; `judge` separation is required by v3 §22.8. |
| E3 | Claude settings: adaptive thinking is always on for Opus 5.5 (we never send `disabled`), depth via `output_config.effort` set explicitly per role. Server-side refusal fallback (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) is enabled by default for Opus 5.5 / Sonnet 5.5 and can be turned off with `ANTHROPIC_FALLBACKS=false`. | Opus 5.5 rejects disabled thinking; its default effort is `medium`, so we set it. Fallbacks stop a safety-classifier false positive from killing a live demo. |
| E4 | The router refuses any request whose `data_class` is not `synthetic` when the target provider is marked `free_tier`. | Enforces "no real data on free tiers" in code, not by convention. |
| E5 | The router writes a JSONL call log (role, provider, model, tokens, latency, request hash) with **no prompt or response text**. | Cost/latency metrics for `make eval` without logging PII. |
| E6 | Python 3.12 managed with `uv`; ruff for lint; pytest + pytest-asyncio. SQLite fallback until Phase 1 wires Postgres. | Reproducible, fast installs; one-command setup. |

## 2026-10-09 — Phase 1 decisions

| # | Decision | Why |
|---|---|---|
| E7 | Contracts (RunEvent, REST routes, RunState) frozen in `docs/CONTRACTS.md`. | Lets frontend/3D work proceed in parallel against a stable interface. |
| E8 | Approval routes are `POST /approvals/{id}/approve` and `/reject` (v3 sketched `{id}:approve`). | Clearer in FastAPI and browser tooling. |
| E9 | Phase 1 graph is a fixed LangGraph chain with a conditional branch after the supervisor; the run **ends** at `needs_approval` and the governance layer performs approved actions outside the graph (no checkpointer yet). | The approval gate stays deterministic and outside the model loop. A Postgres checkpointer + `interrupt()` arrive with the planning supervisor (Phase 9) if re-entry is needed. |
| E10 | Offline replay = a **cassette** of recorded model answers (`replay/demo.cassette.jsonl`) served by a `replay` LLM profile. The whole system (governance, approvals, audit) still runs for real; only model calls are replayed. Real (non-anonymised) data is never recorded. | A replayed demo behaves exactly like a live one, including approvals, with no network. |
| E11 | Tables are created with `create_all` in Phase 1; Alembic migrations come once the schema settles. SQLite runs in WAL mode with a busy timeout; all timestamps go through a `UTCDateTime` column type. | Zero-setup local runs; SQLite returned naive datetimes, which made the browser read UTC as local time (bug found in the browser check). |
| E12 | Frontend: Next.js 16 (App Router, cacheComponents) with the **language in the URL** (`/en`, `/ar`, a `proxy.ts` redirect) and the theme in a cookie applied by an inline boot script. No next-intl/next-themes. | Both languages are prerendered statically with the right `lang`/`dir`. The theme never flashes and never causes hydration mismatches (per the Next 16 "preventing flash" guide). Fewer dependencies. |
| E13 | Pricing: round the **unit** price first, then line total = unit × qty, then quote total = Σ lines. | Found in the browser check: 23.94 × 500 must equal the printed line total (11,970.00), as on a real invoice. |
| E14 | Small token-based UI primitives instead of the shadcn/ui CLI for now; shadcn components are added when a phase needs dialogs or data tables. | Full control of tokens in both themes; less generated code to maintain. |

## 2026-10-09 — Knowledge-base sources (founder's source pack reviewed)

| # | Decision | Why |
|---|---|---|
| R6 | Primary CEPA text = **UAE MoET "Final Agreement" PDF (2022-03-28)**; the Abu Dhabi Customs copy from the pack is kept as cross-check only and never cited. | The AD Customs PDF is pre-final: its Annex 3B contains negotiator notes. Rule values were verified identical. |
| R7 | The duty/origin calculator takes the **price basis** (FOB vs Ex-Works) as an input: VA threshold is 5 points lower on Ex-Works; HS 71 must use FOB. | Annex 3B Rule 1. Resolves the 40% vs 35% question: both are right on different bases. |
| R8 | KB downloads go through `scripts/download_kb_sources.py`: official hosts only, type sniffing, size cap, SHA-256 + final URL + fetch time per file, curl fallback that keeps TLS verification. Sites that block scripts are captured as dated snapshots (`download_mode=snapshot`); unreachable ones are `manual`. | Every cited fact must be traceable to an unchanged original. |
| R9 | Tariff retrieval indexes **both** Arabic and English descriptions and displays the original text. | The official tariff master has at least one EN/AR mismatch (94052100); Arabic prevails by law. |

## 2026-10-09 — Phase 2 decisions (data and evaluation)

| # | Decision | Why |
|---|---|---|
| E15 | Synthetic data is **template-generated with labels by construction** (seeded, byte-reproducible, checked by a test); attacks are hand-written. No model writes or labels evaluation data. | Avoids grading the model on its own output; every number is reproducible. |
| E16 | Eval lives in `backend/eval/` (suites, results, thresholds, gate, baseline); datasets in `data/synthetic/`. Six suites: extraction, security, redteam, docs, pricing, e2e. Results follow a fixed contract (git SHA, profile, models, dataset version, split). | One yardstick for every phase; `docs/EVAL_REPORT.md` is generated, never hand-edited. |
| E17 | Gate = **hard** thresholds now (PII redaction 1.0, quantity preservation ≥ 0.98, attack success 0, pricing invariants 1.0, clean-set FPR ≤ 0.05, crash rate 0, p95 latency ≤ 120 s) + **targets** that become hard in their phase (extraction F1 ≥ 0.90 in P4, injection recall 1.0 / FPR ≤ 0.02 in P3, doc-issue recall ≥ 0.90 in P6, task success ≥ 0.90 in P9) + **no regression > 0.02** vs `eval/baseline.json`. | Gating stubs on product targets would block all work; gating on regressions keeps quality from slipping. Proven by deliberately breaking the redactor and the extractor: the gate failed (make exit 2). |
| E18 | Extraction is scored with micro-F1 over items (quantity equal + ≥ 60% of gold words, EN or AR) and fields (country, Incoterm, structured deadline, language). | Field-level, bilingual and reproducible; documented in `eval/suites/extraction.py`. |
| E19 | Docker Postgres is published on host port **55432** (not 5432/5433). Tests can run on Postgres with `TEST_DATABASE_URL` / `make test-postgres`. | Two local Postgres servers on this Mac already use 5432 and 5433 and silently answered instead of Docker. |
| E20 | `doc_checker.check_document_set()` contract frozen now as a stub, so Phase 6 is measured from day one. | Honest baseline: recall 0.0 is reported, not hidden. |

## 2026-10-09 — Phase 3 decisions (security core)

| # | Decision | Why |
|---|---|---|
| S1 | **Two-layer injection guard**: deterministic bilingual rules on normalised text views (NFKC, zero-width removal, de-spacing, leetspeak, Arabic alef/ya/ta-marbuta/diacritics/digits) + an LLM classifier on the `fast` role whose confident findings are **added** (can raise risk, never lower it). Classifier failure → rules only, recorded in the trace. In the offline `fake` profile the classifier never flags, so reported numbers are rule-layer only. | Rules are explainable and testable; the classifier covers new phrasings in prod; the policy engine stays the final decision maker. |
| S2 | **Held-out discipline**: the guard was developed on a separate dev set (`adversarial_dev`: 42 attacks + 22 benign lookalikes, different wording). The 30 test attacks were scored once at the end. | Tuning on the test set would make the 100% meaningless. |
| S3 | **First-shot held-out result: 29/30 detected (0.967)**, 0 false positives on 300 enquiries. The miss (adv_008, secrets requested as a *question*) revealed a real gap; two new dev cases with different wording were added and the rule generalised → 30/30. adv_008 is therefore no longer unseen. **Recommendation: the founder writes 10–20 new attacks as a truly independent hold-out** before the pitch. | Honest reporting: both numbers are kept. |
| S4 | Redactor v1 masks PERSON (after honorifics), POBOX, EID, TRN, GSTIN, PAN, ACCOUNT, CARD (Luhn), PHONE (incl. Arabic-Indic digits, brackets) on top of EMAIL/IBAN; HS codes after "HS code/tariff" are never masked as phones. Token→original map is in memory only (`exclude=True`). | Real messages carry more than emails and phones; over-redaction of HS codes would break classification. |
| S5 | **Router PII tripwire**: any request still containing an email address, IBAN, Emirates ID, TRN, GSTIN or Luhn-valid card number is refused (fail closed). Phones are not in the tripwire (too ambiguous); they are covered by redaction + the captured-call test. | Defence in depth: a future bug that skips redaction cannot leak these to a model. |
| S6 | "Mark as paid / confirm received" requests raise `payment_status` → the supervisor proposes `mark_payment_received`, which P-BANK-001 blocks. | Payment-status fraud is as dangerous as bank-detail fraud. |
| S7 | Phase 3 targets flipped to **hard gates**: injection detection 1.0, FPR ≤ 0.02, hard-negative FPR ≤ 0.10, unflagged-to-human 0.0, PII-case recall 1.0, business data kept ≥ 0.98. | Phase delivered them; regressions now fail CI. |
| S8 | Wall-clock metrics (e2e `latency_p95_s`) are exempt from the 0.02 baseline-regression rule (`regression: false`) and keep their absolute hard limit (120 s). | Found when the committed Phase 3 report showed "Gate: FAILED" for 0.041 s → 0.095 s: machine-load noise, not a regression. An absolute 0.02 margin is meant for rates in [0, 1]. |

## 2026-10-09 — Phase 4 decisions (Quote agent)

| # | Decision | Why |
|---|---|---|
| Q1 | **Hybrid, grounded extraction**: the LLM extracts the RFQ; a deterministic bilingual parser (`rfq_rules.py`) grounds it (quantities not written in the message are dropped, unwritten Incoterms replaced, empty fields filled) and is the full fallback when no model is available. Every correction is reported in the trace. | Robust offline demo, and a concrete anti-hallucination control for quotes (money). |
| Q2 | Development discipline: the parser was built on the **train split only**; 30 **hand-written** enquiries (written before the parser) are the honest held-out measure. First shot: **F1 0.970** (template test split 1.000 overstates real accuracy because it shares templates with train). The 3 hand-written misses were **not** fixed (numbered list, pipe table, single-Arabic-word code-switching) to keep 0.970 clean. | Same held-out discipline as Phase 3. |
| Q3 | Dataset v3: 46 enquiry country labels set to *unknown* because no place is written (only a phone code). | Labels must be answerable from the text. |
| Q4 | **Live FX** = ECB USD/INR (Frankfurter API) × CBUAE peg 3.6725 AED/USD, cached 6 h, stale fallback flagged; `fixed` provider (labelled demo rate 0.0379) for tests/offline/replay. Every quote carries rate, source, rate date and fetch time. | ECB publishes no AED rate; the AED is pegged. The Phase 1 stub (0.0436) was ~15% off the market. |
| Q5 | **Pricing v2**: unit-first rounding; volume tiers; owner **minimum margin never crossed automatically** (price held at the floor + flag); Incoterm scope table decides seller-borne charges (inland, export clearance, freight by CBM, insurance 0.25% of 110% CIF, delivery, clearance, duty 5% of CIF from the tariff master before CEPA). Charges are separate quote lines. Logistics costs are labelled **demo estimates**. | Exact, explainable, policy-bound money. |
| Q6 | New policy rules on pricing flags: **P-MARGIN-001** (held at floor / target below floor → owner, high), **P-DISC-001** (discount above cap → owner, high), **P-PRICE-001** (unpriced item / assumed Incoterm / stale FX → medium). Condition `payload_flags_any`. | Pricing exceptions reach the owner with the rule and reason visible. |
| Q7 | Gates flipped to hard: extraction F1 ≥ 0.90 (template), **extraction F1 hand-written ≥ 0.90**, e2e task success ≥ 0.90. | Delivered in this phase; regressions now fail CI. |
| Q8 | The drafter prompt receives only the fields it needs (`quote_for_prompt`), not the whole quote. | Found when replay broke: the FX fetch timestamp made every prompt unique. Smaller, deterministic prompts. |
| Q9 | Hand-written held-out score history: **0.970 first shot → 0.976** after a general fix found in the *demo sample* (a dangling "(medium size" bracket in descriptions), not from inspecting the held-out set. Both numbers are kept. | Transparent provenance of every change to a held-out number. |
