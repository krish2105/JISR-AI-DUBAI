"""
config.py — All runtime settings for the Jisr backend, read from environment variables.

Why this file exists:
    Every knob (which LLM profile to use, where the database lives, where traces go)
    is read here and nowhere else. Code asks `get_settings()` for a value instead of
    reading `os.environ` directly, so settings are typed, validated and testable.

How to change a setting:
    Put it in `.env` at the repo root (see `.env.example`) or export it in your shell,
    e.g. `LLM_PROFILE=prod`. Variable names are the field names in UPPER_CASE.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo root is two folders above this file: jisr-ai/backend/app/config.py -> jisr-ai/
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed settings object. Each attribute can be overridden by an environment variable."""

    # Look for a `.env` file at the repo root; ignore unknown variables instead of crashing.
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # "dev" on laptops, "prod" for the hosted demo / pilot, "test" inside pytest.
    app_env: Literal["dev", "test", "prod"] = "dev"

    # Which block of `llm/profiles.yaml` to use: fake (no network), dev (free tiers),
    # prod (Claude), replay (answers from a recorded cassette, no network).
    llm_profile: Literal["fake", "dev", "prod", "replay"] = "fake"

    # Cassette file for recording (LLM_RECORD=true) and for the replay profile.
    llm_cassette: Path | None = REPO_ROOT / "replay" / "demo.cassette.jsonl"
    llm_record: bool = False

    # Postgres in Docker for real runs; SQLite file as a zero-setup fallback.
    database_url: str = f"sqlite:///{REPO_ROOT / 'jisr.db'}"

    # Folder for JSONL traces (LLM call log, run events). Never contains raw PII.
    trace_dir: Path = REPO_ROOT / "traces"

    # Turn Claude's server-side refusal fallback on/off (see docs/DECISIONS.md E3).
    anthropic_fallbacks: bool = True

    # Hard ceiling on output tokens for a single LLM call (protects the demo budget).
    llm_max_output_tokens: int = 16000

    # Pause between agent steps so humans can follow the live demo (0 in tests).
    demo_step_delay_ms: int = 450

    # Organisation used when a request does not name one (the public no-login demo org).
    default_org_id: str = "demo"

    # Allowed browser origins for the dashboard (comma-separated in the env var).
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    """Return the one shared Settings object (created on first call, then cached)."""
    return Settings()
