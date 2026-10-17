"""
deps.py — Who is calling, and may they do this? (Phase 13: authentication and RBAC.)

Every business route depends on `current_principal` (a verified access token -> user, organisation, CURRENT role)
or on `require("<permission>")`, which also checks the role against app/governance/rbac.yaml. The organisation
always comes from the verified token, never from a header the caller controls.

Test-only fallback: under APP_ENV=test a request WITHOUT an Authorization header acts as an Owner of the
organisation in `X-Org-Id` (or the default), so the older API tests keep working. Production and dev never do this:
there, a missing or invalid token is 401. RBAC tests always send real tokens.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from fastapi import Depends, Header, HTTPException

from app.auth.passwords import WeakPassword
from app.auth.service import (
    AccessError,
    AuthError,
    BadRequest,
    Conflict,
    NotFound,
    Principal,
    principal_from_token,
)
from app.billing.service import QuotaExceeded
from app.config import get_settings
from app.governance.rbac import Forbidden, get_rbac

UNAUTHORISED = {"WWW-Authenticate": "Bearer"}


def bearer_token(authorization: str | None) -> str | None:
    """The token from an `Authorization: Bearer <token>` header."""
    if authorization and authorization[:7].lower() == "bearer ":
        return authorization[7:].strip() or None
    return None


async def current_principal(authorization: str | None = Header(default=None),
                            x_org_id: str | None = Header(default=None)) -> Principal:
    """The verified caller (401 when there is no valid session)."""
    token = bearer_token(authorization)
    if token:
        try:
            return await principal_from_token(token)
        except AuthError as exc:
            raise HTTPException(401, str(exc), headers=UNAUTHORISED) from exc
    settings = get_settings()
    if settings.app_env == "test":
        return Principal(user_id="test-user", org_id=x_org_id or settings.default_org_id, role="owner",
                         permissions=tuple(get_rbac().permissions_of("owner")))
    raise HTTPException(401, "Sign in to continue.", headers=UNAUTHORISED)


def require(permission: str) -> Callable:
    """Route dependency: the caller must hold `permission` (403 otherwise, with the reason)."""

    async def checker(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.can(permission):
            label = get_rbac().roles.get(principal.role, {}).get("label", principal.role)
            raise HTTPException(403, f"Your role ({label}) does not allow this ({permission}).")
        return principal

    checker.__name__ = f"require_{permission.replace('.', '_')}"
    return checker


@contextmanager
def http_errors() -> Iterator[None]:
    """Map service exceptions to HTTP status codes in one place."""
    try:
        yield
    except AuthError as exc:
        raise HTTPException(401, str(exc), headers=UNAUTHORISED) from exc
    except (AccessError, Forbidden) as exc:
        raise HTTPException(403, str(exc)) from exc
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (BadRequest, WeakPassword) as exc:
        raise HTTPException(422, str(exc)) from exc
    except QuotaExceeded as exc:
        raise HTTPException(402, str(exc)) from exc
