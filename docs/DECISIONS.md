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
