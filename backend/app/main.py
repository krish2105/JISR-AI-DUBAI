"""
main.py — The FastAPI application: the backend's front door.

Why this file exists:
    It creates the web app, allows the dashboard (Next.js on :3000) to call it, and
    exposes `/health` so humans, Docker and the hosting platform can check it is alive.
    Feature routes (runs, approvals, audit, ...) are added in Phase 1 under `app/api/`.

Run it:
    make run            (or: uv run uvicorn app.main:app --reload --port 8000)
    open http://localhost:8000/health
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.llm.router import get_router


def create_app() -> FastAPI:
    """Build and configure the FastAPI app (a function so tests can create fresh apps)."""
    settings = get_settings()
    app = FastAPI(
        title="Jisr AI",
        version=__version__,
        description="Governed multi-agent system for India-to-UAE SME trade.",
    )

    # Let the browser dashboard call this API from its own origin(s).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
