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
    # Hosted-demo protection (Phase 10). 0 = unlimited. Past the daily token budget the router answers with the
    # deterministic offline model (labelled "budget-fallback") instead of failing; the demo keeps working.
    llm_daily_token_budget: int = 0
    public_runs_per_hour: int = 0              # per client IP, for POST /runs and the WhatsApp simulator

    # Use the local knowledge base (data/kb_index, built by `make kb`). Unit tests switch it off.
    kb_enabled: bool = True

    # Exchange rates: "fixed" (demo/tests/replay, deterministic) or "live" (ECB via Frankfurter x AED peg).
    fx_provider: Literal["fixed", "live"] = "fixed"
    fx_cache_hours: float = 6.0

    # Pause between agent steps so humans can follow the live demo (0 in tests).
    demo_step_delay_ms: int = 450

    # Organisation used when a request does not name one (the public no-login demo org).
    default_org_id: str = "demo"

    # WhatsApp Cloud API (Phase 8). Disabled -> replies go to the simulator. Secrets live only in .env.
    whatsapp_enabled: bool = False
    whatsapp_verify_token: str = ""            # you choose it; paste the same value in the Meta app webhook settings
    whatsapp_app_secret: str = ""              # Meta app secret: verifies X-Hub-Signature-256 on every webhook
    whatsapp_access_token: str = ""            # system-user token with whatsapp_business_messaging permission
    whatsapp_phone_number_id: str = ""         # the test (or production) number's id from the Meta dashboard
    whatsapp_api_version: str = "v23.0"        # Graph API version; check Meta's changelog and update
    whatsapp_org_id: str = "demo"              # organisation that receives the number's messages
    simulator_secret: str = "jisr-simulator-local-only"   # signs simulated webhooks so they take the same path

    # MCP server over HTTP (Phase 10). Empty token = not mounted (stdio mode still works locally).
    mcp_token: str = ""
    mcp_host: str = "127.0.0.1"                # public host name when deployed (DNS-rebinding protection)
    public_base_url: str = "http://localhost:8000"   # advertised in the A2A Agent Card

    # Allowed browser origins for the dashboard (comma-separated in the env var).
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    """Return the one shared Settings object (created on first call, then cached)."""
    return Settings()
