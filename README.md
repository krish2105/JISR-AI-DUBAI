# Jisr AI — the governed bridge for India–UAE SME trade

**Jisr** (جسر, "bridge") is a multi-agent system that turns an India-to-UAE buyer enquiry into an
approved INR/AED quote, a CEPA duty analysis with citations, a consistency-checked export document
pack, buyer trust signals and bilingual (English/Arabic) drafts. A human approves anything that
leaves the building, and every step is audited.

Entry for the **Create AI Agents Championship** (Dubai Chamber of Digital Economy), category
*Best Business AI Agent*. Plan: [docs/PLAN.md](docs/PLAN.md) · Decisions: [docs/DECISIONS.md](docs/DECISIONS.md) ·
Progress: [docs/PROGRESS.md](docs/PROGRESS.md).

> Status: **Phase 2 (data + evaluation)** on top of the Phase 1 vertical slice. Enquiry → agents → governance → approval → audit works end to end
> in a bilingual dashboard. Specialist agents marked "stub" are deepened in later phases.

## Quick start

```bash
make setup      # install backend + dashboard dependencies, create .env
make test       # offline tests + frontend type-check and lint (fake model, no keys needed)
make demo       # API :8000 + dashboard :3000, opens http://localhost:3000/en/demo
make replay     # the same demo fully offline (model answers from replay/demo.cassette.jsonl)
```

Quality is measured, not claimed:

```bash
make eval-fast  # test split, ~5 s: metrics + quality gate (what CI runs)
make eval       # all suites, all splits -> docs/EVAL_REPORT.md, then the gate
make test-postgres  # backend tests on Postgres 17 + pgvector (after `make db`)
```

See [docs/EVAL_REPORT.md](docs/EVAL_REPORT.md) for the current numbers (bad ones included) and
[data/synthetic/README.md](data/synthetic/README.md) for how the evaluation data was built.

In the demo: run the English or Arabic enquiry, watch the agent graph and timeline, then approve the
draft (sent through a simulator). Run the hostile sample to see the policy engine block a bank-detail
change. `/approvals` is the inbox, `/audit` shows the hash-chain check. Toggle the theme (moon/sun)
and the language (العربية / English) in the top bar.

### Knowledge base (CEPA duty analysis)

The duty and document agents answer from official sources only: the UAE tariff (Dubai Customs, EN + AR), the
India–UAE CEPA Final Agreement (Annex 3B origin rules parsed into 137 rules) and customs guides. The originals are
not committed; build the local index once:

```bash
python3 scripts/download_kb_sources.py   # official hosts only, SHA-256 recorded
make kb         # tariff tree + rules + chunks + embeddings -> data/kb_index/ (first build ~30 min on CPU)
```

`make kb` downloads two models (~2.8 GB, cached in `~/.cache/fastembed`). Without the index the app still runs and
the duty card says the knowledge base is unavailable; the retrieval eval suite reports SKIP. Sources, corrections and
gaps (no official Annex 2B yet, so savings are shown as "up to"): [data/kb_sources/SOURCES_REVIEW.md](data/kb_sources/SOURCES_REVIEW.md).

### Dashboard pages

`/demo` live run (2D / 3D agent graph, 3D document pack) · `/approvals` inbox + collections · `/audit` hash chain ·
`/governance` kill switch, autonomy levels, policies, Agent Passports · `/tariff` 3D tariff explorer · `/impact` Impact
Ledger. 3D turns off under reduced motion.

### Agent to agent (A2A)

A buyer's procurement agent can request a quotation over A2A (Agent Card at `/.well-known/agent-card.json`). The quote
returns only after the owner approves it. Try it: `uv --directory backend run python ../scripts/buyer_agent.py`
(add `--malicious` to see a hostile agent rejected).

### MCP and hosting

`uv --directory backend run python -m app.interop.mcp_server` serves Jisr's tools to MCP clients (stdio); with
`MCP_TOKEN` set the API also serves `/mcp/`. Hosting (Fly + Neon + Vercel): [docs/DEPLOY.md](docs/DEPLOY.md).

### WhatsApp and voice notes

The demo page has a **WhatsApp voice notes** card: synthetic Arabic and English voice notes go through the same
signed webhook path as real messages (speech-to-text → quote). To connect a real WhatsApp test number, follow
[docs/WHATSAPP_SETUP.md](docs/WHATSAPP_SETUP.md). `/approvals` → "Check overdue invoices" drafts payment reminders
(never with bank details) for approval.

Optional: `make db` starts Postgres + pgvector in Docker; `make up` runs DB and API in containers (start OrbStack or Docker Desktop first).

## Model profiles

| `LLM_PROFILE` | Used for | Models |
|---|---|---|
| `fake` (default) | tests, CI, offline replay | deterministic fake, no network |
| `dev` | development on **synthetic data only** (enforced in code) | free tiers via LiteLLM |
| `prod` | hosted demo, pilot, finals | Claude Opus 5.5 (planning, grounding, judge), Sonnet 5.5 (agents), Haiku 5.5 (fast tasks) |
| `replay` | finals fallback, no network | answers recorded by `make record` |

All model calls go through [backend/app/llm/router.py](backend/app/llm/router.py).

Contracts between backend and dashboard: [docs/CONTRACTS.md](docs/CONTRACTS.md).

## Layout

```
backend/   FastAPI app, agents, governance, RAG (Python 3.12, uv)
frontend/  Next.js 16 dashboard: light/dark themes, English + Arabic (RTL), live agent graph (3D views later)
replay/    recorded demo cassette + event streams for offline replay
docs/      plan, decisions, progress, strategy, and later eval and submission docs
data/      synthetic data, official knowledge-base sources, public sanctions lists
```
