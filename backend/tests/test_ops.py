"""
test_ops.py — Phase 14 operations: liveness/readiness, request ids, JSON logs without query strings, per-run token
and cost accounting at published prices, and the owner/admin operations metrics.
"""

import json
import logging
import uuid

import pytest

from app.auth.tokens import issue_access_token
from app.db.models import Membership, Organisation, Run, User
from app.db.session import session_scope
from app.llm.usage import cost_usd, record, tracking_run
from app.runs.service import create_run


@pytest.fixture
async def client(db_ready):
    import httpx

    from app.main import create_app

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def org_with(*roles: str) -> tuple[str, dict[str, dict]]:
    org = f"org_{uuid.uuid4().hex[:12]}"
    headers = {}
    async with session_scope() as db:
        db.add(Organisation(id=org, name="Ops test"))
        await db.flush()
        for role in roles:
            user = User(id=f"usr_{uuid.uuid4().hex[:12]}", email=f"{role}-{uuid.uuid4().hex[:6]}@example.com")
            db.add(user)
            await db.flush()
            db.add(Membership(user_id=user.id, org_id=org, role=role))
            headers[role] = {"Authorization": f"Bearer {issue_access_token(user.id, org, 1)}"}
    return org, headers


def test_prices_are_exact_and_offline_is_free():
    assert cost_usd("claude-opus-5-5", 1_000_000, 1_000_000) == pytest.approx(24.0)
    assert cost_usd("claude-sonnet-5-5", 2_000, 1_000) == pytest.approx(0.014)
    assert cost_usd("claude-haiku-5-5", 10_000, 2_000) == pytest.approx(0.002)
    assert cost_usd("fake-worker", 10_000, 10_000) == 0.0
    assert cost_usd("budget-fallback:claude-opus-5-5", 10_000, 10_000) == 0.0  # offline answers cost nothing
    with tracking_run() as usage:
        record("claude-sonnet-5-5", 1_000, 500)
        record("claude-haiku-5-5", 2_000, 100)
    assert usage["calls"] == 2 and usage["input_tokens"] == 3_000
    assert usage["cost_usd"] == pytest.approx(0.007 + 0.00025)
    record("claude-opus-5-5", 1, 1)  # outside a run: ignored


async def test_runs_record_their_model_usage(db_ready):
    run_id = await create_run(message="We need 100 brass lamps CIF Dubai", org_id="demo", background=False)
    async with session_scope() as db:
        run = await db.get(Run, run_id)
    usage = run.state["usage"]
    assert usage["calls"] >= 1 and usage["input_tokens"] > 0 and usage["cost_usd"] == 0.0  # fake model: free
    assert usage["prices_as_of"] == "2026-10-06" and all(m.startswith("fake") for m in usage["by_model"])


async def test_health_probes_and_request_ids(client):
    assert (await client.get("/health/live")).json() == {"status": "ok"}
    ready = await client.get("/health/ready")
    assert ready.status_code == 200 and ready.json()["database"] is True
    r = await client.get("/health")
    assert len(r.headers["x-request-id"]) == 16
    echoed = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["x-request-id"] == "abc-123"
    bad = await client.get("/health", headers={"X-Request-ID": "<script>"})
    assert bad.headers["x-request-id"] != "<script>"


async def test_json_access_log_never_contains_the_query_string(client, caplog):
    from app.observability import JsonFormatter

    with caplog.at_level(logging.INFO, logger="jisr.http"):
        await client.get("/runs/run_x/events?st=secret-stream-token")
    record_ = next(r for r in caplog.records if r.name == "jisr.http")
    line = json.loads(JsonFormatter().format(record_))
    assert line["path"] == "/runs/run_x/events" and "secret-stream-token" not in json.dumps(line)
    assert {"request_id", "method", "status", "duration_ms"} <= set(line)


async def test_ops_metrics_for_owners_and_admins_only(client):
    org, h = await org_with("owner", "admin", "approver")
    for _ in range(2):
        await create_run(message="We need 100 brass lamps CIF Dubai", org_id=org, background=False)
    m = (await client.get("/ops/metrics", headers=h["owner"])).json()
    assert m["runs"] == 2 and sum(m["by_status"].values()) == 2 and m["llm_profile"] == "fake"
    assert m["agent_seconds"]["p95"] is not None and m["cost"]["per_quote_usd"] == 0.0
    assert m["cost"]["prices_as_of"] == "2026-10-06" and m["approvals"]["pending"] >= 2
    assert (await client.get("/ops/metrics", headers=h["admin"])).status_code == 200
    assert (await client.get("/ops/metrics", headers=h["approver"])).status_code == 403
