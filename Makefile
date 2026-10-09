# Makefile — one-word commands for everything you do in this repo.
# Why: nobody should need to remember long commands. Run `make help` to see them all.
# Note: recipes `cd` into subfolders, so the repo path may safely contain spaces.

.DEFAULT_GOAL := help
BACKEND := backend
UV := uv --directory $(BACKEND)

.PHONY: help setup test lint fmt run db up down eval demo replay clean

help: ## Show this list of commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend dependencies (frontend joins in Phase 1)
	$(UV) sync --python 3.12
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

test: ## Run all backend tests (offline, fake model)
	$(UV) run pytest -q

lint: ## Check code style (ruff)
	$(UV) run ruff check .

fmt: ## Auto-fix code style
	$(UV) run ruff check . --fix
	$(UV) run ruff format .

run: ## Start the API on http://localhost:8000 (auto-reloads on code changes)
	$(UV) run uvicorn app.main:app --reload --port 8000

db: ## Start Postgres + pgvector in Docker
	docker compose up -d db

up: ## Start database and API in Docker
	docker compose up -d --build

down: ## Stop Docker services
	docker compose down

eval: ## Run the evaluation harness (arrives in Phase 2)
	@echo "make eval: the evaluation harness is built in Phase 2 (see docs/PLAN.md). Nothing to evaluate yet."

demo: ## Open the one-click demo (arrives in Phase 1)
	@echo "make demo: the vertical-slice demo is built in Phase 1 (see docs/PLAN.md)."

replay: ## Offline replay of a recorded run (arrives in Phase 1/12)
	@echo "make replay: offline replay is built from Phase 1 event recordings (see docs/PLAN.md)."

clean: ## Remove caches and local trace files
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache traces
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
