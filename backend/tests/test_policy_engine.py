"""
test_policy_engine.py — Every governance rule has a trigger test and a non-trigger test.

The policy engine is deterministic code, so these tests are exact: the same action and
context must always give the same decision.
"""

import pytest

from app.agents.state import PendingAction
from app.governance.policy_engine import PolicyContext, PolicyEngine

ENGINE = PolicyEngine.load()
CLEAN = PolicyContext()
FLAGGED = PolicyContext(injection_flags=["instruction_override"])


def action(action_type: str) -> PendingAction:
    """Build a minimal pending action of the given type."""
    return PendingAction(action_type=action_type, title=action_type, requested_by="test")


# P-BANK-001 -------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["update_bank_details", "change_payment_instructions", "mark_payment_received"])
def test_bank_rule_triggers_block(kind):
    """Trigger: anything touching bank details or payment status is blocked, high risk."""
    decision = ENGINE.evaluate(action(kind), CLEAN)
    assert decision.effect == "block"
    assert "P-BANK-001" in decision.rule_ids
    assert decision.risk == "high"


def test_bank_rule_does_not_trigger_on_messages():
    """Non-trigger: a normal outbound message is not blocked by the bank rule."""
    decision = ENGINE.evaluate(action("send_message"), CLEAN)
    assert "P-BANK-001" not in decision.rule_ids
    assert decision.effect != "block"


# P-OUT-001 --------------------------------------------------------------------------

def test_outbound_message_requires_approval():
    """Trigger: an outbound message always waits for a human."""
    decision = ENGINE.evaluate(action("send_message"), CLEAN)
    assert decision.effect == "require_approval"
    assert decision.rule_ids == ["P-OUT-001"]
    assert decision.risk == "medium"


def test_outbound_rule_does_not_trigger_on_other_actions():
    """Non-trigger: the outbound rule ignores non-message actions."""
    decision = ENGINE.evaluate(action("recompute_fx"), CLEAN)
    assert "P-OUT-001" not in decision.rule_ids


# P-INJ-001 --------------------------------------------------------------------------

def test_flagged_run_raises_risk_to_high():
    """Trigger: on a flagged run, even a normal message becomes high risk."""
    decision = ENGINE.evaluate(action("send_message"), FLAGGED)
    assert "P-INJ-001" in decision.rule_ids
    assert decision.effect == "require_approval"
    assert decision.risk == "high"


def test_clean_run_does_not_trigger_injection_rule():
    """Non-trigger: no flags, no P-INJ-001."""
    assert "P-INJ-001" not in ENGINE.evaluate(action("send_message"), CLEAN).rule_ids


# Combination and default ---------------------------------------------------------------

def test_strongest_effect_wins():
    """Bank change on a flagged run matches two rules; block beats require_approval."""
    decision = ENGINE.evaluate(action("update_bank_details"), FLAGGED)
    assert decision.effect == "block"
    assert set(decision.rule_ids) == {"P-BANK-001", "P-INJ-001"}


def test_unknown_action_gets_safe_default():
    """No matching rule -> the safe default (a human approves), never 'allow'."""
    decision = ENGINE.evaluate(action("something_new"), CLEAN)
    assert decision.effect == "require_approval"
    assert decision.rule_ids == ["DEFAULT"]
