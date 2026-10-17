"""
ratelimit.py — Per-IP limits on starting runs and on sign-in attempts (hosted demo protection).

Why in the database (Phase 20, DECISIONS H3): with two or more API machines an in-process counter would let each
machine allow the full limit. A fixed-window counter row per (bucket, IP, window) is incremented atomically with
INSERT … ON CONFLICT DO UPDATE … RETURNING (Postgres and SQLite), so every machine sees the same count.
0 in settings = no limit.
"""

import random
import time

from fastapi import HTTPException, Request
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import get_settings
from app.db.models import RateCounter
from app.db.session import session_scope

RUNS_WINDOW = 3600
LOGIN_WINDOW = 60


def client_ip(request: Request) -> str:
    """The caller's IP (first X-Forwarded-For hop behind Fly's proxy, else the socket peer)."""
    forwarded = request.headers.get("fly-client-ip") or request.headers.get("x-forwarded-for", "").split(",")[0]
    return forwarded.strip() or (request.client.host if request.client else "unknown")


async def hit(bucket: str, subject: str, limit: int, window: int) -> bool:
    """Count one request; True while the subject is within `limit` for the current window."""
    now = int(time.time())
    start = now - now % window
    key = f"{bucket}:{subject}:{start}"[:200]
    async with session_scope() as db:
        insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
        stmt = (insert(RateCounter).values(key=key, window_start=start, count=1)
                .on_conflict_do_update(index_elements=["key"], set_={"count": RateCounter.count + 1})
                .returning(RateCounter.count))
        count = (await db.execute(stmt)).scalar_one()
        if random.random() < 0.02:                                   # prune old windows now and then
            await db.execute(delete(RateCounter).where(RateCounter.window_start < now - 86400))
    return count <= limit


async def limit_runs(request: Request) -> None:
    """FastAPI dependency: 429 when this IP started too many runs in the current hour."""
    limit = get_settings().public_runs_per_hour
    if limit and not await hit("runs", client_ip(request), limit, RUNS_WINDOW):
        raise HTTPException(429, f"Demo limit: {limit} runs per hour from one address. Please try again later.")


async def limit_logins(request: Request) -> None:
    """FastAPI dependency: 429 after too many sign-in or sign-up attempts from one IP in a minute (slows guessing)."""
    limit = get_settings().login_attempts_per_minute
    if limit and not await hit("login", client_ip(request), limit, LOGIN_WINDOW):
        raise HTTPException(429, "Too many attempts. Please wait a minute and try again.")


def reset_limits() -> None:
    """Counters live in the (per-test) database now; kept for the test fixtures' interface."""
