"""
test_router.py — Tests for the LLM router (backend/app/llm/router.py).

What we prove here, all offline:
  1. profiles.yaml is valid and every profile defines every role.
  2. The fake model is deterministic and validates structured answers like a real model.
  3. The data policy blocks non-synthetic data from free tiers (and does not over-block).
  4. The call log stores metadata only, never prompt text.
  5. Claude requests are built the way Anthropic's current API expects
     (explicit effort, no "disabled" thinking, refusal fallbacks, structured output).
"""

import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.llm.router import (
    AnthropicBackend,
    FakeBackend,
    LLMBackendError,
    LLMPolicyError,
    LLMRequest,
    LLMRouter,
    RoleConfig,
    load_profiles,
)

ROLES = {"smart", "worker", "fast", "judge", "stt"}


class TinyRFQ(BaseModel):
    """A small schema used to test structured answers."""

    buyer_name: str
    quantity: int


# ---------- 1. profiles.yaml ----------------------------------------------------------


def test_every_profile_defines_every_role():
    """Every profile (fake, dev, prod, replay) must map all five roles to a model."""
    profiles = load_profiles()
    assert set(profiles) == {"fake", "dev", "prod", "replay"}
    for name, roles in profiles.items():
        assert set(roles) == ROLES, f"profile {name} is missing roles"


def test_judge_model_differs_from_worker_model():
    """v3 §22.8: the LLM judge must not be the same model as the agents it grades."""
    for name, roles in load_profiles().items():
        assert roles["judge"].model != roles["worker"].model, name


def test_prod_uses_current_claude_models_without_date_suffixes():
    """Prod roles use the exact current Claude ids (Opus 5.5 / Sonnet 5.5 / Haiku 5.5)."""
    prod = load_profiles()["prod"]
    assert prod["smart"].model == "claude-opus-5-5"
    assert prod["worker"].model == "claude-sonnet-5-5"
    assert prod["fast"].model == "claude-haiku-5-5"
    for role in ("smart", "worker", "fast", "judge"):
        assert prod[role].provider == "anthropic"
        assert prod[role].effort is not None, "Opus 5.5 defaults to medium, so effort is always explicit"


# ---------- 2. fake backend -----------------------------------------------------------


async def test_fake_echo_is_deterministic():
    """Without a script, the fake echoes a predictable string."""
    router = LLMRouter()
    first = await router.complete(LLMRequest(role="worker", prompt="Need 500 brass lamps"))
    second = await router.complete(LLMRequest(role="worker", prompt="Need 500 brass lamps"))
    assert first.text == second.text == "[fake:worker] Need 500 brass lamps"
    assert first.provider == "fake"


async def test_fake_structured_answer_is_validated():
    """A scripted dict is validated against the requested schema, like a real model answer."""
    fake = FakeBackend(scripts={"TinyRFQ": {"buyer_name": "Buyer-001", "quantity": 500}})
    router = LLMRouter(backends={"fake": fake})
    reply = await router.complete(LLMRequest(role="worker", prompt="...", output_schema=TinyRFQ))
    assert isinstance(reply.parsed, TinyRFQ)
    assert reply.parsed.quantity == 500


async def test_fake_bad_structured_answer_fails_loudly():
    """A script that does not match the schema raises instead of passing bad data on."""
    fake = FakeBackend(scripts={"TinyRFQ": {"buyer_name": "Buyer-001"}})   # quantity missing
    router = LLMRouter(backends={"fake": fake})
    with pytest.raises(ValidationError):
        await router.complete(LLMRequest(role="worker", prompt="...", output_schema=TinyRFQ))


async def test_fake_without_script_for_schema_raises():
    """Asking for a schema with no script is a test-setup bug, so it fails clearly."""
    router = LLMRouter()
    with pytest.raises(LLMBackendError, match="no script"):
        await router.complete(LLMRequest(role="worker", prompt="...", output_schema=TinyRFQ))


async def test_purpose_script_takes_priority_over_role():
    """Scripts are looked up by purpose first, so one role can serve different tasks."""
    fake = FakeBackend(scripts={"rfq_extract": "by-purpose", "worker": "by-role"})
    router = LLMRouter(backends={"fake": fake})
    reply = await router.complete(LLMRequest(role="worker", prompt="x", purpose="rfq_extract"))
    assert reply.text == "by-purpose"


# ---------- 3. data policy ------------------------------------------------------------


def _router_with_free_tier_worker() -> LLMRouter:
    """A router whose worker role is a free-tier model, but answered by the fake backend."""
    profiles = load_profiles()
    profiles["fake"]["worker"] = RoleConfig(provider="fake", model="free-model", free_tier=True)
    return LLMRouter(profiles=profiles)


@pytest.mark.parametrize("data_class", ["real", "anonymised"])
async def test_free_tier_blocks_non_synthetic_data(data_class):
    """Trigger test: real or anonymised data aimed at a free tier is blocked."""
    router = _router_with_free_tier_worker()
    with pytest.raises(LLMPolicyError, match="free-tier"):
        await router.complete(LLMRequest(role="worker", prompt="x", data_class=data_class))


async def test_free_tier_allows_synthetic_data():
    """Non-trigger test: synthetic data may go to a free tier."""
    router = _router_with_free_tier_worker()
    reply = await router.complete(LLMRequest(role="worker", prompt="x", data_class="synthetic"))
    assert reply.text


async def test_paid_model_allows_real_data():
    """Non-trigger test: the rule only applies to free tiers, not paid no-training models."""
    router = LLMRouter()   # fake profile roles are not free_tier
    reply = await router.complete(LLMRequest(role="worker", prompt="x", data_class="real"))
    assert reply.text


# ---------- 4. call log ---------------------------------------------------------------


async def test_call_log_has_metadata_but_no_prompt_text():
    """Each call writes one JSONL line; the secret-looking prompt text never appears in it."""
    router = LLMRouter()
    secret = "Call Mr Sharma on +91 98290 00000"
    await router.complete(LLMRequest(role="fast", prompt=secret, purpose="classify"))

    log_file = get_settings().trace_dir / "llm_calls.jsonl"
    content = log_file.read_text(encoding="utf-8")
    assert secret not in content and "98290" not in content
    record = json.loads(content.strip().splitlines()[-1])
    assert record["role"] == "fast" and record["purpose"] == "classify"
    assert len(record["prompt_sha256"]) == 16


async def test_max_tokens_is_clamped_to_settings_ceiling(monkeypatch):
    """An agent cannot ask for more output tokens than the configured ceiling."""
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "1000")
    get_settings.cache_clear()
    seen = {}

    class SpyBackend(FakeBackend):
        async def complete(self, cfg, req, max_tokens):
            seen["max_tokens"] = max_tokens
            return await super().complete(cfg, req, max_tokens)

    router = LLMRouter(backends={"fake": SpyBackend()})
    await router.complete(LLMRequest(role="worker", prompt="x", max_tokens=50_000))
    assert seen["max_tokens"] == 1000


# ---------- 5. Claude request building ------------------------------------------------


def _anthropic(fallbacks: bool = True, client=None) -> AnthropicBackend:
    """Build an AnthropicBackend with settings that toggle refusal fallbacks."""
    settings = get_settings().model_copy(update={"anthropic_fallbacks": fallbacks})
    return AnthropicBackend(settings, client=client)


def test_claude_kwargs_set_effort_and_fallbacks_for_opus():
    """Opus 5.5: explicit effort, server-side 'default' fallback with its beta header."""
    cfg = RoleConfig(provider="anthropic", model="claude-opus-5-5", effort="high")
    kwargs = _anthropic().build_kwargs(cfg, LLMRequest(role="smart", prompt="p", system="s"), 4000)
    assert kwargs["output_config"] == {"effort": "high"}
    assert kwargs["fallbacks"] == "default"
    assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert kwargs["system"] == "s"
    assert "thinking" not in kwargs, "never send thinking: disabled (400 on Opus 5.5)"


def test_claude_kwargs_no_fallbacks_for_haiku_or_when_disabled():
    """Haiku 5.5 has no server-side fallback; and the switch turns it off everywhere."""
    haiku = RoleConfig(provider="anthropic", model="claude-haiku-5-5", effort="low")
    assert "fallbacks" not in _anthropic().build_kwargs(haiku, LLMRequest(role="fast", prompt="p"), 256)
    opus = RoleConfig(provider="anthropic", model="claude-opus-5-5", effort="high")
    assert "fallbacks" not in _anthropic(fallbacks=False).build_kwargs(
        opus, LLMRequest(role="smart", prompt="p"), 256
    )


def test_claude_kwargs_include_output_format_for_schema():
    """Structured requests pass the Pydantic class so the SDK validates the JSON answer."""
    cfg = RoleConfig(provider="anthropic", model="claude-sonnet-5-5", effort="medium")
    req = LLMRequest(role="worker", prompt="p", output_schema=TinyRFQ)
    assert _anthropic().build_kwargs(cfg, req, 1000)["output_format"] is TinyRFQ


class _StubMessages:
    """Stands in for client.messages / client.beta.messages and records the call."""

    def __init__(self, response):
        self.response, self.kwargs = response, None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response

    async def parse(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _stub_client(response):
    """A fake Anthropic client exposing both the regular and beta messages APIs."""
    messages = _StubMessages(response)
    return SimpleNamespace(messages=messages, beta=SimpleNamespace(messages=messages)), messages


def _claude_response(stop_reason="end_turn"):
    """A response shaped like the SDK's: a thinking block, then text."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text="Hello")],
        model="claude-sonnet-5-5",
        usage=SimpleNamespace(input_tokens=12, output_tokens=3),
        stop_reason=stop_reason,
    )


async def test_claude_complete_returns_only_text_blocks():
    """Thinking blocks are skipped; the text answer and token usage come through."""
    client, messages = _stub_client(_claude_response())
    backend = _anthropic(client=client)
    cfg = RoleConfig(provider="anthropic", model="claude-sonnet-5-5", effort="medium")
    reply = await backend.complete(cfg, LLMRequest(role="worker", prompt="hi"), 500)
    assert reply.text == "Hello"
    assert reply.input_tokens == 12
    assert "output_format" not in messages.kwargs   # plain create() never gets a schema arg


async def test_claude_refusal_is_raised_not_guessed():
    """If the whole fallback chain refuses, the router raises so a human is involved."""
    client, _ = _stub_client(_claude_response(stop_reason="refusal"))
    backend = _anthropic(client=client)
    cfg = RoleConfig(provider="anthropic", model="claude-opus-5-5", effort="high")
    with pytest.raises(LLMBackendError, match="refusal"):
        await backend.complete(cfg, LLMRequest(role="smart", prompt="hi"), 500)
