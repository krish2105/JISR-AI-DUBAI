"""
policy_engine.py — Deterministic governance: may this action leave the building?

Why this file exists:
    Language models can be fooled (prompt injection). So the final say on any outside-world
    action belongs to plain code reading plain YAML rules, which a model cannot talk out of
    a decision. Even if every agent were tricked into proposing "change the bank account",
    this engine still blocks it. This is the core of Jisr's trust story.

Two deterministic inputs decide every action:
    policies.yaml   rules: block / require_approval / allow, with a risk level
    autonomy.yaml   how much each action type may happen without a human (NEVER, L0-L3)
The final effect is the strongest of the two, so autonomy can only add caution.

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
AUTONOMY_PATH = Path(__file__).with_name("autonomy.yaml")
Level = Literal["NEVER", "L0", "L1", "L2", "L3"]

# Higher number = stronger effect. The strongest matching effect wins.
_STRENGTH: dict[str, int] = {"allow": 0, "require_approval": 1, "block": 2}
_RISK_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


class Condition(BaseModel):
    """The `when:` part of a rule. All given conditions must hold (logical AND)."""

    action_type_in: list[str] | None = None
    run_has_flags: bool | None = None
    payload_flags_any: list[str] | None = None      # any of these codes in payload["pricing_flags"]
    buyer_signals_any: list[str] | None = None      # any of these buyer-trust signals was raised in the run
    kill_switch_engaged: bool | None = None         # the organisation's kill switch is on


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
    buyer_signals: list[str] = Field(default_factory=list)      # signal names from the Buyer Trust tool
    kill_switch: bool = False                                     # organisation-wide stop for outbound actions


class Decision(BaseModel):
    """The engine's verdict on one action, with the rules that produced it."""

    effect: Effect
    risk: RiskLevel
    rule_ids: list[str]
    reasons: list[str]
    autonomy: Level = "L1"                     # the action type's autonomy level
    policy_effect: Effect | None = None        # the policies' effect before the autonomy cap


class PolicyEngine:
    """Loads rules once and evaluates actions against them."""

    def __init__(self, rules: list[Rule], default_effect: Effect = "require_approval",
                 autonomy: dict[str, dict] | None = None, default_level: Level = "L1") -> None:
        self.rules = rules
        self.default_effect = default_effect
        self.autonomy = autonomy or {}
        self.default_level = default_level

    @classmethod
    def load(cls, path: Path = POLICIES_PATH, autonomy_path: Path = AUTONOMY_PATH) -> "PolicyEngine":
        """Read and validate policies.yaml and autonomy.yaml."""
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        aut = yaml.safe_load(autonomy_path.read_text(encoding="utf-8")) if autonomy_path.exists() else {}
        return cls([Rule(**r) for r in raw["rules"]], raw.get("default_effect", "require_approval"),
                   aut.get("actions", {}), aut.get("default_level", "L1"))

    def level_for(self, action_type: str) -> Level:
        """Autonomy level of an action type (default for unknown types)."""
        return (self.autonomy.get(action_type) or {}).get("level", self.default_level)

    @staticmethod
    def _matches(rule: Rule, action: PendingAction, ctx: PolicyContext) -> bool:
        """True when every condition in the rule holds for this action and context."""
        cond = rule.when
        if cond.action_type_in is not None and action.action_type not in cond.action_type_in:
            return False
        if cond.run_has_flags is not None and bool(ctx.injection_flags) != cond.run_has_flags:
            return False
        if cond.payload_flags_any is not None:
            present = set(action.payload.get("pricing_flags") or [])
            if not present & set(cond.payload_flags_any):
                return False
        if cond.buyer_signals_any is not None and not set(ctx.buyer_signals) & set(cond.buyer_signals_any):
            return False
        if cond.kill_switch_engaged is not None and ctx.kill_switch != cond.kill_switch_engaged:
            return False
        return True

    def evaluate(self, action: PendingAction, ctx: PolicyContext) -> Decision:
        """Apply all matching rules, then the autonomy cap; return the strongest effect and the highest risk."""
        matched = [rule for rule in self.rules if self._matches(rule, action, ctx)]
        if matched:
            effect = max((r.effect for r in matched), key=_STRENGTH.__getitem__)
            risk = max((r.risk for r in matched), key=_RISK_ORDER.__getitem__)
            rule_ids, reasons = [r.id for r in matched], [r.description for r in matched]
        else:
            effect, risk = self.default_effect, "medium"
            rule_ids, reasons = ["DEFAULT"], ["No rule matched; the safe default applies."]
        level = self.level_for(action.action_type)
        cap = self._autonomy_cap(level, effect, risk)
        final = max(effect, cap, key=_STRENGTH.__getitem__)
        if _STRENGTH[cap] > _STRENGTH[effect]:
            rule_ids = rule_ids + [f"AUTONOMY-{level}"]
            reasons = reasons + [f"Autonomy level {level} for '{action.action_type}': "
                                 + (self.autonomy.get(action.action_type) or {}).get("why", "human in the loop.")]
        return Decision(effect=final, risk=risk, rule_ids=rule_ids, reasons=reasons, autonomy=level,
                        policy_effect=effect)

    @staticmethod
    def _autonomy_cap(level: Level, effect: Effect, risk: RiskLevel) -> Effect:
        """The weakest effect this autonomy level allows for an action with this policy effect and risk."""
        if level in ("NEVER", "L0"):
            return "block"
        if level == "L1":
            return "require_approval"
        if level == "L2":
            return "allow" if effect == "allow" and risk == "low" else "require_approval"
        return "allow"                                          # L3: the policies decide


@lru_cache
def get_policy_engine() -> PolicyEngine:
    """The shared engine for the running app."""
    return PolicyEngine.load()
