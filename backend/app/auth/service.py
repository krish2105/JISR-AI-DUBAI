"""
service.py — Identity and access operations: sign-up, login, sandboxes, team, invitations, API keys.

Every operation that changes who may do what is written to the organisation's hash-chained audit log with
`actor = user:<id>`. Secrets (passwords, invitation tokens, API keys) are stored only as hashes.
"""

import hashlib
import logging
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update

from app.auth.passwords import DUMMY_HASH, check_strength, hash_password, verify_password
from app.auth.tokens import InvalidToken, decode, issue_access_token
from app.config import get_settings
from app.db.models import (
    ApiKey,
    Approval,
    AuditEntry,
    BuyerMemory,
    Contact,
    InboundLog,
    Invitation,
    Invoice,
    Membership,
    Organisation,
    OrgProfile,
    OrgSettings,
    Run,
    RunEventRow,
    User,
)
from app.db.session import session_scope
from app.governance.audit import append_audit
from app.governance.rbac import ROLES, get_rbac
from app.profile import blank_profile

log = logging.getLogger("jisr.auth")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
INVITE_DAYS = 7
SANDBOX_PREFIX = "sbx_"


class AuthError(Exception):
    """Wrong credentials or an unusable token (HTTP 401)."""


class AccessError(Exception):
    """Signed in, but not allowed (HTTP 403)."""


class NotFound(Exception):
    """Unknown or not visible to the caller (HTTP 404)."""


class Conflict(Exception):
    """The request clashes with existing data (HTTP 409)."""


class BadRequest(Exception):
    """Invalid input (HTTP 422)."""


@dataclass(frozen=True)
class Principal:
    """Who is calling: a user acting in one organisation with one role."""

    user_id: str
    org_id: str
    role: str
    email: str = ""
    name: str = ""
    is_sandbox: bool = False
    permissions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def actor(self) -> str:
        """The audit actor string."""
        return f"user:{self.user_id}"

    def can(self, permission: str) -> bool:
        return get_rbac().can(self.role, permission)


def is_sandbox_org(org_id: str) -> bool:
    """Sandbox organisations belong to anonymous demo visitors and never reach real channels."""
    return org_id.startswith(SANDBOX_PREFIX)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalise_email(email: str) -> str:
    """Lower-case and validate an email address."""
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise BadRequest("Enter a valid email address.")
    return email


def _principal(user: User, membership: Membership, org: Organisation | None) -> Principal:
    rbac = get_rbac()
    return Principal(user_id=user.id, org_id=membership.org_id, role=membership.role, email=user.email,
                     name=user.name, is_sandbox=bool(org and org.is_sandbox),
                     permissions=tuple(rbac.permissions_of(membership.role)))


async def _active_membership(db, user_id: str, org_id: str) -> Membership | None:
    return await db.scalar(select(Membership).where(Membership.user_id == user_id, Membership.org_id == org_id,
                                                    Membership.status == "active"))


async def principal_from_token(token: str) -> Principal:
    """Verify an access token and load the caller's CURRENT role (role changes apply at once)."""
    try:
        claims = decode(token, "access")
    except InvalidToken as exc:
        raise AuthError("Your session has expired or is invalid. Please sign in again.") from exc
    async with session_scope() as db:
        user = await db.get(User, claims["sub"])
        if user is None or claims.get("sv") != user.session_version:
            raise AuthError("Your session has ended. Please sign in again.")
        membership = await _active_membership(db, user.id, claims["org"])
        if membership is None:
            raise AuthError("You no longer have access to this organisation.")
        org = await db.get(Organisation, membership.org_id)
        if org is not None and org.expires_at is not None and org.expires_at < datetime.now(UTC):
            raise AuthError("This demo sandbox has expired. Start a new one.")
        return _principal(user, membership, org)


async def principal_for_stream(token: str, run_id: str) -> Principal:
    """Verify a stream token for one run."""
    try:
        claims = decode(token, "stream")
    except InvalidToken as exc:
        raise AuthError("Stream token expired or invalid.") from exc
    if claims.get("run") != run_id:
        raise AuthError("Stream token is for another run.")
    async with session_scope() as db:
        user = await db.get(User, claims["sub"])
        membership = await _active_membership(db, claims["sub"], claims["org"]) if user else None
        if user is None or membership is None:
            raise AuthError("No access.")
        return _principal(user, membership, await db.get(Organisation, membership.org_id))


def _token_for(user: User, org_id: str, hours: float | None = None) -> str:
    return issue_access_token(user.id, org_id, user.session_version, hours)


async def signup(email: str, password: str, name: str, org_name: str) -> tuple[str, Principal]:
    """Create a user, their organisation and an Owner membership. Returns (token, principal)."""
    if not get_settings().allow_signup:
        raise AccessError("Sign-up is closed on this server. Ask an owner for an invitation.")
    email = normalise_email(email)
    check_strength(password)
    org_name = (org_name or "").strip() or "My export business"
    async with session_scope() as db:
        if await db.scalar(select(User.id).where(User.email == email)):
            raise Conflict("An account with this email already exists. Sign in instead.")
        user = User(id=_new_id("usr"), email=email, name=(name or "").strip()[:120],
                    password_hash=hash_password(password))
        org = Organisation(id=_new_id("org"), name=org_name[:160])
        db.add_all([user, org])
        await db.flush()
        membership = Membership(user_id=user.id, org_id=org.id, role="owner")
        db.add(membership)
        db.add(OrgProfile(org_id=org.id, data=blank_profile(org.name).model_dump(mode="json")))   # onboarding next
        await db.flush()
        await append_audit(db, org_id=org.id, actor=f"user:{user.id}", action="auth.signup",
                           details={"role": "owner"})
        return _token_for(user, org.id), _principal(user, membership, org)


async def login(email: str, password: str, org_id: str | None = None) -> tuple[str, Principal]:
    """Check credentials; sign into the requested (or first) organisation. Failures are audited."""
    try:
        email = normalise_email(email)
    except BadRequest:
        verify_password(password, DUMMY_HASH)
        raise AuthError("Email or password is incorrect.") from None
    async with session_scope() as db:
        user = await db.scalar(select(User).where(User.email == email))
        memberships = [] if user is None else (await db.scalars(
            select(Membership).where(Membership.user_id == user.id, Membership.status == "active")
            .order_by(Membership.id))).all()
        ok = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if not ok or user is None:
        if memberships:                                   # recorded in its own transaction (the error rolls back)
            async with session_scope() as db:
                await append_audit(db, org_id=memberships[0].org_id, actor=f"user:{user.id}",
                                   action="auth.login_failed", details={})
        log.info("login failed for %s", "known user" if user else "unknown email")
        raise AuthError("Email or password is incorrect.")
    async with session_scope() as db:
        if not memberships:
            raise AccessError("This account is not a member of any organisation.")
        membership = next((m for m in memberships if m.org_id == org_id), memberships[0])
        await append_audit(db, org_id=membership.org_id, actor=f"user:{user.id}", action="auth.login",
                           details={"role": membership.role})
        org = await db.get(Organisation, membership.org_id)
        return _token_for(user, membership.org_id), _principal(user, membership, org)


async def switch_org(principal: Principal, org_id: str) -> tuple[str, Principal]:
    """Issue a token for another organisation the user belongs to."""
    async with session_scope() as db:
        user = await db.get(User, principal.user_id)
        membership = await _active_membership(db, principal.user_id, org_id)
        if user is None or membership is None:
            raise NotFound("Organisation not found.")
        return _token_for(user, org_id), _principal(user, membership, await db.get(Organisation, org_id))


async def sign_out_everywhere(principal: Principal) -> None:
    """Invalidate every token of this user (bumps the session version)."""
    async with session_scope() as db:
        user = await db.get(User, principal.user_id)
        user.session_version += 1
        await append_audit(db, org_id=principal.org_id, actor=principal.actor, action="auth.sign_out_everywhere",
                           details={})


async def me(principal: Principal) -> dict:
    """The signed-in user, their current organisation and role, and every organisation they can switch to."""
    async with session_scope() as db:
        rows = (await db.execute(select(Membership, Organisation)
                                 .join(Organisation, Organisation.id == Membership.org_id)
                                 .where(Membership.user_id == principal.user_id, Membership.status == "active")
                                 .order_by(Membership.id))).all()
        current = await db.get(Organisation, principal.org_id)
        profile = await db.get(OrgProfile, principal.org_id)
    rbac = get_rbac()
    return {
        "user": {"id": principal.user_id, "email": principal.email, "name": principal.name},
        "org": {"id": principal.org_id, "name": current.name if current else principal.org_id,
                "is_sandbox": principal.is_sandbox,
                "expires_at": current.expires_at.isoformat() if current and current.expires_at else None},
        "role": principal.role,
        "role_label": rbac.roles[principal.role]["label"], "role_label_ar": rbac.roles[principal.role]["label_ar"],
        "permissions": rbac.permissions_of(principal.role),
        "orgs": [{"id": o.id, "name": o.name, "role": m.role, "is_sandbox": o.is_sandbox} for m, o in rows],
        "onboarding": {"done": profile.onboarding_done if profile else True,
                       "step": profile.onboarding_step if profile else 5},
    }


# --- Demo sandboxes -------------------------------------------------------------------------------------------------

async def purge_expired_sandboxes() -> int:
    """Delete sandbox organisations past their expiry, with all their data. Returns how many were removed."""
    now = datetime.now(UTC)
    async with session_scope() as db:
        expired = (await db.scalars(select(Organisation.id).where(Organisation.is_sandbox.is_(True),
                                                                   Organisation.expires_at < now))).all()
        for org_id in expired:
            run_ids = select(Run.id).where(Run.org_id == org_id)
            await db.execute(delete(RunEventRow).where(RunEventRow.run_id.in_(run_ids)))
            await db.execute(delete(Approval).where(Approval.org_id == org_id))
            await db.execute(delete(Run).where(Run.org_id == org_id))
            for model in (AuditEntry, OrgSettings, OrgProfile, Contact, InboundLog, Invoice, BuyerMemory,
                          Invitation, ApiKey):
                await db.execute(delete(model).where(model.org_id == org_id))
            user_ids = (await db.scalars(select(Membership.user_id).where(Membership.org_id == org_id))).all()
            await db.execute(delete(Membership).where(Membership.org_id == org_id))
            if user_ids:
                await db.execute(delete(User).where(User.id.in_(user_ids), User.is_demo.is_(True)))
            await db.execute(delete(Organisation).where(Organisation.id == org_id))
    return len(expired)


async def create_sandbox() -> tuple[str, Principal]:
    """A private, throw-away organisation for one demo visitor, pre-filled with synthetic data.

    The visitor is the Owner of their sandbox (so they can try approvals and the kill switch) and has no access to
    anything else. Sandboxes expire after SANDBOX_HOURS and can never reach real WhatsApp.
    """
    settings = get_settings()
    if not settings.demo_mode:
        raise AccessError("The demo is not enabled on this server.")
    await purge_expired_sandboxes()
    hours = settings.sandbox_hours
    token_hex = uuid.uuid4().hex[:12]
    async with session_scope() as db:
        user = User(id=_new_id("usr"), email=f"visitor-{token_hex}@sandbox.invalid", name="Demo visitor",
                    password_hash=None, is_demo=True)
        org = Organisation(id=f"{SANDBOX_PREFIX}{token_hex}", name="Demo sandbox", is_sandbox=True,
                           expires_at=datetime.now(UTC) + timedelta(hours=hours))
        db.add_all([user, org])
        await db.flush()
        membership = Membership(user_id=user.id, org_id=org.id, role="owner")
        db.add(membership)
        await db.flush()
        await append_audit(db, org_id=org.id, actor=f"user:{user.id}", action="auth.sandbox_created",
                           details={"expires_in_hours": hours})
        principal = _principal(user, membership, org)
        token = _token_for(user, org.id, hours=hours)
    from app.agents.collections import seed_demo_invoices

    await seed_demo_invoices(org.id)
    return token, principal


# --- Team: members, roles, invitations ------------------------------------------------------------------------------

def _check_role(role: str) -> str:
    if role not in ROLES:
        raise BadRequest(f"Unknown role. Choose one of: {', '.join(ROLES)}.")
    return role


async def list_members(principal: Principal) -> list[dict]:
    async with session_scope() as db:
        rows = (await db.execute(select(Membership, User).join(User, User.id == Membership.user_id)
                                 .where(Membership.org_id == principal.org_id, Membership.status == "active")
                                 .order_by(Membership.id))).all()
        invites = (await db.scalars(select(Invitation).where(
            Invitation.org_id == principal.org_id, Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None),
            Invitation.expires_at > datetime.now(UTC)).order_by(Invitation.created_at))).all()
    return [{"user_id": u.id, "email": u.email, "name": u.name, "role": m.role, "you": u.id == principal.user_id}
            for m, u in rows] + [{"invitation_id": i.id, "email": i.email, "role": i.role, "pending": True,
                                  "expires_at": i.expires_at.isoformat()} for i in invites]


def _guard_admin_vs_owner(principal: Principal, target_role: str | None, new_role: str | None) -> None:
    """Admins manage the team but cannot touch owners or create them."""
    if principal.role == "owner":
        return
    if target_role == "owner" or new_role == "owner":
        raise AccessError("Only an owner can add, change or remove owners.")


async def invite(principal: Principal, email: str, role: str) -> dict:
    """Create an invitation link (shown once to the inviter; only its hash is stored)."""
    email, role = normalise_email(email), _check_role(role)
    _guard_admin_vs_owner(principal, None, role)
    token = secrets.token_urlsafe(32)
    async with session_scope() as db:
        existing = await db.scalar(select(Membership).join(User, User.id == Membership.user_id).where(
            Membership.org_id == principal.org_id, Membership.status == "active", User.email == email))
        if existing:
            raise Conflict("This person is already a member.")
        inv = Invitation(id=_new_id("inv"), org_id=principal.org_id, email=email, role=role, token_hash=_sha256(token),
                         invited_by=principal.user_id, expires_at=datetime.now(UTC) + timedelta(days=INVITE_DAYS))
        db.add(inv)
        await append_audit(db, org_id=principal.org_id, actor=principal.actor, action="team.invited",
                           details={"invitation_id": inv.id, "role": role, "email_sha256": _sha256(email)[:16]})
    return {"invitation_id": inv.id, "email": email, "role": role, "token": token,
            "expires_at": inv.expires_at.isoformat()}


async def invitation_info(token: str) -> dict:
    """What an invitation is for (organisation and role), for the accept page."""
    async with session_scope() as db:
        inv = await db.scalar(select(Invitation).where(Invitation.token_hash == _sha256(token)))
        if inv is None or inv.accepted_at or inv.revoked_at or inv.expires_at < datetime.now(UTC):
            raise NotFound("This invitation is not valid any more.")
        org = await db.get(Organisation, inv.org_id)
        has_account = bool(await db.scalar(select(User.id).where(User.email == inv.email)))
    return {"org_name": org.name if org else inv.org_id, "email": inv.email, "role": inv.role,
            "has_account": has_account}


async def accept_invitation(token: str, password: str, name: str = "") -> tuple[str, Principal]:
    """Join an organisation: existing users confirm with their password, new users choose one."""
    async with session_scope() as db:
        inv = await db.scalar(select(Invitation).where(Invitation.token_hash == _sha256(token)))
        if inv is None or inv.accepted_at or inv.revoked_at or inv.expires_at < datetime.now(UTC):
            raise NotFound("This invitation is not valid any more.")
        user = await db.scalar(select(User).where(User.email == inv.email))
        if user is None:
            check_strength(password)
            user = User(id=_new_id("usr"), email=inv.email, name=(name or "").strip()[:120],
                        password_hash=hash_password(password))
            db.add(user)
            await db.flush()
        elif not verify_password(password, user.password_hash):
            raise AuthError("Password is incorrect for this account.")
        membership = await db.scalar(select(Membership).where(Membership.user_id == user.id,
                                                              Membership.org_id == inv.org_id))
        if membership is None:
            membership = Membership(user_id=user.id, org_id=inv.org_id, role=inv.role)
            db.add(membership)
        else:
            membership.role, membership.status = inv.role, "active"
        inv.accepted_at = datetime.now(UTC)
        await db.flush()
        await append_audit(db, org_id=inv.org_id, actor=f"user:{user.id}", action="team.joined",
                           details={"invitation_id": inv.id, "role": inv.role})
        org = await db.get(Organisation, inv.org_id)
        return _token_for(user, inv.org_id), _principal(user, membership, org)


async def revoke_invitation(principal: Principal, invitation_id: str) -> None:
    async with session_scope() as db:
        inv = await db.get(Invitation, invitation_id)
        if inv is None or inv.org_id != principal.org_id or inv.accepted_at:
            raise NotFound("Invitation not found.")
        _guard_admin_vs_owner(principal, None, inv.role)
        inv.revoked_at = datetime.now(UTC)
        await append_audit(db, org_id=principal.org_id, actor=principal.actor, action="team.invitation_revoked",
                           details={"invitation_id": inv.id})


async def _owner_count(db, org_id: str) -> int:
    return await db.scalar(select(func.count()).select_from(Membership).where(
        Membership.org_id == org_id, Membership.role == "owner", Membership.status == "active")) or 0


async def change_role(principal: Principal, user_id: str, role: str) -> dict:
    """Change a member's role (owners only for anything involving the owner role; never the last owner)."""
    role = _check_role(role)
    async with session_scope() as db:
        membership = await _active_membership(db, user_id, principal.org_id)
        if membership is None:
            raise NotFound("Member not found.")
        _guard_admin_vs_owner(principal, membership.role, role)
        if membership.role == "owner" and role != "owner" and await _owner_count(db, principal.org_id) <= 1:
            raise Conflict("An organisation needs at least one owner. Make someone else owner first.")
        before = membership.role
        membership.role = role
        await append_audit(db, org_id=principal.org_id, actor=principal.actor, action="team.role_changed",
                           details={"user_id": user_id, "before": before, "after": role})
    return {"user_id": user_id, "role": role}


async def remove_member(principal: Principal, user_id: str) -> None:
    async with session_scope() as db:
        membership = await _active_membership(db, user_id, principal.org_id)
        if membership is None:
            raise NotFound("Member not found.")
        _guard_admin_vs_owner(principal, membership.role, None)
        if membership.role == "owner" and await _owner_count(db, principal.org_id) <= 1:
            raise Conflict("You cannot remove the last owner.")
        membership.status = "removed"
        await append_audit(db, org_id=principal.org_id, actor=principal.actor, action="team.removed",
                           details={"user_id": user_id, "role": membership.role})


# --- API keys (machine access: MCP) ---------------------------------------------------------------------------------

API_KEY_PREFIX = "jisr_mcp_"


async def create_api_key(principal: Principal, name: str, kind: str = "mcp") -> dict:
    """Create a key scoped to the caller's organisation. The full key is returned ONCE."""
    if kind != "mcp":
        raise BadRequest("Only 'mcp' keys exist: A2A is open to buyers' agents and governed like a buyer's message.")
    raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
    async with session_scope() as db:
        key = ApiKey(id=_new_id("key"), org_id=principal.org_id, name=(name or "MCP client").strip()[:80], kind=kind,
                     prefix=raw[:14], key_hash=_sha256(raw), created_by=principal.user_id)
        db.add(key)
        await append_audit(db, org_id=principal.org_id, actor=principal.actor, action="api_key.created",
                           details={"key_id": key.id, "kind": kind, "prefix": key.prefix})
    return {"id": key.id, "name": key.name, "kind": kind, "prefix": key.prefix, "key": raw}


async def list_api_keys(principal: Principal) -> list[dict]:
    async with session_scope() as db:
        rows = (await db.scalars(select(ApiKey).where(ApiKey.org_id == principal.org_id)
                                 .order_by(ApiKey.created_at.desc()))).all()
    return [{"id": k.id, "name": k.name, "kind": k.kind, "prefix": k.prefix, "created_at": k.created_at.isoformat(),
             "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
             "revoked": k.revoked_at is not None} for k in rows]


async def revoke_api_key(principal: Principal, key_id: str) -> None:
    async with session_scope() as db:
        key = await db.get(ApiKey, key_id)
        if key is None or key.org_id != principal.org_id:
            raise NotFound("Key not found.")
        key.revoked_at = datetime.now(UTC)
        await append_audit(db, org_id=principal.org_id, actor=principal.actor, action="api_key.revoked",
                           details={"key_id": key.id})


async def org_for_api_key(raw: str) -> str | None:
    """The organisation a valid, unrevoked key belongs to (and record its use), else None."""
    if not raw.startswith(API_KEY_PREFIX):
        return None
    async with session_scope() as db:
        key = await db.scalar(select(ApiKey).where(ApiKey.key_hash == _sha256(raw), ApiKey.revoked_at.is_(None)))
        if key is None:
            return None
        await db.execute(update(ApiKey).where(ApiKey.id == key.id).values(last_used_at=datetime.now(UTC)))
        return key.org_id
