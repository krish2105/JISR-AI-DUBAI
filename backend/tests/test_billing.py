"""
test_billing.py — Phase 19: plans, monthly quotas from run records, seats, test-mode plan changes.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.auth.tokens import issue_access_token
from app.db.models import AuditEntry, Membership, Organisation, Run, User
from app.db.session import session_scope


@pytest.fixture
async def client(db_ready):
    import httpx

    from app.main import create_app

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def org_with(*roles: str, plan: str | None = None) -> tuple[str, dict[str, dict]]:
    org = f"org_{uuid.uuid4().hex[:12]}"
    headers = {}
    async with session_scope() as db:
        db.add(Organisation(id=org, name="Billing test", plan=plan))
        await db.flush()
        for role in roles:
            user = User(id=f"usr_{uuid.uuid4().hex[:12]}", email=f"{role}-{uuid.uuid4().hex[:6]}@example.com")
            db.add(user)
            await db.flush()
            db.add(Membership(user_id=user.id, org_id=org, role=role))
            headers[role] = {"Authorization": f"Bearer {issue_access_token(user.id, org, 1)}"}
    return org, headers


async def add_runs(org: str, n: int, when: datetime | None = None) -> None:
    async with session_scope() as db:
        for _ in range(n):
            db.add(
                Run(
                    id=f"run_{uuid.uuid4().hex[:12]}",
                    org_id=org,
                    raw_redacted="x",
                    state={},
                    created_at=when or datetime.now(UTC),
                )
            )


async def test_public_plans_hide_internal_ones(client):
    plans = (await client.get("/billing/plans")).json()
    assert set(plans["plans"]) == {"trial", "starter", "growth"} and plans["test_mode"] is True
    assert plans["plans"]["starter"]["price_inr_month"] == 4999 and "hypothesis" in plans["status"]


async def test_monthly_quote_quota_counts_only_this_month(client):
    org, h = await org_with("owner")
    last_month = datetime.now(UTC).replace(day=1) - timedelta(days=2)
    await add_runs(org, 30, when=last_month)  # previous month: does not count
    await add_runs(org, 24)
    usage = (await client.get("/billing", headers=h["owner"])).json()
    assert usage["plan"] == "trial" and usage["quotes"] == {"used": 24, "limit": 25}
    assert (await client.post("/runs", headers=h["owner"], json={"message": "100 brass lamps"})).status_code == 201
    over = await client.post("/runs", headers=h["owner"], json={"message": "100 brass lamps"})
    assert over.status_code == 402 and "25 enquiries a month" in over.json()["detail"]
    sim = await client.post("/channels/whatsapp/simulate?sync=true", headers=h["owner"], json={"text": "50 shawls"})
    assert sim.status_code == 402


async def test_seats_include_pending_invitations(client):
    org, h = await org_with("owner")
    first = await client.post(
        "/team/invitations", headers=h["owner"], json={"email": "a@example.com", "role": "viewer"}
    )
    assert first.status_code == 201
    second = await client.post(
        "/team/invitations", headers=h["owner"], json={"email": "b@example.com", "role": "viewer"}
    )
    assert second.status_code == 402 and "2 seats" in second.json()["detail"]


async def test_plan_changes_are_owner_only_test_mode_and_audited(client):
    org, h = await org_with("owner", "admin")
    assert (await client.post("/billing/plan", headers=h["admin"], json={"plan": "growth"})).status_code == 403
    assert (await client.post("/billing/plan", headers=h["owner"], json={"plan": "design_partner"})).status_code == 422
    r = await client.post("/billing/plan", headers=h["owner"], json={"plan": "starter"})
    assert r.status_code == 200 and r.json()["quotes"]["limit"] == 150 and r.json()["seats"]["limit"] == 3
    assert (await client.get("/billing", headers=h["admin"])).json()["plan"] == "starter"
    async with session_scope() as db:
        entry = await db.scalar(
            select(AuditEntry).where(AuditEntry.org_id == org, AuditEntry.action == "billing.plan_changed")
        )
    assert entry.details == {"before": "trial", "after": "starter", "mode": "test (no payment)"}


async def test_sandboxes_have_a_fixed_plan(client):
    demo = (await client.post("/auth/demo")).json()
    h = {"Authorization": f"Bearer {demo['token']}"}
    usage = (await client.get("/billing", headers=h)).json()
    assert usage["plan"] == "sandbox" and usage["quotes"]["limit"] == 40
    assert (await client.post("/billing/plan", headers=h, json={"plan": "growth"})).status_code == 403


def test_pricing_page_data_matches_the_plans():
    """frontend/src/data/plans.json is what the static pricing page shows: it must equal GET /billing/plans."""
    import json
    from pathlib import Path

    from app.api.billing import plans

    page = json.loads((Path(__file__).resolve().parents[2] / "frontend/src/data/plans.json").read_text("utf-8"))
    assert page == plans(), "Regenerate frontend/src/data/plans.json from plans.yaml (see docs/business)"
