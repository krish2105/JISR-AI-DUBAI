"""
main.py — The FastAPI application: the backend's front door.

Why this file exists:
    It creates the web app, allows the dashboard (Next.js on :3000) to call it, and
    exposes `/health` so humans, Docker and the hosting platform can check it is alive.
    Feature routes live in `app/api/` (runs + live events, approvals, audit, demo samples).
    On start-up it creates any missing database tables.

Run it:
    make run            (or: uv run uvicorn app.main:app --reload --port 8000)
    open http://localhost:8000/health
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import approvals, audit, demo, governance, runs
from app.config import get_settings
from app.db.session import get_engine, init_db
from app.llm.router import get_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs once at start-up (create tables) and once at shutdown (close DB connections)."""
    await init_db()
    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    """Build and configure the FastAPI app (a function so tests can create fresh apps)."""
    settings = get_settings()
    app = FastAPI(
        title="Jisr AI",
        version=__version__,
        description="Governed multi-agent system for India-to-UAE SME trade.",
        lifespan=lifespan,
    )

    # Let the browser dashboard call this API from its own origin(s).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for module in (runs, approvals, audit, demo, governance):
        app.include_router(module.router)

    @app.get("/health", tags=["system"])
    def health() -> dict:
        """Report that the API is up, plus which environment and models are active.

        Model names are shown so a demo operator can confirm at a glance that the
        hosted demo is on Claude (prod) and tests are on the fake model.
        """
        router = get_router()
        return {
            "status": "ok",
            "service": "jisr-api",
            "version": __version__,
            "env": settings.app_env,
            "llm_profile": settings.llm_profile,
            "models": {role: cfg.model for role, cfg in router.profiles[settings.llm_profile].items()},
        }

    return app


# Uvicorn looks for this module-level `app` object.
app = create_app()
