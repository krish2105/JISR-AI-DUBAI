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
from app.api import approvals, audit, auth, channels, collections, demo, governance, impact, kb, runs, team
from app.config import get_settings
from app.db.session import get_engine, init_db
from app.llm.router import get_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs once at start-up (create tables) and once at shutdown (close DB connections)."""
    from app.auth.service import purge_expired_sandboxes
    from app.auth.tokens import signing_secret

    signing_secret()                      # production refuses to start without AUTH_SECRET (Phase 13)
    await init_db()
    await purge_expired_sandboxes()
    if getattr(app.state, "mcp", None) is not None:          # the MCP HTTP transport needs its session manager
        async with app.state.mcp.session_manager.run():
            await _seed_demo()
            yield
        await get_engine().dispose()
        return
    await _seed_demo()
    yield
    await get_engine().dispose()


async def _seed_demo() -> None:
    """Synthetic invoices for the collections demo (demo organisation only)."""
    if get_settings().default_org_id == "demo":
        from app.agents.collections import seed_demo_invoices

        await seed_demo_invoices("demo")


class BearerGuard:
    """Tiny ASGI wrapper for /mcp: `Authorization: Bearer <key>` is required.

    Accepted keys: the server-wide MCP_TOKEN (acts for the default organisation, constant-time compare) or an
    organisation's own API key from Team settings (acts for that organisation only, Phase 13).
    """

    def __init__(self, app, token: str) -> None:
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send) -> None:
        import hmac

        from app.auth.service import org_for_api_key
        from app.interop.mcp_server import MCP_ORG

        if scope["type"] == "http":
            auth = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
            org = None
            if self.token and hmac.compare_digest(auth, f"Bearer {self.token}"):
                org = get_settings().default_org_id
            elif auth[:7].lower() == "bearer ":
                org = await org_for_api_key(auth[7:].strip())
            if org is None:
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"detail":"unauthorized"}'})
                return
            reset = MCP_ORG.set(org)
            try:
                await self.app(scope, receive, send)
            finally:
                MCP_ORG.reset(reset)
            return
        await self.app(scope, receive, send)


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

    for module in (auth, team, runs, approvals, audit, demo, governance, channels, collections, impact, kb):
        app.include_router(module.router)

    # A2A: Agent Card at /.well-known/agent-card.json and JSON-RPC at /a2a (buyer agents request quotations).
    from app.interop.a2a_server import mount as mount_a2a

    mount_a2a(app, settings.public_base_url)

    # MCP over streamable HTTP at /mcp when MCP_TOKEN or MCP_HTTP is set; every request needs a key (BearerGuard).
    app.state.mcp = None
    if settings.mcp_token or settings.mcp_http:
        from mcp.server.transport_security import TransportSecuritySettings

        from app.interop.mcp_server import mcp

        security = TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                             allowed_hosts=[settings.mcp_host, f"{settings.mcp_host}:*", "testserver"],
                                             allowed_origins=[])
        mcp_http = mcp.streamable_http_app(streamable_http_path="/", stateless_http=True, json_response=True,
                                           transport_security=security)
        app.state.mcp = mcp
        app.mount("/mcp", BearerGuard(mcp_http, settings.mcp_token))

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
            "budget": router.budget_status(),
        }

    return app


# Uvicorn looks for this module-level `app` object.
app = create_app()
