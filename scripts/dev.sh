#!/usr/bin/env bash
# dev.sh — start the API (:8000) and the dashboard (:3000) together; Ctrl+C stops both.
#
# Usage:  scripts/dev.sh            (uses LLM_PROFILE from .env, default fake)
#         LLM_PROFILE=replay scripts/dev.sh   (offline replay of the recorded demo)
# Why a script: `make demo` and `make replay` both need two processes; this keeps them
# in one terminal and cleans up both on exit.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "▶ API      http://localhost:8000/health   (LLM_PROFILE=${LLM_PROFILE:-from .env})"
uv --directory "$ROOT/backend" run uvicorn app.main:app --port 8000 &

echo "▶ Dashboard http://localhost:3000/en/demo"
(cd "$ROOT/frontend" && npm run dev -- --port 3000) &

# Open the demo page once the dashboard answers (macOS `open`; ignored elsewhere).
if [ "${OPEN_BROWSER:-1}" = "1" ]; then
  ( for _ in $(seq 1 60); do curl -sf -o /dev/null http://localhost:3000/en/demo && { open http://localhost:3000/en/demo 2>/dev/null || true; break; }; sleep 1; done ) &
fi
wait
