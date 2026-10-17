"""
test_settings.py — Phase 15: the business profile per organisation, catalogue management, bounded autonomy and
onboarding. A new exporter must get quotes from THEIR catalogue without touching code.
"""

import uuid

import pytest
from sqlalchemy import select

from app.agents.state import PendingAction
from app.auth.tokens import issue_access_token
from app.db.models import AuditEntry, Membership, Organisation, OrgProfile, Run, User
from app.db.session import session_scope
from app.governance.policy_engine import PolicyContext, PolicyEngine
from app.runs.service import create_run

PASSWORD = "correct horse battery"
LAMP = {
    "name": "Brass diya lamp",
    "keywords": ["diya", "lamp", "lamps"],
    "materials": ["brass"],
    "unit_cost_inr": 300,
    "kg": 0.8,
    "cbm": 0.003,
    "hs_hint": "9405.50",
}


@pytest.fixture
async def client(db_ready):
    import httpx

    from app.main import create_app

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def new_exporter(client, name="Moradabad Metal Works") -> tuple[str, str]:
    r = await client.post(
        "/auth/signup", json={"email": f"{uuid.uuid4().hex[:8]}@example.com", "password": PASSWORD, "org_name": name}
    )
    return r.json()["token"], r.json()["me"]["org"]["id"]


async def add_member(org_id: str, role: str) -> str:
    async with session_scope() as db:
        user = User(id=f"usr_{uuid.uuid4().hex[:12]}", email=f"{role}-{uuid.uuid4().hex[:6]}@example.com")
        db.add(user)
        await db.flush()
        db.add(Membership(user_id=user.id, org_id=org_id, role=role))
    return issue_access_token(user.id, org_id, 1)


async def quote_lines(org_id: str, message: str = "We need 200 brass diya lamps CIF Dubai") -> list[dict]:
    run_id = await create_run(message=message, org_id=org_id, background=False)
    async with session_scope() as db:
        run = await db.get(Run, run_id)
    return run.state["quote"]["lines"]


async def test_new_organisation_starts_blank_and_needs_onboarding(client):
    token, org = await new_exporter(client)
    view = (await client.get("/settings/profile", headers=bearer(token))).json()
    assert view["source"] == "organisation" and view["profile"]["seller_name"] == "Moradabad Metal Works"
    assert view["profile"]["catalogue"] == [] and view["onboarding"] == {
        "steps": ["business", "products", "pricing", "logistics", "first_quote"],
        "step": 0,
        "done": False,
    }
    lines = await quote_lines(org)
    assert lines and all(not line["catalogue_match"] for line in lines)  # unknown products are flagged, not guessed


async def test_quotes_use_the_organisations_own_catalogue_and_name(client):
    token, org = await new_exporter(client)
    r = await client.post("/settings/catalogue", headers=bearer(token), json=LAMP)
    assert r.status_code == 201 and r.json()["profile"]["catalogue"][0]["hs_hint"] == "940550"
    lines = await quote_lines(org)
    assert lines[0]["catalogue_match"] and lines[0]["catalogue_item"] == "Brass diya lamp"
    demo_lines = await quote_lines("demo")  # another organisation is unaffected
    assert demo_lines[0]["catalogue_item"] != "Brass diya lamp"
    async with session_scope() as db:
        run = await db.scalar(select(Run).where(Run.org_id == org).order_by(Run.created_at.desc()).limit(1))
    assert "Moradabad Metal Works" in " ".join(d["text"] for d in run.state["drafts"])


async def test_profile_changes_are_validated_and_audited(client):
    token, org = await new_exporter(client)
    h = bearer(token)
    bad = await client.patch("/settings/profile", headers=h, json={"min_margin_pct": 40, "default_margin_pct": 20})
    assert bad.status_code == 422 and "minimum margin" in bad.json()["detail"]
    assert (await client.patch("/settings/profile", headers=h, json={"catalogue": []})).status_code == 422
    assert (await client.patch("/settings/profile", headers=h, json={"quote_validity_days": 0})).status_code == 422
    ok = await client.patch(
        "/settings/profile", headers=h, json={"default_margin_pct": 30, "logistics": {"origin_port": "Nhava Sheva"}}
    )
    assert ok.status_code == 200
    profile = ok.json()["profile"]
    assert profile["default_margin_pct"] == 30 and profile["logistics"]["origin_port"] == "Nhava Sheva"
    assert profile["logistics"]["insurance_pct"] == 0.25  # nested sections merge, not replace
    async with session_scope() as db:
        entry = await db.scalar(
            select(AuditEntry).where(AuditEntry.org_id == org, AuditEntry.action == "settings.profile_updated")
        )
    assert entry.details["sections"] == ["default_margin_pct", "logistics"]
    assert entry.details["before"] != entry.details["after"]


async def test_catalogue_crud_and_csv(client):
    token, org = await new_exporter(client)
    h = bearer(token)
    await client.post("/settings/catalogue", headers=h, json=LAMP)
    assert (await client.post("/settings/catalogue", headers=h, json=LAMP)).status_code == 422  # duplicate name
    assert (
        await client.post("/settings/catalogue", headers=h, json={**LAMP, "name": "Bad", "unit_cost_inr": 0})
    ).status_code == 422
    changed = {**LAMP, "unit_cost_inr": 350}
    assert (await client.put("/settings/catalogue/brass diya lamp", headers=h, json=changed)).status_code == 200
    csv_text = (
        "name,keywords,materials,unit_cost_inr,kg,cbm,hs_hint\n"
        "Brass diya lamp,diya|lamp,brass,360,0.8,0.003,9405\n"
        "Copper bottle,bottle|bottles,copper,520,0.5,0.0018,7418\n"
        "Broken row,thing,,abc,1,1,\n"
    )
    r = await client.post("/settings/catalogue/import", headers=h, json={"csv": csv_text, "mode": "merge"})
    body = r.json()
    assert r.status_code == 200 and body["import"]["added"] == 1 and body["import"]["updated"] == 1
    assert len(body["import"]["errors"]) == 1 and body["import"]["errors"][0].startswith("Row 4")
    names = {p["name"]: p for p in body["profile"]["catalogue"]}
    assert names["Brass diya lamp"]["unit_cost_inr"] == 360 and "Copper bottle" in names
    exported = await client.get("/settings/catalogue/export", headers=h)
    assert exported.headers["content-type"].startswith("text/csv") and "Copper bottle" in exported.text
    replaced = await client.post(
        "/settings/catalogue/import",
        headers=h,
        json={"csv": "name,unit_cost_inr,kg,cbm\nJute tote,140,0.25,0.0015\n", "mode": "replace"},
    )
    assert [p["name"] for p in replaced.json()["profile"]["catalogue"]] == ["Jute tote"]
    assert replaced.json()["profile"]["catalogue"][0]["keywords"] == ["jute tote"]  # name used as keyword
    assert (
        await client.post("/settings/catalogue/import", headers=h, json={"csv": "product,price\nx,1\n"})
    ).status_code == 422
    assert (await client.delete("/settings/catalogue/jute tote", headers=h)).status_code == 200
    assert (await client.delete("/settings/catalogue/jute tote", headers=h)).status_code == 404


async def test_settings_respect_roles(client):
    token, org = await new_exporter(client)
    operator, viewer, admin = [await add_member(org, r) for r in ("operator", "viewer", "admin")]
    assert (await client.get("/settings/profile", headers=bearer(viewer))).status_code == 200
    assert (
        await client.patch("/settings/profile", headers=bearer(operator), json={"default_margin_pct": 50})
    ).status_code == 403
    assert (await client.post("/settings/catalogue", headers=bearer(viewer), json=LAMP)).status_code == 403
    assert (await client.post("/settings/catalogue", headers=bearer(admin), json=LAMP)).status_code == 201
    assert (
        await client.put(
            "/settings/autonomy", headers=bearer(operator), json={"action_type": "send_message", "level": "L0"}
        )
    ).status_code == 403


async def test_autonomy_can_only_become_stricter(client):
    token, org = await new_exporter(client)
    h = bearer(token)
    view = {a["action_type"]: a for a in (await client.get("/settings/autonomy", headers=h)).json()}
    assert view["send_acknowledgement"]["allowed"] == ["NEVER", "L0", "L1", "L2"]
    assert view["update_bank_details"]["locked"] and view["update_bank_details"]["allowed"] == ["NEVER"]
    loose = await client.put("/settings/autonomy", headers=h, json={"action_type": "send_message", "level": "L3"})
    assert loose.status_code == 422 and "add caution" in loose.json()["detail"]
    assert (
        await client.put("/settings/autonomy", headers=h, json={"action_type": "update_bank_details", "level": "L1"})
    ).status_code == 422
    r = await client.put("/settings/autonomy", headers=h, json={"action_type": "send_acknowledgement", "level": "L1"})
    assert {a["action_type"]: a["level"] for a in r.json()}["send_acknowledgement"] == "L1"
    gov = (await client.get("/governance", headers=h)).json()
    ack = next(a for a in gov["autonomy"] if a["action_type"] == "send_acknowledgement")
    assert ack == {**ack, "level": "L1", "default": "L2"}
    # The run on WhatsApp now waits for a human for the acknowledgement too.
    run_id = await create_run(
        message="We need 100 brass lamps CIF Dubai", org_id=org, channel="whatsapp", background=False
    )
    async with session_scope() as db:
        run = await db.get(Run, run_id)
        sent_alone = (
            await db.scalars(
                select(AuditEntry).where(AuditEntry.run_id == run_id, AuditEntry.action == "action.autonomous_sent")
            )
        ).all()
    assert sent_alone == [] and run.status == "needs_approval"
    back = await client.put(
        "/settings/autonomy", headers=h, json={"action_type": "send_acknowledgement", "level": "L2"}
    )
    assert {a["action_type"]: a["level"] for a in back.json()}["send_acknowledgement"] == "L2"
    async with session_scope() as db:
        changes = (
            await db.scalars(
                select(AuditEntry.details).where(
                    AuditEntry.org_id == org, AuditEntry.action == "settings.autonomy_changed"
                )
            )
        ).all()
    assert [(c["before"], c["after"]) for c in changes] == [("L2", "L1"), ("L1", "L2")]


def test_engine_ignores_a_looser_override():
    engine = PolicyEngine.load()
    ack = PendingAction(action_type="send_acknowledgement", title="ack", requested_by="t", payload={"text": "Thanks"})
    assert engine.evaluate(ack, PolicyContext()).effect == "allow"
    stricter = engine.evaluate(ack, PolicyContext(autonomy_overrides={"send_acknowledgement": "L0"}))
    assert stricter.effect == "block" and "AUTONOMY-L0" in stricter.rule_ids
    bank = PendingAction(action_type="update_bank_details", title="b", requested_by="t", payload={})
    tampered = engine.evaluate(bank, PolicyContext(autonomy_overrides={"update_bank_details": "L3"}))
    assert tampered.effect == "block" and tampered.autonomy == "NEVER"
    assert engine.evaluate(ack, PolicyContext(autonomy_overrides={"send_acknowledgement": "nonsense"})).autonomy == "L2"


async def test_onboarding_progress_and_demo_orgs(client):
    token, org = await new_exporter(client)
    h = bearer(token)
    r = await client.post("/settings/onboarding", headers=h, json={"step": 2})
    assert r.json()["onboarding"]["step"] == 2 and not r.json()["onboarding"]["done"]
    r = await client.post("/settings/onboarding", headers=h, json={"step": 1})  # never goes backwards
    assert r.json()["onboarding"]["step"] == 2
    r = await client.post("/settings/onboarding", headers=h, json={"step": 5, "done": True})
    assert r.json()["onboarding"]["done"] is True
    demo = (await client.post("/auth/demo")).json()
    view = (await client.get("/settings/profile", headers=bearer(demo["token"]))).json()
    assert view["source"] == "demo" and view["onboarding"]["done"] and len(view["profile"]["catalogue"]) == 16
    assert (
        await client.post("/settings/onboarding", headers=bearer(demo["token"]), json={"step": 1})
    ).status_code == 409


async def test_sandbox_profile_edits_are_private_and_purged(client):
    from datetime import UTC, datetime, timedelta

    from app.auth.service import purge_expired_sandboxes

    demo = (await client.post("/auth/demo")).json()
    org = demo["me"]["org"]["id"]
    r = await client.patch("/settings/profile", headers=bearer(demo["token"]), json={"seller_name": "Judge's Exports"})
    assert r.json()["source"] == "organisation"
    other = (await client.post("/auth/demo")).json()
    other_view = (await client.get("/settings/profile", headers=bearer(other["token"]))).json()
    assert other_view["profile"]["seller_name"] != "Judge's Exports"
    async with session_scope() as db:
        (await db.get(Organisation, org)).expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await purge_expired_sandboxes()
    async with session_scope() as db:
        assert await db.get(OrgProfile, org) is None
