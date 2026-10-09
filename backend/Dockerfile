# Dockerfile — container image for the Jisr API (used by docker-compose and Fly.io).
# Why: one reproducible image that runs the same everywhere. Dependencies are installed
# from uv.lock first so code edits don't force a full reinstall (faster rebuilds).

FROM python:3.12-slim

# uv: the fast Python package manager we use locally too.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

WORKDIR /app

# 1) Install dependencies only (cached layer while pyproject/uv.lock are unchanged).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Copy the application code.
COPY app ./app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Docker restarts the container if /health stops answering.
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
