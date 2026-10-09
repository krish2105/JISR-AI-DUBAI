# Makefile — one-word commands for everything you do in this repo.
# Why: nobody should need to remember long commands. Run `make help` to see them all.
# Note: recipes `cd` into subfolders, so the repo path may safely contain spaces.

.DEFAULT_GOAL := help
BACKEND := backend
UV := uv --directory $(BACKEND)

.PHONY: kb help setup test test-backend test-postgres test-frontend lint fmt run db up down data eval eval-fast eval-gate eval-baseline demo replay record build clean

help: ## Show this list of commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend and frontend dependencies, create .env
	$(UV) sync --python 3.12
	cd frontend && npm install
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

test: test-backend test-frontend ## Run every test and check (offline, fake model)

test-backend: ## Backend unit, policy, API and replay tests
	$(UV) run pytest -q

test-postgres: ## Backend tests against Postgres in Docker (make db first; uses database jisr_test)
	-docker compose exec -T db psql -U jisr -d jisr -c "CREATE DATABASE jisr_test" 2>/dev/null
	TEST_DATABASE_URL=postgresql+psycopg://jisr:jisr_local_only@localhost:55432/jisr_test $(UV) run pytest -q

test-frontend: ## Frontend type-check and lint
	cd frontend && npx tsc --noEmit && npm run lint

lint: ## Check code style (ruff + eslint)
	$(UV) run ruff check .
	cd frontend && npm run lint

fmt: ## Auto-fix code style
	$(UV) run ruff check . --fix
	$(UV) run ruff format .

run: ## Start only the API on http://localhost:8000 (auto-reloads on code changes)
	$(UV) run uvicorn app.main:app --reload --port 8000

db: ## Start Postgres + pgvector in Docker
	docker compose up -d db

up: ## Start database and API in Docker
	docker compose up -d --build

down: ## Stop Docker services
	docker compose down

kb: ## Build the knowledge-base index from data/kb_sources (first build ~30 min on CPU; later builds reuse vectors)
	$(UV) run python -m app.rag.index

data: ## Regenerate the synthetic evaluation datasets (deterministic) in data/synthetic/
	$(UV) run python -m eval.synth.generate

eval: ## Full evaluation (all suites, all splits) -> docs/EVAL_REPORT.md, then the quality gate
	$(UV) run python -m eval.run
	$(UV) run python -m eval.gate

eval-fast: ## Quick evaluation on the test split (what CI runs on every change), then the gate
	$(UV) run python -m eval.run --fast
	$(UV) run python -m eval.gate

eval-gate: ## Only re-check the latest results against thresholds and the baseline
	$(UV) run python -m eval.gate

eval-baseline: ## Accept the latest results as the new baseline (after a reviewed change; note it in DECISIONS.md)
	$(UV) run python -m eval.gate --update-baseline

demo: ## Start API + dashboard and open http://localhost:3000/en/demo
	./scripts/dev.sh

replay: ## Same as demo, fully offline: model answers come from replay/demo.cassette.jsonl
	LLM_PROFILE=replay ./scripts/dev.sh

record: ## Re-record the demo cassette (use LLM_PROFILE=prod to record real Claude answers)
	$(UV) run python ../scripts/record_demo.py

build: ## Production build of the dashboard
	cd frontend && npm run build

clean: ## Remove caches and local trace files
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache traces
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
