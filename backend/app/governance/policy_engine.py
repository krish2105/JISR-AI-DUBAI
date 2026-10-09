"""
policy_engine.py — Deterministic governance: may this action leave the building?

Why this file exists:
    Language models can be fooled (prompt injection). So the final say on any outside-world
    action belongs to plain code reading plain YAML rules, which a model cannot talk out of
    a decision. Even if every agent were tricked into proposing "change the bank account",
    this engine still blocks it. This is the core of Jisr's trust story.

Usage:
    engine = PolicyEngine.load()
    decision = engine.evaluate(action, PolicyContext(injection_flags=state.injection_flags))
    decision.effect  -> "allow" | "require_approval" | "block"
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from app.agents.state import PendingAction

Effect = Literal["allow", "require_approval", "block"]
RiskLevel = Literal["low", "medium", "high"]

POLICIES_PATH = Path(__file__).with_name("policies.yaml")

# Higher number = stronger effect. The strongest matching effect wins.
_STRENGTH: dict[str, int] = {"allow": 0, "require_approval": 1, "block": 2}
_RISK_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


class Condition(BaseModel):
    """The `when:` part of a rule. All given conditions must hold (logical AND)."""

    action_type_in: list[str] | None = None
    run_has_flags: bool | None = None


class Rule(BaseModel):
    """One governance rule from policies.yaml."""

    id: str
    description: str
    when: Condition
    effect: Effect
    risk: RiskLevel = "medium"


class PolicyContext(BaseModel):
    """Facts about the run that rules may look at (never free text the model wrote)."""

    injection_flags: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    """The engine's verdict on one action, with the rules that produced it."""

    effect: Effect
    risk: RiskLevel
    rule_ids: list[str]
    reasons: list[str]


class PolicyEngine:
    """Loads rules once and evaluates actions against them."""

    def __init__(self, rules: list[Rule], default_effect: Effect = "require_approval") -> None:
        self.rules = rules
        self.default_effect = default_effect

    @classmethod
    def load(cls, path: Path = POLICIES_PATH) -> "PolicyEngine":
        """Read and validate policies.yaml."""
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls([Rule(**r) for r in raw["rules"]], raw.get("default_effect", "require_approval"))

    @staticmethod
    def _matches(rule: Rule, action: PendingAction, ctx: PolicyContext) -> bool:
        """True when every condition in the rule holds for this action and context."""
        cond = rule.when
        if cond.action_type_in is not None and action.action_type not in cond.action_type_in:
            return False
        if cond.run_has_flags is not None and bool(ctx.injection_flags) != cond.run_has_flags:
            return False
        return True

    def evaluate(self, action: PendingAction, ctx: PolicyContext) -> Decision:
        """Apply all matching rules; return the strongest effect and the highest risk."""
        matched = [rule for rule in self.rules if self._matches(rule, action, ctx)]
        if not matched:
            return Decision(
                effect=self.default_effect, risk="medium", rule_ids=["DEFAULT"],
                reasons=["No rule matched; the safe default applies."],
            )
        effect = max((r.effect for r in matched), key=_STRENGTH.__getitem__)
        risk = max((r.risk for r in matched), key=_RISK_ORDER.__getitem__)
        return Decision(
            effect=effect,
            risk=risk,
            rule_ids=[r.id for r in matched],
            reasons=[r.description for r in matched],
        )


@lru_cache
def get_policy_engine() -> PolicyEngine:
    """The shared engine for the running app."""
    return PolicyEngine.load()
