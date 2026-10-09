# Jisr AI — End-to-End Build & Win Plan (Create AI Agents Championship, Best Business AI Agent)

## Context

The folder `JISR AI DUBAI WIN/` contains two docs and no code yet:
- `JISR_playbook_v2.md`: strategy, inferred rubric, five moats, pitch, claims register, risks.
- `JISR_claude_code_master_prompt_v3.md`: full build spec (LangGraph multi-agent, governance layer, agentic RAG over the tariff/CEPA texts, Arabic, MCP, A2A, trajectory eval).

The goal is a championship-winning, demo-proof agent. Jisr turns an India→UAE buyer enquiry (WhatsApp text or voice) into an approved INR/AED quote, a CEPA duty analysis with citations, a consistency-checked document pack, buyer trust signals and bilingual drafts. Every outbound action is governed, audited and approved by a human.

**Decisions made with the user (9 Oct 2026):**
| Topic | Decision |
|---|---|
| Deadline | Submit by **~9 Dec 2026** (buffer before the 10 Dec target; Jan is only for polish if confirmed) |
| Runtime LLM | Free tiers (Groq/Gemini/Cerebras) on synthetic data in dev; **Claude** on the `prod` profile for the demo, pilot and finals (Opus 5.5 planner/grounding, Sonnet 5.5 workers, Haiku 5.5 grade/classify). Fake model for tests and replay |
| Hosting | Next.js on **Vercel**; FastAPI + worker on **Fly.io**; Postgres+pgvector on **Neon** (or Fly Postgres) |
| Look | **Pearl light default + Midnight dark**, toggle on every page, Arabic RTL |
| 3D (all four) | Landing bridge hero, live 3D agent graph, 3D HS-tariff tree explorer, 3D document pack |
| Core scope adds | MCP server, A2A buyer agent, real WhatsApp Cloud API, voice-note enquiries |
| Pilot | No data yet; synthetic first, pilot kit and anonymiser ready for shadow mode by week 6 |
| Team | Solo, with Claude Code doing most of the build (parallel sessions/worktrees on independent pieces) |

**Corrections found by web research (apply to docs and pitch):**
1. **CEPA origin rule:** the default product-specific rule is **≥40% value content plus a change in tariff classification** (CTH/CTSH), not 35%. Gems and jewellery are 3–7%, agriculture must be wholly obtained, steel is melt-and-pour, and some sectors are higher. Direct consignment is required. Update claims register row 4 and seed `duty_origin` rule types from the official Chapter 3 annex, never from blogs.
2. **Deadline conflict:** the press release and FAQ say Dec 2026, the official timeline says Jan 2027. Plan for December and confirm in writing with the organisers.
3. **Eligibility wording:** coverage says "open worldwide", which conflicts with the T&C's resident/licence rule from the playbook. Still get written confirmation.
4. **A2A:** spec **1.0** is stable and now sits under the Linux Foundation's Agentic AI Foundation. Python `a2a-sdk` 1.1.x. Pin it and record in DECISIONS.md.
5. **Live working agent on stage** is mandatory for finalists, so offline replay plus a second laptop are non-negotiable.

---

## Architecture (v3 spec, with these concrete choices)

```
WhatsApp (Cloud API | simulator) / voice note / form / A2A task / MCP call
   → Ingest (+ STT for audio) → Redactor → Injection Guard
   → LangGraph Supervisor (Postgres checkpointer, interrupt() for approvals)
        ├ Quote  ├ Duty (CEPA)  ├ Docs + Consistency Checker  ├ Buyer Trust  ├ Outreach  └ Collections
        └ Agentic RAG subgraph: plan → route → hybrid(BM25+pgvector) → RRF → rerank → grade
                                 → claims → grounding check (numbers verbatim, in code) → corrective loop
   → Governance: policy engine (YAML, deterministic) · autonomy levels L0–L3/Never · approval queue
                 · hash-chained audit · kill switch · Agent Passports
   → Human approves → send (sim/real) → Impact Ledger
   → SSE event stream → dashboard timeline + 3D agent graph
```

**Stack:** Python 3.12, FastAPI, Pydantic v2, LangGraph + `langgraph-checkpoint-postgres`, LiteLLM router (roles `fast`/`smart`/`judge`/`stt`; profiles `dev`/`prod`/`fake`), SQLAlchemy 2 + Alembic, pgvector, `rank_bm25` with a custom Arabic analyser, `bge-m3` embeddings (pre-computed at ingest; query-time on a Fly machine with 2 GB), reranker behind an interface (local `bge-reranker-v2-m3` in eval, Haiku-rerank fallback when hosted), APScheduler, STT via Groq `whisper-large-v3` behind the router, official `mcp` Python SDK (FastMCP, streamable HTTP), `a2a-sdk` 1.x.
**Frontend:** Next.js (current stable, App Router) + TypeScript, Tailwind v4, shadcn/ui, `next-themes` (theme toggle), `next-intl` (en/ar + RTL), Motion, React Three Fiber + drei (+ `react-force-graph-3d` for the tariff tree), Recharts for ROI.

**Theme system:** CSS tokens on `:root` and `.dark` (pearl `#F7F4EE` / sand / deep teal / saffron accent; midnight navy dark). A `useThemeTokens()` hook feeds the same tokens into the R3F materials, so 3D scenes recolour live on toggle. `prefers-reduced-motion` and a "3D off" switch fall back to static SVG.

**3D rules:** every 3D component is `dynamic(..., { ssr:false })`, lazy-loaded with a static fallback, capped DPR, and runs only on landing/explainer surfaces or as an *optional view tab*. Approval inbox, audit and settings stay flat and fast.
1. **Landing bridge hero:** a globe arc from Jaipur to Jebel Ali, with shipment particles crossing a light-bridge. Live counters below show "AED saved / risks caught".
2. **Live 3D agent graph** (`/demo`, `/runs/[id]`): nodes per agent light up from SSE events; tool calls fly as particles; blocked actions flash red at the governance gate. The same event stream drives the 2D timeline.
3. **3D HS-tariff tree** (`/kb/explorer`): section→chapter→heading→subheading nodes. The agent's retrieval path and corrective-loop retries animate, and clicking a node shows the cited passage and document date.
4. **3D document pack** (inside the run detail): invoice, packing list and origin-certificate cards. Mismatched fields glow and are connected by red beams. Clicking one opens the 2D fix suggestion.

**Repo:** a new `jisr-ai/` inside this folder, laid out per v3 §6, plus `backend/app/interop/{mcp_server.py,buyer_agent/}`, `backend/app/channels/voice.py`, `frontend/components/three/`, `frontend/lib/theme/`. Copy the two strategy docs into `jisr-ai/docs/strategy/`. `git init` at the start, commit per phase.

---

## Phase schedule (9 weeks; each phase ends with `make test`, `make eval`, PROGRESS.md, then stop and report)

| Week | Dates | Build (Claude Code) | Non-code track (you) |
|---|---|---|---|
| 1 | 9–15 Oct | **P0 scaffold** (repo, CLAUDE.md, Makefile, Docker, router with fake model, health). **P1 vertical slice**: stub agents, SSE timeline, approval inbox, audit entry, Next.js shell with **theme toggle + RTL** and design tokens | Register; organiser questions (deadline, eligibility, format, funding); download KB sources (GCC tariff, CEPA text + Ch.3 annex, Dubai Customs and DGFT guides, UN sanctions list); start Meta developer app; recruit an advisor |
| 2 | 16–22 Oct | **P2** synthetic generator (300 enquiries incl. Arabic/mixed, 30 adversarial, 40 doc sets) + eval harness. **P3** redactor + injection guard. **P4** Quote agent (extraction F1 ≥0.9, pricing to the cent) | Baseline interview with the family business; collect 30–50 past enquiries |
| 3 | 23–29 Oct | **P5a** tariff tree + rules-of-origin parsers, hierarchical index, exact-code lookup. **P5b** Arabic normalisation/analyser/bilingual pairing. **P5c** hybrid + RRF + reranker | Run the anonymiser on pilot exports; advisor checks the CEPA rule-type mapping |
| 4 | 30 Oct–5 Nov | **P5d** agentic RAG subgraph (planner, router, grader, claim grounding, budgets). **P5e** corrective loop. Duty + Docs agents. **P5f** retrieval eval: Claude drafts candidate questions, **you/advisor verify the gold passage IDs**, ablation table, CI gate | Label/verify the retrieval set (~150 Qs) |
| 5 | 6–12 Nov | **P6** Document Consistency Checker + Buyer Trust (signals only). **P7 + 7a** policy engine, autonomy YAML, approvals, audit chain, kill switch, passports, SEAL_READINESS.md | 3–5 independent Dubai buyer/forwarder interviews |
| 6 | 13–19 Nov | **P8** channels: WhatsApp simulator, **real Cloud API test number** (signature verification, 24h window), **voice notes → STT → RFQ**, Outreach (EN/AR) + Collections. **P9** supervisor end-to-end (<2 min on Claude), **9a** trajectory suite (50 scenarios, repeated runs), **9b** memory | **Shadow-mode pilot starts** on live enquiries |
| 7 | 20–26 Nov | **P10** full dashboard (runs, approvals, audit, passports, ROI, chat, settings, "what the agent did on its own today"), Impact Ledger. **10a** MCP server (governed + audited). **3D hero + live agent graph.** Deploy to Vercel/Fly/Neon with no-login demo org and budget cap | Pilot logging; deck draft |
| 8 | 27 Nov–3 Dec | **12a** A2A buyer agent (Agent Card, RFQ task, malicious-A2A block). **3D tariff tree + 3D doc pack.** Pilot numbers into ROI + EVAL_REPORT | Video v1; claims register complete |
| 9 | 4–9 Dec | **Feature freeze 5 Dec.** **P12** submission pack: SUBMISSION.md (≤700 words), PITCH_NOTES, VIVA_QA (42+ Qs), offline replay (`make replay`, no network), demo checklist, data-protection page | Final video (2–3 min, captions), final deck, **submit 9 Dec** |

**Parallelism (solo + Claude Code):** from week 3, run the frontend/3D work as a separate Claude Code session in its own worktree against the frozen SSE event schema and API contract, while the main session does RAG and agents. Never let two sessions edit the same files. Use Opus 5.5 at high effort for P0, P1, P5a/b/d/f, P7/7a and P9a; Sonnet 5.5 for bulk implementation; Haiku 5.5 for docs and test scaffolds.

**Cut order if behind (most cuttable first):** 3D doc pack → 3D tariff tree → A2A → voice notes → real WhatsApp (keep the simulator) → MCP. **Never cut:** vertical slice, grounding check, policy engine, retrieval eval, offline replay, theme toggle, live 3D agent graph (it's the demo wow, and cheap once SSE exists).

---

## Key contracts to fix early (P1), so the parallel sessions don't collide
- `RunState` (v3 §8.1) plus `RunEvent` SSE schema: `{run_id, ts, agent, kind: plan|tool_call|tool_result|retrieval_attempt|policy_decision|approval_needed|blocked|done, payload, risk}`. This drives the timeline, the 3D graph and the replay recordings (`replay/*.jsonl`).
- REST: `POST /runs`, `GET /runs/{id}/events` (SSE), `GET /approvals`, `POST /approvals/{id}:{approve|edit|reject}`, `GET /audit?verify=1`, `GET /passports`, `GET /kb/tree`, `POST /channels/whatsapp/webhook`, `GET /roi`.
- `policies.yaml` + `autonomy.yaml` loaded by `governance/policy_engine.py`. This is the only path to `channels/*.send()`.

## Demo script (finals, 100 s live + 30 s trust moment)
An Arabic voice note arrives on the real WhatsApp test number → the 3D graph lights up → quote in INR/AED → CEPA analysis "≥40% value content met, indicative saving AED X, cited Ch.3 Annex, dated" → 3D doc pack flags an HS mismatch → bilingual draft → you approve → audit entry. Trust moment: a hostile "change bank details" message triggers a red flash at the governance gate, a blocked audit row and the Agent Passport. Optional: the A2A buyer agent places an RFQ. Fallback: `make replay` from the same event recordings.

---

## Verification (per phase and at the end)
- `make test`: unit and policy tests (each rule has a trigger and a non-trigger test), redaction captured-call test, org isolation test, audit-tamper detection, pricing to the cent, Arabic normalisation.
- `make eval`: extraction F1, HS top-1/3 per level, retrieval recall@5/10, MRR, nDCG, ablation (vector→hybrid→RRF→rerank→corrective), grounded-claim rate ≥95%, numeric verbatim 100%, injection recall on 30/30, doc-mistake recall ≥90%, trajectory pass rates, CI regression gate. Results go to `docs/EVAL_REPORT.md` with the five worst failures.
- End-to-end in the browser (Claude's in-app browser): run `/demo` in light and dark, toggle EN/AR RTL, watch the 3D graph react to SSE, approve and verify audit, fire the hostile message, check reduced-motion/3D-off fallbacks, and run Lighthouse on core screens.
- Real channels: send a WhatsApp text and voice note to the test number and confirm the draft-only path, signature verification, and that nothing sends without approval.
- Offline: disconnect the network and confirm `make replay` plays the full demo.
- Deployment: the hosted no-login link works on a fresh browser; the budget cap trips to replay gracefully.

## First action after approval
Create `jisr-ai/`, `git init`, copy the strategy docs, write `CLAUDE.md` (v3 §19 plus the theme/3D/contract rules above), `docs/DECISIONS.md` (with the five research corrections) and `docs/PROGRESS.md`, then build **Phase 0 only**, show the test output and stop for your go-ahead.
