"""
conftest.py — Shared pytest setup for every backend test.

Why: tests must be offline, deterministic and isolated. Before each test we force the
fake LLM profile, point traces at a temporary folder, and clear cached settings/routers
so one test's configuration can never leak into another.
"""

import pytest

from app.config import get_settings
from app.llm.router import get_router


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """Run every test with test settings, the fake model and a private trace folder."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_PROFILE", "fake")
    monkeypatch.setenv("TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    get_settings.cache_clear()
    get_router.cache_clear()
    yield
    get_settings.cache_clear()
    get_router.cache_clear()
