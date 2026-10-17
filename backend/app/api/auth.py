"""
auth.py — Sign-up, sign-in, demo sandbox, organisation switch, sign-out everywhere, invitations (Phase 13).

    GET  /auth/config                     what the sign-in page should offer (demo, sign-up)
    POST /auth/signup                     new user + organisation (they become its Owner)
    POST /auth/login                      email + password -> access token
    POST /auth/demo                       a private sandbox organisation for one visitor (DEMO_MODE)
    GET  /auth/me                         user, organisation, role, permissions, organisations to switch to
    POST /auth/switch                     token for another organisation the user belongs to
    POST /auth/logout-all                 invalidate every token of this user
    GET  /auth/invitations/{token}        what an invitation is for
    POST /auth/invitations/accept         join the organisation (new users choose a password)

Tokens are returned in the JSON body and sent back as `Authorization: Bearer <token>` (DECISIONS S9).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import current_principal, http_errors
from app.api.ratelimit import limit_logins
from app.auth import service
from app.auth.service import Principal
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupBody(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)
    name: str = Field(default="", max_length=120)
    org_name: str = Field(default="", max_length=160)


class LoginBody(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)
    org_id: str | None = Field(default=None, max_length=40)


class SwitchBody(BaseModel):
    org_id: str = Field(max_length=40)


class AcceptBody(BaseModel):
    token: str = Field(max_length=200)
    password: str = Field(max_length=200)
    name: str = Field(default="", max_length=120)


async def _session(token: str, principal: Principal) -> dict:
    return {"token": token, "me": await service.me(principal)}


@router.get("/config")
def auth_config() -> dict:
    """Public: which sign-in options this server offers."""
    s = get_settings()
    return {"demo_mode": s.demo_mode, "allow_signup": s.allow_signup, "sandbox_hours": s.sandbox_hours}


@router.post("/signup", dependencies=[Depends(limit_logins)], status_code=201)
async def signup(body: SignupBody) -> dict:
    with http_errors():
        token, principal = await service.signup(body.email, body.password, body.name, body.org_name)
    return await _session(token, principal)


@router.post("/login", dependencies=[Depends(limit_logins)])
async def login(body: LoginBody) -> dict:
    with http_errors():
        token, principal = await service.login(body.email, body.password, body.org_id)
    return await _session(token, principal)


@router.post("/demo", dependencies=[Depends(limit_logins)], status_code=201)
async def demo() -> dict:
    """A private sandbox (synthetic data, expires) where the visitor can try everything, including approvals."""
    with http_errors():
        token, principal = await service.create_sandbox()
    return await _session(token, principal)


@router.get("/me")
async def me(principal: Principal = Depends(current_principal)) -> dict:
    return await service.me(principal)


@router.post("/switch")
async def switch(body: SwitchBody, principal: Principal = Depends(current_principal)) -> dict:
    with http_errors():
        token, new = await service.switch_org(principal, body.org_id)
    return await _session(token, new)


@router.post("/logout-all")
async def logout_all(principal: Principal = Depends(current_principal)) -> dict:
    with http_errors():
        await service.sign_out_everywhere(principal)
    return {"ok": True}


@router.get("/invitations/{token}")
async def invitation(token: str) -> dict:
    with http_errors():
        return await service.invitation_info(token)


@router.post("/invitations/accept", dependencies=[Depends(limit_logins)])
async def accept(body: AcceptBody) -> dict:
    with http_errors():
        token, principal = await service.accept_invitation(body.token, body.password, body.name)
    return await _session(token, principal)
