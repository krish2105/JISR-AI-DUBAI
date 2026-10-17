"""
test_rbac.py — Phase 13 acceptance: authentication, the role x permission matrix on every route, four-eyes,
organisation isolation, team management, sessions, invitations, demo sandboxes and machine keys.

Every request here carries a real signed token (the APP_ENV=test fallback is never used).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.auth.service import principal_from_token, purge_expired_sandboxes
from app.auth.tokens import issue_access_token
from app.db.models import Approval, AuditEntry, Membership, Organisation, Run, User
from app.db.session import session_scope
from app.governance.rbac import ROLES, get_rbac

PASSWORD = "correct horse battery"


@pytest.fixture
async def client(db_ready):
    import httpx

    from app.main import create_app

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def make_org(roles=ROLES) -> tuple[str, dict[str, str], dict[str, str]]:
    """An organisation with one member per role. Returns (org_id, role -> token, role -> user_id)."""
    org_id = f"org_{uuid.uuid4().hex[:12]}"
    tokens, users = {}, {}
    async with session_scope() as db:
        db.add(Organisation(id=org_id, name="Test exports", plan="growth"))  # 10 seats: one member per role
        await db.flush()
        for role in roles:
            user = User(
                id=f"usr_{uuid.uuid4().hex[:12]}", email=f"{role}-{uuid.uuid4().hex[:6]}@example.com", name=role.title()
            )
            db.add(user)
            await db.flush()
            db.add(Membership(user_id=user.id, org_id=org_id, role=role))
            tokens[role] = issue_access_token(user.id, org_id, 1)
            users[role] = user.id
    return org_id, tokens, users


async def make_approval(
    org_id: str, *, risk: str = "medium", kind: str | None = None, created_by: str | None = None
) -> str:
    """A run with one held send_message action of the given risk."""
    run_id, apr_id = f"run_{uuid.uuid4().hex[:12]}", f"apr_{uuid.uuid4().hex[:12]}"
    payload = {"text": "Dear buyer, our quotation is attached.", "language": "en", "channel": "form"}
    if kind:
        payload["kind"] = kind
    async with session_scope() as db:
        db.add(
            Run(
                id=run_id,
                org_id=org_id,
                status="needs_approval",
                channel="form",
                raw_redacted="test",
                state={"run_id": run_id, "status": "needs_approval"},
                created_by=created_by,
            )
        )
        await db.flush()
        db.add(
            Approval(
                id=apr_id,
                run_id=run_id,
                org_id=org_id,
                action_type="send_message",
                title="Reply",
                payload=payload,
                reason="test",
                evidence=[],
                risk=risk,
                rule_id="P-OUT-001",
            )
        )
    return apr_id


# --- Authentication ---------------------------------------------------------------------------------------------------


async def test_signup_login_me_and_wrong_password(client):
    r = await client.post(
        "/auth/signup",
        json={"email": "Founder@Example.com", "password": PASSWORD, "name": "Krishna", "org_name": "Jaipur Brass"},
    )
    assert r.status_code == 201
    me = r.json()["me"]
    assert (
        me["role"] == "owner" and me["user"]["email"] == "founder@example.com" and "billing.manage" in me["permissions"]
    )
    assert (
        await client.post("/auth/signup", json={"email": "founder@example.com", "password": PASSWORD})
    ).status_code == 409
    assert (await client.post("/auth/signup", json={"email": "x@example.com", "password": "short"})).status_code == 422
    ok = await client.post("/auth/login", json={"email": "founder@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    token = ok.json()["token"]
    assert (await client.get("/auth/me", headers=bearer(token))).json()["org"]["name"] == "Jaipur Brass"
    bad = await client.post("/auth/login", json={"email": "founder@example.com", "password": "wrong password!"})
    assert bad.status_code == 401 and "incorrect" in bad.json()["detail"]
    unknown = await client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert unknown.status_code == 401 and unknown.json()["detail"] == bad.json()["detail"]  # no account probing
    async with session_scope() as db:
        actions = (await db.scalars(select(AuditEntry.action).where(AuditEntry.org_id == me["org"]["id"]))).all()
    assert {"auth.signup", "auth.login", "auth.login_failed"} <= set(actions)


async def test_tokens_are_required_outside_tests_and_tampering_is_rejected(client, monkeypatch):
    from app.config import get_settings

    org, tokens, _ = await make_org(["owner"])
    monkeypatch.setenv("APP_ENV", "dev")
    get_settings.cache_clear()
    assert (await client.get("/runs")).status_code == 401  # no X-Org-Id shortcut in dev
    assert (await client.get("/runs", headers={"X-Org-Id": org})).status_code == 401
    assert (await client.get("/runs", headers=bearer(tokens["owner"]))).status_code == 200
    head, payload, sig = tokens["owner"].split(".")
    tampered = f"{head}.{payload}.{sig[:-2]}{'AA' if sig[-2:] != 'AA' else 'BB'}"
    assert (await client.get("/runs", headers=bearer(tampered))).status_code == 401
    expired = issue_access_token("usr_x", org, 1, hours=-1)
    assert (await client.get("/runs", headers=bearer(expired))).status_code == 401


def test_production_refuses_to_run_without_a_secret(monkeypatch):
    from app.auth.tokens import AuthConfigError, signing_secret
    from app.config import get_settings

    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("AUTH_SECRET", "")
    get_settings.cache_clear()
    with pytest.raises(AuthConfigError):
        signing_secret()
    monkeypatch.setenv("AUTH_SECRET", "too-short")
    get_settings.cache_clear()
    with pytest.raises(AuthConfigError):
        signing_secret()


async def test_login_attempts_are_rate_limited(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("LOGIN_ATTEMPTS_PER_MINUTE", "3")
    get_settings.cache_clear()
    codes = [
        (await client.post("/auth/login", json={"email": "a@example.com", "password": "x" * 12})).status_code
        for _ in range(4)
    ]
    assert codes == [401, 401, 401, 429]


async def test_sign_out_everywhere_and_removal_end_sessions(client):
    org, tokens, users = await make_org(["owner", "operator"])
    assert (await client.post("/auth/logout-all", headers=bearer(tokens["operator"]))).status_code == 200
    assert (await client.get("/runs", headers=bearer(tokens["operator"]))).status_code == 401
    _, tokens2, users2 = await make_org(["owner", "viewer"])
    r = await client.delete(f"/team/members/{users2['viewer']}", headers=bearer(tokens2["owner"]))
    assert r.status_code == 200
    assert (await client.get("/runs", headers=bearer(tokens2["viewer"]))).status_code == 401


# --- The permission matrix on every route --------------------------------------------------------------------------

ROUTES = [
    ("POST", "/runs", {"message": "We need 100 brass lamps CIF Dubai"}, "runs.create"),
    ("POST", "/channels/whatsapp/simulate?sync=true", {"text": "Need 50 cushion covers"}, "runs.create"),
    ("GET", "/runs", None, "runs.read"),
    ("GET", "/approvals", None, "runs.read"),
    ("GET", "/impact", None, "runs.read"),
    ("GET", "/collections/invoices", None, "runs.read"),
    ("GET", "/governance", None, "governance.read"),
    ("GET", "/governance/autonomous", None, "governance.read"),
    ("GET", "/passports", None, "governance.read"),
    ("POST", "/governance/kill-switch", {"engaged": True, "reason": "test"}, "governance.kill_switch.engage"),
    ("POST", "/governance/kill-switch", {"engaged": False}, "governance.kill_switch.release"),
    ("GET", "/audit", None, "audit.read"),
    ("GET", "/audit/verify", None, "audit.read"),
    ("GET", "/audit/export", None, "audit.export"),
    ("POST", "/collections/run", None, "collections.run"),
    ("GET", "/team/members", None, "team.read"),
    ("POST", "/team/invitations", {"email": "new-{role}@example.com", "role": "viewer"}, "team.manage"),
    ("GET", "/team/api-keys", None, "api_keys.manage"),
    ("POST", "/team/api-keys", {"name": "Claude Desktop"}, "api_keys.manage"),
]


@pytest.mark.parametrize("role", ROLES)
async def test_permission_matrix_on_every_route(client, role):
    org, tokens, _ = await make_org()
    rbac = get_rbac()
    for method, path, body, permission in ROUTES:
        if body:
            body = {k: v.replace("{role}", role) if isinstance(v, str) else v for k, v in body.items()}
        r = await client.request(method, path, json=body, headers=bearer(tokens[role]))
        allowed = rbac.can(role, permission)
        assert (r.status_code < 300) == allowed, f"{role} {method} {path}: {r.status_code} {r.text[:120]}"
        if not allowed:
            assert r.status_code == 403


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("risk", ["low", "medium", "high"])
async def test_who_may_decide_which_risk(client, role, risk):
    org, tokens, _ = await make_org()
    apr = await make_approval(org, risk=risk)
    r = await client.post(f"/approvals/{apr}/approve", headers=bearer(tokens[role]), json={})
    expected = role == "owner" if risk == "high" else role in ("owner", "admin", "approver")
    assert (r.status_code == 200) == expected, f"{role}/{risk}: {r.status_code} {r.text[:120]}"
    if not expected:
        assert r.status_code == 403
    rej = await make_approval(org, risk=risk)
    r = await client.post(f"/approvals/{rej}/reject", headers=bearer(tokens[role]), json={})
    assert (r.status_code == 200) == expected  # rejecting needs the same right as approving


async def test_accountant_may_decide_collection_reminders_only(client):
    org, tokens, _ = await make_org()
    reminder = await make_approval(org, risk="medium", kind="collection_reminder")
    quote = await make_approval(org, risk="medium")
    acc = bearer(tokens["accountant"])
    assert (await client.post(f"/approvals/{reminder}/approve", headers=acc, json={})).status_code == 200
    assert (await client.post(f"/approvals/{quote}/approve", headers=acc, json={})).status_code == 403
    high = await make_approval(org, risk="high", kind="collection_reminder")
    assert (await client.post(f"/approvals/{high}/approve", headers=acc, json={})).status_code == 403


async def test_editing_a_draft_needs_drafts_edit(client):
    org, tokens, _ = await make_org()
    apr = await make_approval(org, risk="medium", kind="collection_reminder")
    r = await client.post(
        f"/approvals/{apr}/approve", headers=bearer(tokens["accountant"]), json={"edited_text": "Changed text"}
    )
    assert r.status_code == 403 and "edit" in r.json()["detail"]
    r = await client.post(
        f"/approvals/{apr}/approve", headers=bearer(tokens["approver"]), json={"edited_text": "Changed text"}
    )
    assert r.status_code == 200 and r.json()["payload"]["edited_by_human"] is True


async def test_listing_shows_who_may_decide(client):
    org, tokens, _ = await make_org()
    await make_approval(org, risk="high")
    owner = (await client.get("/approvals", headers=bearer(tokens["owner"]))).json()[0]
    approver = (await client.get("/approvals", headers=bearer(tokens["approver"]))).json()[0]
    assert owner["approver_role"] == "owner" and owner["can_decide"] is True and approver["can_decide"] is False


async def test_four_eyes_on_high_risk_actions(client):
    org, tokens, users = await make_org(["owner", "approver"])
    second_owner = await make_org(["owner"])
    apr = await make_approval(org, risk="high", created_by=users["owner"])
    r = await client.post(f"/approvals/{apr}/approve", headers=bearer(tokens["owner"]), json={})
    assert r.status_code == 403 and "Four-eyes" in r.json()["detail"]
    r = await client.post(
        f"/approvals/{apr}/approve", headers=bearer(tokens["owner"]), json={"override_reason": "too short"}
    )
    assert r.status_code == 403
    r = await client.post(
        f"/approvals/{apr}/approve",
        headers=bearer(tokens["owner"]),
        json={"override_reason": "Solo exporter, I checked the buyer by phone."},
    )
    assert r.status_code == 200
    async with session_scope() as db:
        entry = await db.scalar(
            select(AuditEntry).where(AuditEntry.org_id == org, AuditEntry.action == "approval.approved")
        )
    assert entry.actor == f"user:{users['owner']}" and entry.details["role"] == "owner"
    assert entry.details["four_eyes_override"].startswith("Solo exporter")
    # someone else's high-risk action: no override needed; medium risk: four-eyes does not apply
    other = await make_approval(org, risk="high", created_by=users["approver"])
    assert (
        await client.post(f"/approvals/{other}/approve", headers=bearer(tokens["owner"]), json={})
    ).status_code == 200
    assert second_owner  # a different organisation's owner is unrelated (isolation test below)


async def test_viewer_and_auditor_cannot_act(client):
    org, tokens, _ = await make_org()
    apr = await make_approval(org, risk="low")
    for role in ("viewer", "auditor"):
        h = bearer(tokens[role])
        assert (await client.post(f"/approvals/{apr}/approve", headers=h, json={})).status_code == 403
        assert (await client.post("/governance/kill-switch", headers=h, json={"engaged": True})).status_code == 403
        assert (await client.post("/runs", headers=h, json={"message": "100 lamps"})).status_code == 403
        assert (
            await client.post("/team/invitations", headers=h, json={"email": "z@example.com", "role": "viewer"})
        ).status_code == 403


async def test_anyone_who_works_can_stop_only_owner_or_admin_can_restart(client):
    org, tokens, _ = await make_org()
    assert (
        await client.post(
            "/governance/kill-switch",
            headers=bearer(tokens["operator"]),
            json={"engaged": True, "reason": "suspicious buyer"},
        )
    ).status_code == 200
    r = await client.post("/governance/kill-switch", headers=bearer(tokens["approver"]), json={"engaged": False})
    assert r.status_code == 403 and "Owner or Admin" in r.json()["detail"]
    r = await client.post("/governance/kill-switch", headers=bearer(tokens["admin"]), json={"engaged": False})
    assert r.status_code == 200 and r.json()["kill_switch"] is False
    async with session_scope() as db:
        actors = (
            await db.scalars(
                select(AuditEntry.actor).where(AuditEntry.org_id == org, AuditEntry.action.like("kill_switch.%"))
            )
        ).all()
    assert all(a.startswith("user:usr_") for a in actors) and len(actors) == 2


async def test_organisations_are_isolated(client):
    org_a, tokens_a, _ = await make_org(["owner"])
    org_b, tokens_b, _ = await make_org(["owner"])
    apr_b = await make_approval(org_b, risk="low")
    async with session_scope() as db:
        run_b = await db.scalar(select(Approval.run_id).where(Approval.id == apr_b))
    a = bearer(tokens_a["owner"])
    assert (await client.get(f"/runs/{run_b}", headers=a)).status_code == 404
    assert (await client.post(f"/runs/{run_b}/stream-token", headers=a)).status_code == 404
    assert (await client.post(f"/approvals/{apr_b}/approve", headers=a, json={})).status_code == 404
    assert (await client.get("/approvals", headers=a)).json() == []
    assert (await client.post("/auth/switch", headers=a, json={"org_id": org_b})).status_code == 404


async def test_role_changes_apply_immediately(client):
    org, tokens, users = await make_org(["owner", "operator"])
    apr = await make_approval(org, risk="medium")
    op = bearer(tokens["operator"])
    assert (await client.post(f"/approvals/{apr}/approve", headers=op, json={})).status_code == 403
    r = await client.patch(
        f"/team/members/{users['operator']}", headers=bearer(tokens["owner"]), json={"role": "approver"}
    )
    assert r.status_code == 200
    assert (await client.post(f"/approvals/{apr}/approve", headers=op, json={})).status_code == 200


async def test_admins_cannot_touch_owners_and_the_last_owner_stays(client):
    org, tokens, users = await make_org(["owner", "admin", "viewer"])
    admin, owner = bearer(tokens["admin"]), bearer(tokens["owner"])
    assert (
        await client.patch(f"/team/members/{users['viewer']}", headers=admin, json={"role": "owner"})
    ).status_code == 403
    assert (
        await client.patch(f"/team/members/{users['owner']}", headers=admin, json={"role": "viewer"})
    ).status_code == 403
    assert (await client.delete(f"/team/members/{users['owner']}", headers=admin)).status_code == 403
    assert (
        await client.post("/team/invitations", headers=admin, json={"email": "o@example.com", "role": "owner"})
    ).status_code == 403
    assert (
        await client.patch(f"/team/members/{users['owner']}", headers=owner, json={"role": "admin"})
    ).status_code == 409
    assert (
        await client.patch(f"/team/members/{users['viewer']}", headers=admin, json={"role": "accountant"})
    ).status_code == 200
    assert (
        await client.patch(f"/team/members/{users['viewer']}", headers=owner, json={"role": "boss"})
    ).status_code == 422


async def test_invitation_flow(client):
    org, tokens, _ = await make_org(["owner"])
    r = await client.post(
        "/team/invitations", headers=bearer(tokens["owner"]), json={"email": "sales@example.com", "role": "operator"}
    )
    assert r.status_code == 201
    invite = r.json()
    info = await client.get(f"/auth/invitations/{invite['token']}")
    assert info.json() == {
        "org_name": "Test exports",
        "email": "sales@example.com",
        "role": "operator",
        "has_account": False,
    }
    members = (await client.get("/team/members", headers=bearer(tokens["owner"]))).json()
    assert any(m.get("pending") and m["email"] == "sales@example.com" for m in members)
    joined = await client.post(
        "/auth/invitations/accept", json={"token": invite["token"], "password": PASSWORD, "name": "Sales"}
    )
    assert joined.status_code == 200 and joined.json()["me"]["role"] == "operator"
    assert (
        await client.post("/auth/invitations/accept", json={"token": invite["token"], "password": PASSWORD})
    ).status_code == 404  # once only
    second = (
        await client.post(
            "/team/invitations", headers=bearer(tokens["owner"]), json={"email": "late@example.com", "role": "viewer"}
        )
    ).json()
    assert (
        await client.delete(f"/team/invitations/{second['invitation_id']}", headers=bearer(tokens["owner"]))
    ).status_code == 200
    assert (await client.get(f"/auth/invitations/{second['token']}")).status_code == 404
    async with session_scope() as db:
        stored = (await db.scalars(select(AuditEntry.details).where(AuditEntry.action == "team.invited"))).all()
    assert all("sales@example.com" not in str(d) for d in stored)  # emails are hashed in the audit


async def test_users_can_belong_to_two_organisations(client):
    r = await client.post("/auth/signup", json={"email": "two@example.com", "password": PASSWORD, "org_name": "First"})
    first = r.json()
    org2, tokens2, _ = await make_org(["owner"])
    inv = (
        await client.post(
            "/team/invitations", headers=bearer(tokens2["owner"]), json={"email": "two@example.com", "role": "approver"}
        )
    ).json()
    info = (await client.get(f"/auth/invitations/{inv['token']}")).json()
    assert info["has_account"] is True
    wrong = await client.post("/auth/invitations/accept", json={"token": inv["token"], "password": "not my password"})
    assert wrong.status_code == 401
    ok = await client.post("/auth/invitations/accept", json={"token": inv["token"], "password": PASSWORD})
    assert ok.json()["me"]["org"]["id"] == org2 and len(ok.json()["me"]["orgs"]) == 2
    back = await client.post(
        "/auth/switch", headers=bearer(ok.json()["token"]), json={"org_id": first["me"]["org"]["id"]}
    )
    assert back.status_code == 200 and back.json()["me"]["role"] == "owner"


# --- Demo sandboxes --------------------------------------------------------------------------------------------------


async def test_demo_sandbox_is_private_seeded_and_cannot_invite(client):
    r = await client.post("/auth/demo")
    assert r.status_code == 201
    token, me = r.json()["token"], r.json()["me"]
    assert me["org"]["is_sandbox"] and me["org"]["id"].startswith("sbx_") and me["role"] == "owner"
    h = bearer(token)
    invoices = (await client.get("/collections/invoices", headers=h)).json()
    assert {i["number"] for i in invoices} == {"INV-2026-031", "INV-2026-034", "INV-2026-040"}
    created = (await client.post("/collections/run", headers=h)).json()
    assert created["drafted"] == 2 and all(r["invoice_id"].startswith("INV-") for r in created["reminders"])
    assert (
        await client.post("/team/invitations", headers=h, json={"email": "a@example.com", "role": "viewer"})
    ).status_code == 403
    assert (await client.post("/team/api-keys", headers=h, json={"name": "x"})).status_code == 403
    other = (await client.post("/auth/demo")).json()
    assert other["me"]["org"]["id"] != me["org"]["id"]
    assert (await client.get("/approvals", headers=bearer(other["token"]))).json() == []  # sandboxes are separate


async def test_expired_sandboxes_are_deleted_with_their_data(client):
    r = (await client.post("/auth/demo")).json()
    org_id = r["me"]["org"]["id"]
    await client.post("/collections/run", headers=bearer(r["token"]))
    async with session_scope() as db:
        org = await db.get(Organisation, org_id)
        org.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    assert (await client.get("/runs", headers=bearer(r["token"]))).status_code == 401
    assert await purge_expired_sandboxes() == 1
    async with session_scope() as db:
        assert await db.get(Organisation, org_id) is None
        assert (await db.scalars(select(Run).where(Run.org_id == org_id))).all() == []
        assert (await db.scalars(select(AuditEntry).where(AuditEntry.org_id == org_id))).all() == []


async def test_sandboxes_never_reach_real_whatsapp(db_ready):
    from app.channels import outbox
    from app.db.models import Contact

    class Boom:
        async def send_text(self, *a, **k):  # pragma: no cover - must never be called
            raise AssertionError("real WhatsApp used from a sandbox")

    outbox.set_whatsapp_client(Boom())
    try:
        async with session_scope() as db:
            db.add(
                Contact(
                    contact_key="c1",
                    org_id="sbx_test",
                    channel="whatsapp",
                    address="971500000001",
                    last_inbound_at=datetime.now(UTC),
                )
            )
            db.add(Run(id="run_sbx", org_id="sbx_test", raw_redacted="x", contact_key="c1", state={}))
            await db.flush()
            sent = await outbox.send(
                db,
                org_id="sbx_test",
                run_id="run_sbx",
                action_type="send_message",
                payload={"text": "hi", "channel": "whatsapp"},
                actor="user:usr_x",
            )
        assert sent["channel"].endswith("_simulator")
    finally:
        outbox.set_whatsapp_client(None)


# --- Live events and machine keys ------------------------------------------------------------------------------------


async def test_stream_tokens_open_one_run_only(client, monkeypatch):
    from app.config import get_settings
    from app.runs.service import create_run, decide

    org, tokens, _ = await make_org(["viewer", "owner"])
    run_id = await create_run(message="We need 100 brass lamps CIF Dubai", org_id=org, background=False)
    async with session_scope() as db:  # finish the run so its stream ends with `done`
        pending = (await db.scalars(select(Approval.id).where(Approval.run_id == run_id))).all()
    for apr in pending:
        await decide(apr, org_id=org, decision="reject")
    other = await create_run(message="50 cushion covers", org_id=org, background=False)
    st = (await client.post(f"/runs/{run_id}/stream-token", headers=bearer(tokens["viewer"]))).json()["token"]
    monkeypatch.setenv("APP_ENV", "dev")
    get_settings.cache_clear()
    assert (await client.get(f"/runs/{run_id}/events")).status_code == 401
    assert (await client.get(f"/runs/{other}/events?st={st}")).status_code == 401
    assert (await client.get(f"/runs/{run_id}/events?st={tokens['viewer']}")).status_code == 401  # access != stream
    r = await client.get(f"/runs/{run_id}/events?st={st}")
    assert r.status_code == 200 and '"kind":"done"' in r.text.replace(" ", "")


async def test_api_keys_are_shown_once_scoped_and_revocable(client, monkeypatch):
    from app.auth.service import org_for_api_key

    org, tokens, _ = await make_org(["owner"])
    r = await client.post("/team/api-keys", headers=bearer(tokens["owner"]), json={"name": "Claude Desktop"})
    key = r.json()
    assert key["key"].startswith("jisr_mcp_") and await org_for_api_key(key["key"]) == org
    listed = (await client.get("/team/api-keys", headers=bearer(tokens["owner"]))).json()
    assert "key" not in listed[0] and listed[0]["prefix"] == key["prefix"]
    await client.delete(f"/team/api-keys/{key['id']}", headers=bearer(tokens["owner"]))
    assert await org_for_api_key(key["key"]) is None
    assert await org_for_api_key("jisr_mcp_not-a-real-key") is None


async def test_principal_reflects_current_role(db_ready):
    org, tokens, users = await make_org(["auditor"])
    p = await principal_from_token(tokens["auditor"])
    assert p.role == "auditor" and p.can("audit.export") and not p.can("runs.create")
