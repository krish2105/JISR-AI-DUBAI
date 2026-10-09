# Progress

Updated after every phase: what was built, what was tested, what is next.

## Phase 0 — Scaffold ✅ (2026-10-09)

**Built**
- Repo with `CLAUDE.md` (project memory), `docs/PLAN.md` (approved plan), `docs/DECISIONS.md` (planning decisions, 5 research corrections, engineering decisions), `docs/CLAIMS_REGISTER.md` (seeded; CEPA origin rule corrected to ≥40% + CTC), strategy docs in `docs/strategy/`.
- Backend (Python 3.12, uv): `app/config.py` (typed settings), `app/main.py` (FastAPI + CORS + `/health`).
- **LLM router** `app/llm/router.py` + `profiles.yaml`: roles `smart/worker/fast/judge/stt`; profiles `fake/dev/prod`; backends `fake` (deterministic, schema-validated), `anthropic` (official SDK: explicit effort, `messages.parse` structured output, server-side refusal fallback, typed error chain, refusal → escalate), `litellm` (free tiers, dev only). Free-tier data guard (synthetic only). Metadata-only JSONL call log.
- `Makefile` (`help setup test lint fmt run db up down eval demo replay clean`), `backend/Dockerfile`, `docker-compose.yml` (pgvector/pg17 + API), `.env.example`, `.gitignore`, `README.md`, KB and sanctions download checklists in `data/`.

**Tested** (real output)
- `make test` → `20 passed` (health, profiles validity, judge ≠ worker, Claude ids/effort, fake determinism and schema validation, free-tier trigger + non-trigger tests, log has no prompt text, max-token clamp, Claude kwargs/fallbacks/structured output, text-only extraction, refusal raised).
- `make lint` → `All checks passed!`
- `make run` → `GET /health` 200 `{"status":"ok", "llm_profile":"fake", ...}`.
- `make up` (OrbStack) → db healthy, API `/health` 200 from the container.
- `make eval`, `make demo`, `make replay` are honest placeholders until Phases 1–2.

**Notes**
- Docker runtime on this Mac is **OrbStack**: start it (`orbctl start`) before `make db` / `make up`.
- Not yet verified against live providers (no API keys used in Phase 0, by design).

**Next: Phase 1, the vertical slice**
- Freeze contracts: `RunState`, `RunEvent` SSE schema, REST routes.
- Stub agents in a LangGraph flow with a Postgres checkpointer and `interrupt()` for approval.
- Approval inbox + hash-chained audit entry (v0).
- Next.js shell: pearl/midnight tokens, theme toggle, EN/AR RTL, `/demo` with a live SSE timeline and a 2D agent graph (the 3D graph later reuses the same events).
- First replay recording so `make demo` and `make replay` work.
