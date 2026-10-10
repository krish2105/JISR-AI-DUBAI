"""
test_governance_p7.py — Graded autonomy, kill switch, Agent Passports, autonomous actions (Phase 7).
"""

import pytest
from sqlalchemy import select

from app.agents.state import PendingAction
from app.db.models import AuditEntry, Run
from app.db.session import session_scope
from app.governance.passports import ToolNotAllowed, check_tool, load_passports
from app.governance.policy_engine import PolicyContext, PolicyEngine
from app.runs.service import ApprovalError, create_run, decide

ENGINE = PolicyEngine.load()
ACK = PendingAction(action_type="send_acknowledgement", title="ack", requested_by="supervisor",
                    payload={"text": "Thank you"})
ENQUIRY = "We need 100 brass lamps CIF Dubai. purchase@acme-demo.ae"


@pytest.fixture
async def client(db_ready):
    """In-process HTTP client sharing the event loop with direct service calls."""
    import httpx

    from app.main import create_app

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def test_acknowledgement_is_autonomous_on_a_clean_run():
    d = ENGINE.evaluate(ACK, PolicyContext())
    assert d.effect == "allow" and d.autonomy == "L2" and "P-ACK-001" in d.rule_ids


def test_acknowledgement_needs_a_human_when_the_buyer_looks_risky():
    d = ENGINE.evaluate(ACK, PolicyContext(buyer_signals=["bank_change_request"]))
    assert d.effect == "require_approval" and d.risk == "high"


def test_no_automatic_contact_with_a_flagged_sender():
    d = ENGINE.evaluate(ACK, PolicyContext(injection_flags=["instruction_override"]))
    assert d.effect == "block" and "P-INJ-002" in d.rule_ids


def test_kill_switch_blocks_everything():
    for kind in ("send_acknowledgement", "send_message", "anything_new"):
        action = PendingAction(action_type=kind, title=kind, requested_by="test")
        d = ENGINE.evaluate(action, PolicyContext(kill_switch=True))
        assert d.effect == "block" and "P-KILL-001" in d.rule_ids


@pytest.mark.parametrize("level, policy_effect, risk, expected", [
    ("NEVER", "allow", "low", "block"), ("L0", "allow", "low", "block"),
    ("L1", "allow", "low", "require_approval"), ("L2", "allow", "low", "allow"),
    ("L2", "allow", "medium", "require_approval"), ("L3", "allow", "high", "allow"),
    ("L3", "require_approval", "low", "require_approval"), ("L3", "block", "low", "block"),
])
def test_autonomy_can_only_add_caution(level, policy_effect, risk, expected):
    cap = PolicyEngine._autonomy_cap(level, policy_effect, risk)
    strength = {"allow": 0, "require_approval": 1, "block": 2}
    assert max(policy_effect, cap, key=strength.__getitem__) == expected


def test_unknown_action_types_default_to_a_human():
    d = ENGINE.evaluate(PendingAction(action_type="book_freight", title="x", requested_by="t"), PolicyContext())
    assert d.effect == "require_approval" and d.autonomy == "L1"


def test_passports_enforce_tool_allow_lists():
    check_tool("quote", "pricing")
    with pytest.raises(ToolNotAllowed):
        check_tool("outreach", "pricing")
    with pytest.raises(ToolNotAllowed):
        check_tool("unknown_agent", "fx")
    assert set(load_passports()) >= {"guard", "quote", "duty", "docs", "trust", "outreach", "governance"}


async def test_kill_switch_stops_sends(client):
    r = await client.post("/governance/kill-switch", json={"engaged": True, "reason": "test drill"})
    assert r.json()["kill_switch"] is True
    run_id = await create_run(message=ENQUIRY, org_id="demo", channel="whatsapp", background=False)
    async with session_scope() as db:
        run = await db.get(Run, run_id)
        actions = [a.action for a in (await db.scalars(select(AuditEntry).where(AuditEntry.run_id == run_id))).all()]
    assert "action.autonomous_sent" not in actions and "policy.blocked" in actions
    assert run.status == "blocked"                       # nothing held, nothing sent
    await client.post("/governance/kill-switch", json={"engaged": False})


async def test_approval_refused_while_kill_switch_is_on(client):
    run_id = await create_run(message=ENQUIRY, org_id="demo", channel="whatsapp", background=False)
    approvals = (await client.get("/approvals")).json()
    approval = next(a for a in approvals if a["run_id"] == run_id)
    await client.post("/governance/kill-switch", json={"engaged": True, "reason": "drill"})
    with pytest.raises(ApprovalError, match="Kill switch"):
        await decide(approval["id"], org_id="demo", decision="approve")
    assert (await client.post(f"/approvals/{approval['id']}/approve")).status_code == 409
    await client.post("/governance/kill-switch", json={"engaged": False})
    assert (await client.post(f"/approvals/{approval['id']}/approve")).status_code == 200


async def test_governance_and_passport_endpoints(client):
    g = (await client.get("/governance")).json()
    assert {p["id"] for p in g["policies"]} >= {"P-BANK-001", "P-KILL-001", "P-ACK-001", "P-TRUST-001"}
    assert {a["action_type"]: a["level"] for a in g["autonomy"]}["update_bank_details"] == "NEVER"
    await create_run(message=ENQUIRY, org_id="demo", channel="whatsapp", background=False)
    auto = (await client.get("/governance/autonomous")).json()
    assert auto["done_alone"] >= 1
    passports = {p["id"]: p for p in (await client.get("/passports")).json()}
    assert passports["supervisor"]["autonomy"] == {"send_acknowledgement": "L2"}
    assert passports["quote"]["tools"] == ["rfq.extract", "fx", "pricing"]
    assert passports["quote"]["activity_24h"].get("tool_call", 0) >= 3


async def test_impact_ledger_is_computed_from_runs(client):
    await create_run(message=ENQUIRY, org_id="demo", channel="whatsapp", background=False)
    await create_run(message="Hi, please send me your catalogue.", org_id="demo", channel="whatsapp", background=False)
    data = (await client.get("/impact?days=7")).json()
    m = data["measured"]
    assert m["enquiries"] >= 2 and m["quotes_drafted"] >= 1 and m["acknowledged_automatically"] >= 2
    assert m["median_seconds_to_acknowledge"] is not None
    assert {"quote", "clarification"} <= {r["kind"] for r in data["ledger"]}
    assert data["estimated"]["assumptions"]["source"].startswith("founder estimate")      # labelled, not measured
