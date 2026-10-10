"""
test_mcp.py — Jisr's MCP server over streamable HTTP: token required, safe tool set, every call audited (Phase 10a).
"""

import json

import pytest
from fastapi.testclient import TestClient

HEADERS = {"Authorization": "Bearer test-mcp-token", "Accept": "application/json, text/event-stream",
           "Content-Type": "application/json"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("MCP_TOKEN", "test-mcp-token")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def rpc(client, method: str, params: dict | None = None, headers: dict | None = None):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return client.post("/mcp/", headers=headers or HEADERS, content=json.dumps(body))


def init(client):
    return rpc(client, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "pytest", "version": "1"}})


def test_token_is_required(client):
    r = rpc(client, "tools/list", headers={**HEADERS, "Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_tool_set_is_safe_and_annotated(client):
    assert init(client).status_code == 200
    tools = {t["name"]: t for t in rpc(client, "tools/list").json()["result"]["tools"]}
    assert set(tools) == {"analyse_enquiry", "ask_cepa", "classify_hs", "check_export_documents",
                          "list_pending_approvals", "governance_status"}
    assert not any(word in name for name in tools for word in ("approve", "send", "bank", "kill"))
    assert tools["ask_cepa"]["annotations"]["readOnlyHint"] is True
    assert tools["analyse_enquiry"]["annotations"]["readOnlyHint"] is False


def test_tool_calls_work_and_are_audited(client):
    init(client)
    docs = {"invoice": {"currency": "USD", "lines": []}, "quote_currency": "AED",
            "export_declaration": {"shipping_bill_no": "SB1"}}
    r = rpc(client, "tools/call", {"name": "check_export_documents", "arguments": {"documents": docs}})
    result = r.json()["result"]
    payload = result.get("structuredContent") or json.loads(result["content"][0]["text"])
    assert payload["ok"] is False and payload["issues"][0]["type"] == "currency_mismatch"
    status = rpc(client, "tools/call", {"name": "governance_status", "arguments": {}}).json()["result"]
    assert "P-KILL-001" in json.dumps(status)
    audit = client.get("/audit?limit=20").json()
    assert {"mcp.check_export_documents", "mcp.governance_status"} <= {a["action"] for a in audit}
    assert all(a["actor"] == "mcp" for a in audit if a["action"].startswith("mcp."))


def test_analyse_enquiry_sends_nothing(client):
    init(client)
    r = rpc(client, "tools/call", {"name": "analyse_enquiry",
                                   "arguments": {"message": "We need 100 brass lamps CIF Jebel Ali."}})
    result = r.json()["result"]
    payload = result.get("structuredContent") or json.loads(result["content"][0]["text"])
    assert payload["status"] == "needs_approval" and payload["waiting_for_owner"]
    actions = {a["action"] for a in client.get("/audit?limit=50").json()}
    assert "action.autonomous_sent" not in actions and "message.sent_simulated" not in actions


def test_not_mounted_without_a_token(monkeypatch):
    monkeypatch.setenv("MCP_TOKEN", "")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    with TestClient(create_app()) as c:
        assert c.post("/mcp/", headers=HEADERS, content="{}").status_code == 404


def test_public_rate_limit_and_budget_fallback(monkeypatch):
    monkeypatch.setenv("PUBLIC_RUNS_PER_HOUR", "2")
    from app.api import ratelimit
    from app.config import get_settings

    get_settings.cache_clear()
    ratelimit._hits.clear()
    from app.main import create_app

    with TestClient(create_app()) as c:
        codes = [c.post("/runs", json={"message": "We need 10 brass lamps CIF Dubai"}).status_code for _ in range(3)]
        assert codes == [201, 201, 429]
    ratelimit._hits.clear()


async def test_budget_exhausted_falls_back_to_the_offline_model(monkeypatch):
    from app.config import get_settings
    from app.llm.router import LLMRequest, LLMRouter, RoleConfig

    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "10")
    get_settings.cache_clear()
    router = LLMRouter()
    router.profiles["fake"]["worker"] = RoleConfig(provider="anthropic", model="claude-sonnet-5-5")
    from datetime import UTC, datetime

    router._budget_day, router._budget_used = datetime.now(UTC).date().isoformat(), 11
    resp = await router.complete(LLMRequest(role="worker", prompt="hello", purpose="budget_test"))
    assert resp.model.startswith("budget-fallback:") and router.budget_status()["fallback_active"]
