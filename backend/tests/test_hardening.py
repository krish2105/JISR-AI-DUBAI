"""
test_hardening.py — Phase 20: security headers, shared rate limits, buyer data rights (export and erasure).
"""

import uuid

import pytest
from sqlalchemy import select

from app.auth.tokens import issue_access_token
from app.db.models import Approval, AuditEntry, BuyerMemory, Contact, Invoice, Membership, Organisation, Run, User
from app.db.session import session_scope


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
        db.add(Organisation(id=org, name="Hardening test"))
        await db.flush()
        for role in roles:
            user = User(id=f"usr_{uuid.uuid4().hex[:12]}", email=f"{role}-{uuid.uuid4().hex[:6]}@example.com")
            db.add(user)
            await db.flush()
            db.add(Membership(user_id=user.id, org_id=org, role=role))
            headers[role] = {"Authorization": f"Bearer {issue_access_token(user.id, org, 1)}"}
    return org, headers


async def test_security_headers_everywhere_except_docs_csp(client):
    r = await client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert r.headers["content-security-policy"].startswith("default-src 'none'")
    assert r.headers["referrer-policy"] == "no-referrer" and "strict-transport-security" not in r.headers  # not prod
    docs = await client.get("/docs")
    assert "content-security-policy" not in docs.headers and docs.headers["x-frame-options"] == "DENY"


async def test_rate_limits_are_shared_through_the_database(client, monkeypatch):
    from app.api.ratelimit import hit
    from app.config import get_settings

    assert [await hit("t", "1.2.3.4", 2, 60) for _ in range(3)] == [True, True, False]
    assert await hit("t", "5.6.7.8", 2, 60)  # another address has its own counter
    monkeypatch.setenv("LOGIN_ATTEMPTS_PER_MINUTE", "2")
    get_settings.cache_clear()
    codes = [
        (
            await client.post(
                "/auth/login",
                json={"email": "x@example.com", "password": "y" * 12},
                headers={"x-forwarded-for": "9.9.9.9"},
            )
        ).status_code
        for _ in range(3)
    ]
    assert codes == [401, 401, 429]
    other = await client.post(
        "/auth/login", json={"email": "x@example.com", "password": "y" * 12}, headers={"x-forwarded-for": "8.8.8.8"}
    )
    assert other.status_code == 401


async def _buyer(org: str) -> tuple[str, str]:
    """A WhatsApp buyer with one run, one approval, memory and an invoice."""
    key = uuid.uuid4().hex[:32]
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    async with session_scope() as db:
        db.add(Contact(contact_key=key, org_id=org, channel="whatsapp", address="971501234567", display_name="Ahmed"))
        db.add(BuyerMemory(contact_key=key, org_id=org, runs=1, languages=["ar"]))
        db.add(
            Run(
                id=run_id,
                org_id=org,
                status="needs_approval",
                raw_redacted="نحتاج 300 مصباح [PHONE_1]",
                contact_key=key,
                state={
                    "raw_message_redacted": "x",
                    "drafts": [{"language": "ar", "text": "مرحبا"}],
                    "rfq": {"buyer_name": "Ahmed Trading"},
                    "quote": {"total_aed": 1200},
                },
            )
        )
        await db.flush()
        db.add(
            Approval(
                id=f"apr_{uuid.uuid4().hex[:12]}",
                run_id=run_id,
                org_id=org,
                action_type="send_message",
                title="Reply",
                payload={"text": "مرحبا أحمد"},
                rule_id="P-OUT-001",
            )
        )
        from datetime import UTC, datetime

        db.add(
            Invoice(
                id=f"{org}-INV-1",
                org_id=org,
                number="INV-1",
                buyer_name="Ahmed Trading",
                contact_key=key,
                amount_aed=1200.0,
                issued_on=datetime.now(UTC),
                due_on=datetime.now(UTC),
            )
        )
    return key, run_id


async def test_buyer_export_and_erasure(client):
    org, h = await org_with("owner", "operator", "viewer")
    other, h2 = await org_with("owner")
    key, run_id = await _buyer(org)

    listed = (await client.get("/buyers", headers=h["operator"])).json()
    assert listed[0]["contact"] == "97150•••67" and listed[0]["languages"] == ["ar"]  # masked in lists
    assert (await client.get("/buyers", headers=h["viewer"])).status_code == 403
    export = (await client.get(f"/buyers/{key}/export", headers=h["operator"])).json()
    assert export["contact"]["address"] == "971501234567" and export["enquiries"][0]["quote_total_aed"] == 1200
    assert export["replies"][0]["text"] == "مرحبا أحمد" and export["invoices"][0]["number"] == "INV-1"
    assert (await client.get(f"/buyers/{key}/export", headers=h2["owner"])).status_code == 404  # isolation

    assert (await client.delete(f"/buyers/{key}", headers=h["operator"])).status_code == 403
    r = await client.delete(f"/buyers/{key}", headers=h["owner"])
    assert r.status_code == 200 and r.json()["runs_scrubbed"] == 1
    async with session_scope() as db:
        assert await db.get(Contact, key) is None and await db.get(BuyerMemory, (key, org)) is None
        run = await db.get(Run, run_id)
        assert run.contact_key is None and "erased" in run.raw_redacted and run.state["rfq"]["buyer_name"] is None
        assert all("erased" in d["text"] for d in run.state["drafts"])
        approval = await db.scalar(select(Approval).where(Approval.run_id == run_id))
        assert "erased" in approval.payload["text"]
        invoice = await db.get(Invoice, f"{org}-INV-1")
        assert invoice.amount_aed == 1200.0 and invoice.contact_key is None  # kept for the books
        actions = (await db.scalars(select(AuditEntry.action).where(AuditEntry.org_id == org))).all()
    assert {"data.buyer_exported", "data.buyer_erased"} <= set(actions)
    assert (await client.get(f"/buyers/{key}/export", headers=h["owner"])).status_code == 404
    chain = (await client.get("/audit/verify", headers=h["owner"])).json()
    assert chain["ok"] is True  # erasure never breaks the chain
