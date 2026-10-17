# api.Dockerfile — the hosted Jisr API (Fly.io). Build from the REPO ROOT:  fly deploy  (see docs/DEPLOY.md)
#
# Why a repo-root build: the API reads data/kb_index (the knowledge-base index derived from public official
# documents), data/gold (governance scenarios for the passports) and replay/ (offline cassette, synthetic voice notes).
# The original downloaded PDFs are NOT copied (the index is enough). Embedding and reranker models are fetched at
# build time so the first request is fast (needs ~4 GB RAM at run time, DECISIONS K1).

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app/backend

# 1) Dependencies (cached while pyproject/uv.lock are unchanged).
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

ENV PATH="/app/backend/.venv/bin:$PATH" PYTHONUNBUFFERED=1 FASTEMBED_CACHE=/models

# 2) Models (one-time download into the image; skipped silently if the build has no network).
RUN python -c "from fastembed import TextEmbedding; from fastembed.rerank.cross_encoder import TextCrossEncoder; \
TextEmbedding('intfloat/multilingual-e5-large', cache_dir='/models'); \
TextCrossEncoder('BAAI/bge-reranker-v2-m3-int8', cache_dir='/models')" || echo "models will download on first use"

# 3) Code and data.
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY backend/eval ./eval
COPY data/kb_index /app/data/kb_index
COPY data/kb_sources/sources.csv data/kb_sources/download_status.csv /app/data/kb_sources/
COPY data/gold /app/data/gold
COPY data/synthetic /app/data/synthetic
COPY replay /app/replay

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
