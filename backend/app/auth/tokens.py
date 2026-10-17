"""
tokens.py — Signed access tokens (JWT, HS256) for the dashboard and short stream tokens for live events.

Access token claims: sub (user id), org (organisation id), sv (session version: "sign out everywhere" bumps it),
typ="access", iat, exp. The role is NOT in the token: it is read from the database on every request, so a role
change or removal takes effect immediately.
Stream tokens (typ="stream") let the browser's EventSource, which cannot send headers, open one run's live events.
"""

from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

ALGORITHM = "HS256"
DEV_SECRET = "jisr-dev-and-test-only-secret-never-use-in-production-2026"
STREAM_MINUTES = 30


class AuthConfigError(RuntimeError):
    """AUTH_SECRET is missing or too short in production."""


class InvalidToken(Exception):
    """The token is missing, expired, tampered with or of the wrong kind."""


def signing_secret() -> str:
    """AUTH_SECRET in production (required, 32+ characters); a fixed local secret elsewhere."""
    s = get_settings()
    if s.auth_secret:
        if s.app_env == "prod" and len(s.auth_secret) < 32:
            raise AuthConfigError("AUTH_SECRET must be at least 32 characters in production.")
        return s.auth_secret
    if s.app_env == "prod":
        raise AuthConfigError("AUTH_SECRET is not set: refusing to sign tokens in production.")
    return DEV_SECRET


def _encode(claims: dict, lifetime: timedelta) -> str:
    now = datetime.now(UTC)
    return jwt.encode({**claims, "iat": now, "exp": now + lifetime}, signing_secret(), algorithm=ALGORITHM)


def issue_access_token(user_id: str, org_id: str, session_version: int, hours: float | None = None) -> str:
    """A token that signs the user into one organisation."""
    lifetime = timedelta(hours=hours if hours is not None else get_settings().access_token_hours)
    return _encode({"sub": user_id, "org": org_id, "sv": session_version, "typ": "access"}, lifetime)


def issue_stream_token(user_id: str, org_id: str, run_id: str) -> str:
    """A short token valid only for the live events of one run."""
    return _encode({"sub": user_id, "org": org_id, "run": run_id, "typ": "stream"}, timedelta(minutes=STREAM_MINUTES))


def decode(token: str, expected_type: str) -> dict:
    """Verify signature, expiry and type; raise InvalidToken otherwise."""
    try:
        claims = jwt.decode(token, signing_secret(), algorithms=[ALGORITHM],
                            options={"require": ["exp", "iat", "sub", "org", "typ"]})
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc
    if claims.get("typ") != expected_type:
        raise InvalidToken("wrong token type")
    return claims
