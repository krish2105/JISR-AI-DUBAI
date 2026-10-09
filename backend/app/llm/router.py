"""
router.py — The ONE place where Jisr talks to language models.

Why this file exists:
    Agents must never call a model provider directly. They build an `LLMRequest` that names
    a ROLE ("smart", "worker", "fast", "judge") and the router decides which provider and
    model serve it, based on the active profile in `profiles.yaml`. This gives us:
      * one switch (LLM_PROFILE) to move from fake -> free tiers -> Claude,
      * one place to enforce "no real data on free tiers",
      * one call log for cost and latency metrics,
      * a deterministic fake model, so tests and offline replay need no network.

Backends:
    fake      -> FakeBackend: returns scripted or echo answers, instantly, offline.
    anthropic -> AnthropicBackend: official `anthropic` SDK (structured outputs, adaptive
                 thinking with an explicit effort level, server-side refusal fallbacks).
    litellm   -> LiteLLMBackend: free-tier non-Claude providers for development only.
    replay    -> ReplayBackend: answers from a recorded "cassette" file, so a demo recorded
                 on Claude can be replayed with no network (make replay).

Typical use (inside an async function):
    router = get_router()
    reply = await router.complete(LLMRequest(role="worker", system="...", prompt="..."))
    print(reply.text)
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Protocol

import yaml
from pydantic import BaseModel, Field

from app.config import Settings, get_settings

# --------------------------------------------------------------------------------------
# Data types
# --------------------------------------------------------------------------------------

Role = Literal["smart", "worker", "fast", "judge", "stt"]
Provider = Literal["fake", "anthropic", "litellm", "replay"]

# How sensitive the data in a request is. Free-tier providers may only see "synthetic".
DataClass = Literal["synthetic", "anonymised", "real"]

PROFILES_PATH = Path(__file__).with_name("profiles.yaml")


class RoleConfig(BaseModel):
    """One line of profiles.yaml: which provider/model serves a role."""

    provider: Provider
    model: str
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    free_tier: bool = False


class LLMRequest(BaseModel):
    """What an agent asks the router for. It names a role, never a model."""

    role: Role
    prompt: str                                   # the user-turn text (already redacted upstream)
    system: str = ""                              # the system prompt (instructions)
    data_class: DataClass = "synthetic"           # sensitivity label, checked against free tiers
    # Optional Pydantic model class: when set, the answer must be JSON matching it.
    output_schema: type[BaseModel] | None = Field(default=None, exclude=True)
    max_tokens: int | None = None                 # None -> settings.llm_max_output_tokens
    purpose: str = ""                             # short label for the call log, e.g. "rfq_extract"


class LLMResponse(BaseModel):
    """What the router gives back, the same shape for every provider."""

    text: str                                     # the plain-text answer ("" if only JSON)
    parsed: Any = None                            # validated schema instance when output_schema was set
    provider: Provider
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    stop_reason: str | None = None


class LLMPolicyError(RuntimeError):
    """Raised when a request breaks a data rule (e.g. real data aimed at a free tier)."""


class LLMBackendError(RuntimeError):
    """Raised when a provider call fails after the SDK's own retries."""


# --------------------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------------------


class Backend(Protocol):
    """Every backend implements one async method with this signature."""

    async def complete(self, cfg: RoleConfig, req: LLMRequest, max_tokens: int) -> LLMResponse: ...


# A scripted fake answer is either a fixed value or a function of the request.
FakeScript = str | dict | Callable[[LLMRequest], str | dict]


class FakeBackend:
    """
    Deterministic offline model used by tests, CI and offline replay.

    `scripts` maps a key to a canned answer. The key is looked up in this order:
    the request's `purpose`, then the schema class name, then the role. If nothing
    matches, the fake echoes a short, predictable string.
    """

    def __init__(self, scripts: dict[str, FakeScript] | None = None) -> None:
        self.scripts: dict[str, FakeScript] = dict(scripts or {})
        self.calls: list[LLMRequest] = []         # every request seen, for assertions in tests

    def _lookup(self, req: LLMRequest) -> FakeScript | None:
        """Find the scripted answer for this request, if any."""
        keys = [req.purpose, req.output_schema.__name__ if req.output_schema else "", req.role]
        for key in keys:
            if key and key in self.scripts:
                return self.scripts[key]
        return None

    async def complete(self, cfg: RoleConfig, req: LLMRequest, max_tokens: int) -> LLMResponse:
        """Return the scripted answer (validated against the schema if one was requested)."""
        self.calls.append(req)
        script = self._lookup(req)
        answer = script(req) if callable(script) else script

        if req.output_schema is not None:
            if answer is None:
                raise LLMBackendError(
                    f"FakeBackend has no script for schema {req.output_schema.__name__}; "
                    "add one with FakeBackend(scripts={...})."
                )
            # Accept a dict or a JSON string, and validate it exactly like a real model answer.
            data = json.loads(answer) if isinstance(answer, str) else answer
            parsed = req.output_schema.model_validate(data)
            text = parsed.model_dump_json()
        else:
            parsed = None
            text = answer if isinstance(answer, str) else (
                json.dumps(answer) if answer is not None else f"[fake:{req.role}] {req.prompt[:60]}"
            )

        return LLMResponse(
            text=text,
            parsed=parsed,
            provider="fake",
            model=cfg.model,
            input_tokens=len(req.prompt.split()),   # rough, but stable for tests
            output_tokens=len(text.split()),
            stop_reason="end_turn",
        )


class AnthropicBackend:
    """
    Claude through the official `anthropic` SDK.

    Rules we follow (see docs/DECISIONS.md E3):
      * Adaptive thinking is on by default on current models; we never send "disabled".
        Depth is controlled with output_config.effort, set per role in profiles.yaml.
      * Structured answers use `messages.parse(output_format=Schema)` so the SDK validates JSON.
      * Server-side refusal fallback (`fallbacks="default"`) is enabled unless turned off,
        so a safety-classifier false positive does not break a live demo.
    """

    # Models that accept the server-side "default" fallback mode on the Claude API.
    FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}
    FALLBACK_BETA = "server-side-fallback-2026-07-01"

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self._client = client                     # injected in tests; created lazily otherwise

    @property
    def client(self) -> Any:
        """Create the async SDK client on first use (reads ANTHROPIC_API_KEY or an `ant` profile)."""
        if self._client is None:
            import anthropic  # imported here so offline tests never need it

            self._client = anthropic.AsyncAnthropic()
        return self._client

    def build_kwargs(self, cfg: RoleConfig, req: LLMRequest, max_tokens: int) -> dict[str, Any]:
        """Build the keyword arguments for one Messages API call (pure function, unit-tested)."""
        kwargs: dict[str, Any] = {
            "model": cfg.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": req.prompt}],
        }
        if req.system:
            kwargs["system"] = req.system
        if cfg.effort:
            kwargs["output_config"] = {"effort": cfg.effort}
        if req.output_schema is not None:
            kwargs["output_format"] = req.output_schema
        if self.settings.anthropic_fallbacks and cfg.model in self.FALLBACK_MODELS:
            kwargs["betas"] = [self.FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        return kwargs

    async def complete(self, cfg: RoleConfig, req: LLMRequest, max_tokens: int) -> LLMResponse:
        """Call Claude and normalise the answer into an LLMResponse."""
        import anthropic

        kwargs = self.build_kwargs(cfg, req, max_tokens)
        # The beta namespace is needed for fallbacks; parse() validates structured output.
        messages_api = self.client.beta.messages if "betas" in kwargs else self.client.messages
        try:
            if req.output_schema is not None:
                response = await messages_api.parse(**kwargs)
            else:
                kwargs.pop("output_format", None)
                response = await messages_api.create(**kwargs)
        except anthropic.BadRequestError as exc:          # our request was wrong: do not retry
            raise LLMBackendError(f"Claude rejected the request: {exc.message}") from exc
        except anthropic.RateLimitError as exc:           # SDK already retried with backoff
            raise LLMBackendError("Claude rate limit reached after retries") from exc
        except anthropic.APIStatusError as exc:
            raise LLMBackendError(f"Claude API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMBackendError("Network error while calling Claude") from exc

        # A refusal means the whole fallback chain declined: surface it, never guess an answer.
        if response.stop_reason == "refusal":
            raise LLMBackendError("Claude declined this request (refusal); escalate to a human.")

        # Only text blocks carry the answer; thinking blocks are skipped.
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResponse(
            text=text,
            parsed=getattr(response, "parsed_output", None),
            provider="anthropic",
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )


class LiteLLMBackend:
    """Free-tier non-Claude providers (Groq, Gemini, Cerebras) through LiteLLM. Dev only."""

    async def complete(self, cfg: RoleConfig, req: LLMRequest, max_tokens: int) -> LLMResponse:
        """Call the provider via LiteLLM; ask for JSON and validate it when a schema is given."""
        import litellm  # heavy import, only loaded when actually used

        messages = []
        if req.system:
            messages.append({"role": "system", "content": req.system})
        messages.append({"role": "user", "content": req.prompt})

        extra: dict[str, Any] = {}
        if req.output_schema is not None:
            extra["response_format"] = req.output_schema   # LiteLLM converts this to JSON mode
        try:
            response = await litellm.acompletion(
                model=cfg.model, messages=messages, max_tokens=max_tokens, **extra
            )
        except Exception as exc:                  # LiteLLM wraps many provider error types
            raise LLMBackendError(f"{cfg.model} call failed: {exc}") from exc

        text = response.choices[0].message.content or ""
        parsed = req.output_schema.model_validate_json(text) if req.output_schema else None
        usage = getattr(response, "usage", None)
        return LLMResponse(
            text=text,
            parsed=parsed,
            provider="litellm",
            model=cfg.model,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            stop_reason=response.choices[0].finish_reason,
        )


def cassette_key(req: LLMRequest) -> str:
    """Stable key for a request: same role, purpose, prompts and schema -> same key."""
    material = json.dumps(
        {
            "role": req.role,
            "purpose": req.purpose,
            "system": req.system,
            "prompt": req.prompt,
            "schema": req.output_schema.__name__ if req.output_schema else None,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class ReplayBackend:
    """
    Answers from a cassette: a JSONL file of recorded responses (see LLMRouter recording).

    Why: the finals need a demo that works with no network. Record the demo once on
    Claude (`LLM_RECORD=true`), then run with `LLM_PROFILE=replay` and every agent gets
    exactly the answers Claude gave, instantly and offline.
    """

    def __init__(self, cassette_path: Path | None) -> None:
        self.cassette_path = cassette_path
        self._entries: dict[str, dict] | None = None

    def _load(self) -> dict[str, dict]:
        """Read the cassette file once (later lines win if a key repeats)."""
        if self._entries is None:
            self._entries = {}
            if self.cassette_path and Path(self.cassette_path).exists():
                for line in Path(self.cassette_path).read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        entry = json.loads(line)
                        self._entries[entry["key"]] = entry
        return self._entries

    async def complete(self, cfg: RoleConfig, req: LLMRequest, max_tokens: int) -> LLMResponse:
        """Return the recorded answer for this exact request, or fail clearly."""
        entry = self._load().get(cassette_key(req))
        if entry is None:
            raise LLMBackendError(
                f"No recorded answer for purpose={req.purpose!r} in cassette {self.cassette_path}. "
                "Re-record the demo with LLM_RECORD=true."
            )
        parsed = req.output_schema.model_validate(entry["parsed"]) if req.output_schema else None
        return LLMResponse(
            text=entry["text"],
            parsed=parsed,
            provider="replay",
            model=f"replay:{entry['model']}",
            input_tokens=entry.get("input_tokens", 0),
            output_tokens=entry.get("output_tokens", 0),
            stop_reason=entry.get("stop_reason"),
        )


# --------------------------------------------------------------------------------------
# The router
# --------------------------------------------------------------------------------------


def load_profiles(path: Path = PROFILES_PATH) -> dict[str, dict[str, RoleConfig]]:
    """Read profiles.yaml into {profile: {role: RoleConfig}}, validating every entry."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        profile: {role: RoleConfig(**cfg) for role, cfg in roles.items()}
        for profile, roles in raw.items()
    }


class LLMRouter:
    """Routes role-based requests to the right backend and records every call."""

    def __init__(
        self,
        settings: Settings | None = None,
        backends: dict[str, Backend] | None = None,
        profiles: dict[str, dict[str, RoleConfig]] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.profiles = profiles or load_profiles()
        if self.settings.llm_profile not in self.profiles:
            raise ValueError(f"Unknown LLM profile {self.settings.llm_profile!r}")
        # Backends can be injected (tests); otherwise create the standard ones.
        if backends is None:
            from app.llm.fake_scripts import DEMO_SCRIPTS  # imported here to avoid a circular import

            backends = {
                "fake": FakeBackend(DEMO_SCRIPTS),
                "anthropic": AnthropicBackend(self.settings),
                "litellm": LiteLLMBackend(),
                "replay": ReplayBackend(self.settings.llm_cassette),
            }
        self.backends: dict[str, Backend] = backends

    def config_for(self, role: Role) -> RoleConfig:
        """Return the model configuration for a role in the active profile."""
        return self.profiles[self.settings.llm_profile][role]

    def check_data_policy(self, cfg: RoleConfig, req: LLMRequest) -> None:
        """Refuse to send anything but synthetic data to a free-tier provider (DECISIONS E4)."""
        if cfg.free_tier and req.data_class != "synthetic":
            raise LLMPolicyError(
                f"Blocked: {req.data_class!r} data may not be sent to free-tier model {cfg.model}. "
                "Use LLM_PROFILE=prod (paid, no-training terms) or synthetic data."
            )

    def check_pii_tripwire(self, req: LLMRequest) -> None:
        """Last line of defence: refuse to send unmistakable personal/financial identifiers to ANY model.

        Agents must send redacted text; if an email address, IBAN, Emirates ID, tax number or card
        number is still present, something upstream forgot to redact, so we stop here (fail closed).
        """
        from app.security.redactor import find_high_risk_pii  # local import avoids a cycle

        found = find_high_risk_pii(f"{req.system}\n{req.prompt}")
        if found:
            raise LLMPolicyError(f"Blocked: unredacted {', '.join(found)} in a {req.purpose or req.role} request.")

    async def complete(self, req: LLMRequest) -> LLMResponse:
        """Answer one request: pick the model, enforce data rules, call it, log it."""
        cfg = self.config_for(req.role)
        self.check_data_policy(cfg, req)
        self.check_pii_tripwire(req)
        max_tokens = min(req.max_tokens or self.settings.llm_max_output_tokens,
                         self.settings.llm_max_output_tokens)

        started = time.perf_counter()
        response = await self.backends[cfg.provider].complete(cfg, req, max_tokens)
        response.latency_ms = round((time.perf_counter() - started) * 1000, 2)

        self._log_call(cfg, req, response)
        if self.settings.llm_record:
            self._record(req, response)
        return response

    def _record(self, req: LLMRequest, resp: LLMResponse) -> None:
        """Append this answer to the cassette so it can be replayed offline later.

        Real (non-anonymised) customer data is never recorded: cassettes are demo assets.
        """
        if req.data_class == "real" or self.settings.llm_cassette is None:
            return
        path = Path(self.settings.llm_cassette)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "key": cassette_key(req),
            "role": req.role,
            "purpose": req.purpose,
            "text": resp.text,
            "parsed": resp.parsed.model_dump(mode="json") if isinstance(resp.parsed, BaseModel) else resp.parsed,
            "model": resp.model,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "stop_reason": resp.stop_reason,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _log_call(self, cfg: RoleConfig, req: LLMRequest, resp: LLMResponse) -> None:
        """Append one JSON line per call. Only metadata: no prompt or answer text (no PII)."""
        trace_dir = Path(self.settings.trace_dir)
        trace_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "profile": self.settings.llm_profile,
            "role": req.role,
            "purpose": req.purpose,
            "provider": resp.provider,
            "model": resp.model,
            "data_class": req.data_class,
            # A hash lets us spot repeated prompts without storing their content.
            "prompt_sha256": hashlib.sha256(req.prompt.encode("utf-8")).hexdigest()[:16],
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "latency_ms": resp.latency_ms,
            "stop_reason": resp.stop_reason,
        }
        with (trace_dir / "llm_calls.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")


@lru_cache
def get_router() -> LLMRouter:
    """Return the shared router for the running app (tests build their own instances)."""
    return LLMRouter()
