"""
team.py — Team management and machine keys for one organisation (Phase 13).

    GET    /team/members                 members and pending invitations        (team.read)
    POST   /team/invitations             invite by email with a role            (team.manage)
    DELETE /team/invitations/{id}        revoke a pending invitation            (team.manage)
    PATCH  /team/members/{user_id}       change a member's role                 (team.manage)
    DELETE /team/members/{user_id}       remove a member                        (team.manage)
    GET    /team/api-keys                list MCP keys (never the secret)       (api_keys.manage)
    POST   /team/api-keys                create a key, shown ONCE               (api_keys.manage)
    DELETE /team/api-keys/{id}           revoke a key                           (api_keys.manage)

Admins manage the team but cannot add, change or remove owners; the last owner can never be removed.
Invitations and keys are disabled in demo sandboxes (nobody real should be invited into throw-away data).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import http_errors, require
from app.auth import service
from app.auth.service import Principal

router = APIRouter(prefix="/team", tags=["team"])


class InviteBody(BaseModel):
    email: str = Field(max_length=254)
    role: str = Field(max_length=20)


class RoleBody(BaseModel):
    role: str = Field(max_length=20)


class KeyBody(BaseModel):
    name: str = Field(default="MCP client", max_length=80)


def _no_sandbox(principal: Principal) -> None:
    if principal.is_sandbox:
        raise HTTPException(403, "Not available in the demo sandbox. Create your own organisation to invite people.")


@router.get("/members")
async def members(principal: Principal = Depends(require("team.read"))) -> list[dict]:
    return await service.list_members(principal)


@router.post("/invitations", status_code=201)
async def invite(body: InviteBody, principal: Principal = Depends(require("team.manage"))) -> dict:
    _no_sandbox(principal)
    with http_errors():
        return await service.invite(principal, body.email, body.role)


@router.delete("/invitations/{invitation_id}")
async def revoke_invitation(invitation_id: str, principal: Principal = Depends(require("team.manage"))) -> dict:
    with http_errors():
        await service.revoke_invitation(principal, invitation_id)
    return {"ok": True}


@router.patch("/members/{user_id}")
async def change_role(user_id: str, body: RoleBody, principal: Principal = Depends(require("team.manage"))) -> dict:
    with http_errors():
        return await service.change_role(principal, user_id, body.role)


@router.delete("/members/{user_id}")
async def remove(user_id: str, principal: Principal = Depends(require("team.manage"))) -> dict:
    with http_errors():
        await service.remove_member(principal, user_id)
    return {"ok": True}


@router.get("/api-keys")
async def api_keys(principal: Principal = Depends(require("api_keys.manage"))) -> list[dict]:
    return await service.list_api_keys(principal)


@router.post("/api-keys", status_code=201)
async def create_key(body: KeyBody, principal: Principal = Depends(require("api_keys.manage"))) -> dict:
    _no_sandbox(principal)
    with http_errors():
        return await service.create_api_key(principal, body.name)


@router.delete("/api-keys/{key_id}")
async def revoke_key(key_id: str, principal: Principal = Depends(require("api_keys.manage"))) -> dict:
    with http_errors():
        await service.revoke_api_key(principal, key_id)
    return {"ok": True}
