"""
conftest.py — Shared pytest setup for every backend test.

Why: tests must be offline, deterministic and isolated. Before each test we force the
fake LLM profile, give the test its own SQLite database and trace folder, turn off the
demo pacing delay, and clear every cached object (settings, router, DB engine, policies)
so one test's configuration can never leak into another.

Postgres: set TEST_DATABASE_URL (e.g. postgresql+psycopg://jisr:jisr_local_only@localhost:5432/jisr_test)
to run the same tests against Postgres; tables are dropped and recreated before every test.
"""

import asyncio
import os

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.agents.graph import build_graph
from app.config import get_settings
from app.db.models import Base
from app.db.session import get_engine, init_db, reset_engine_cache, to_async_url
from app.governance.policy_engine import get_policy_engine
from app.llm.router import get_router
from app.profile import get_business_profile

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


async def _reset_postgres(url: str) -> None:
    """Drop and recreate all tables so each test starts from an empty Postgres database."""
    engine = create_async_engine(to_async_url(url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


def _clear_caches() -> None:
    """Forget every cached singleton."""
    for cached in (get_settings, get_router, get_policy_engine, get_business_profile, build_graph):
        cached.cache_clear()
    reset_engine_cache()


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """Run every test with test settings, the fake model, a private DB and trace folder."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_PROFILE", "fake")
    monkeypatch.setenv("LLM_RECORD", "false")
    monkeypatch.setenv("LLM_CASSETTE", str(tmp_path / "cassette.jsonl"))
    monkeypatch.setenv("TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL or f"sqlite:///{tmp_path / 'test.db'}")
    if TEST_DATABASE_URL:
        asyncio.run(_reset_postgres(TEST_DATABASE_URL))
    monkeypatch.setenv("DEMO_STEP_DELAY_MS", "0")
    _clear_caches()
    yield
    _clear_caches()


@pytest.fixture
async def db_ready():
    """Create the tables for async (non-HTTP) tests, and close connections afterwards."""
    await init_db()
    yield
    await get_engine().dispose()
