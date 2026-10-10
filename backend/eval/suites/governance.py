"""
governance.py — Suite: does the governance layer (policies.yaml + autonomy.yaml) decide like the owner expects?

Scenarios: data/gold/governance_scenarios.yaml (20 rows: clean / flagged / risky buyer / kill switch / pricing flags
x acknowledgement, quote, documents, bank changes, unknown actions). Each row is checked against the REAL engine.
Metrics:
    governance_scenario_pass_rate   rows whose effect (and risk, when given) match
    unsafe_allow_rate               rows expected to need a human or be blocked that the engine ALLOWED (must be 0)
"""

import yaml

from app.agents.state import PendingAction
from app.governance.policy_engine import PolicyContext, get_policy_engine
from eval.common import REPO, EvalContext, SuiteResult


async def run(ctx: EvalContext) -> SuiteResult:
    """Evaluate every scenario."""
    rows = yaml.safe_load((REPO / "data" / "gold" / "governance_scenarios.yaml").read_text(encoding="utf-8"))
    engine = get_policy_engine()
    passed = unsafe = 0
    failures = []
    for row in rows:
        action = PendingAction(action_type=row["action"], title=row["id"], requested_by="eval",
                               payload={"pricing_flags": row.get("pricing", [])})
        decision = engine.evaluate(action, PolicyContext(injection_flags=row.get("flags", []),
                                                         buyer_signals=row.get("signals", []),
                                                         kill_switch=row.get("kill", False)))
        ok = decision.effect == row["expect"] and ("risk" not in row or decision.risk == row["risk"])
        passed += ok
        unsafe += decision.effect == "allow" and row["expect"] != "allow"
        if not ok:
            failures.append({"id": row["id"], "expected": row["expect"], "got": decision.effect,
                             "risk": decision.risk, "rules": decision.rule_ids, "why": row["why"]})
    n = len(rows)
    return SuiteResult("governance", n, {"governance_scenario_pass_rate": passed / n, "unsafe_allow_rate": unsafe / n},
                       {}, failures, ["Scenarios written as the owner's expectations; the engine is never consulted "
                                      "to write them."])
