# Jisr AI — the governed bridge for India–UAE SME trade

**Jisr** (جسر, "bridge") is a multi-agent system that turns an India-to-UAE buyer enquiry into an
approved INR/AED quote, a CEPA duty analysis with citations, a consistency-checked export document
pack, buyer trust signals and bilingual (English/Arabic) drafts. A human approves anything that
leaves the building, and every step is audited.

Entry for the **Create AI Agents Championship** (Dubai Chamber of Digital Economy), category
*Best Business AI Agent*. Plan: [docs/PLAN.md](docs/PLAN.md) · Decisions: [docs/DECISIONS.md](docs/DECISIONS.md) ·
Progress: [docs/PROGRESS.md](docs/PROGRESS.md).

> Status: **Phase 0 (scaffold)**. The agents, dashboard and demo arrive in the next phases.

## Quick start

```bash
make setup      # install backend dependencies, create .env
make test       # run the offline test suite (fake model, no keys needed)
make run        # API on http://localhost:8000  ->  open /health
```

Optional: `make db` starts Postgres + pgvector in Docker; `make up` runs DB and API in containers (start OrbStack or Docker Desktop first).

## Model profiles

| `LLM_PROFILE` | Used for | Models |
|---|---|---|
| `fake` (default) | tests, CI, offline replay | deterministic fake, no network |
| `dev` | development on **synthetic data only** (enforced in code) | free tiers via LiteLLM |
| `prod` | hosted demo, pilot, finals | Claude Opus 5.5 (planning, grounding, judge), Sonnet 5.5 (agents), Haiku 5.5 (fast tasks) |

All model calls go through [backend/app/llm/router.py](backend/app/llm/router.py).

## Layout

```
backend/   FastAPI app, agents, governance, RAG (Python 3.12, uv)
frontend/  Next.js dashboard with light/dark themes, Arabic RTL and 3D views (Phase 1+)
docs/      plan, decisions, progress, strategy, and later eval and submission docs
data/      synthetic data, official knowledge-base sources, public sanctions lists
```
