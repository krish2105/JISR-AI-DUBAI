# Jisr AI: project memory for Claude Code

- Goal: championship entry (Create AI Agents Championship, Best Business AI Agent). Priorities: working demo path, honest metrics, governance, clean code.
- Submission target: **9 Dec 2026**. Feature freeze 5 Dec. Full plan: `docs/PLAN.md`. Strategy: `docs/strategy/`.
- Always keep `make demo` and `make replay` working once they exist (Phase 1+). Never break the demo path.
- Every file: header comment (what and why), docstrings on every function, beginner-friendly inline comments.
- Never invent tariff, origin, HS or legal facts. Cite retrieved sources with document date, or flag "needs human check".
  CEPA default origin rule is >=40% value content + change in tariff classification (sector exceptions exist); take rules from the official Chapter 3 annex only.
- All LLM calls go through `backend/app/llm/router.py`. Never hardcode a model or call a provider SDK elsewhere.
  Claude is called through the official `anthropic` SDK; LiteLLM is used only for non-Claude free tiers in dev.
- Free-tier providers only ever receive `data_class="synthetic"` requests (enforced in the router, tested).
- Policy rules are deterministic code/YAML. Never move a safety decision into a prompt.
- No real customer data in repo or in free-tier calls. Only anonymised or synthetic data.
- Contracts frozen in Phase 1 (`RunEvent` SSE schema, REST routes, `RunState`) are shared by backend, frontend and 3D sessions: change them only with a DECISIONS.md entry.
- Frontend: light (pearl) default + dark (midnight) toggle on every page, Arabic RTL. 3D (React Three Fiber) is lazy-loaded with a static fallback, respects reduced motion, and never runs on approvals/audit/settings.
- After each phase: run `make test` and `make eval`, update `docs/PROGRESS.md`, commit, then stop and report.
- Every quality number comes from `backend/eval/results/` (never typed by hand). Changing `eval/thresholds.yaml` or
  `eval/baseline.json` needs a line in `docs/DECISIONS.md`. When a phase delivers a target, flip it to `gate: hard`.
- Never tune prompts or code on the `test` split; the 30 adversarial cases are test-only.
- Use parallel sessions/subagents only for independent work (e.g. frontend/3D vs RAG), never for edits to the same files.
