"""
ratelimit.py — Per-IP limit on starting runs, for the public no-login demo.

Why: the hosted demo is open to judges without an account, so one visitor must not be able to burn the model budget.
In-memory sliding window per process (one machine hosts the demo); 0 in settings = no limit (local, tests).
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings

_hits: dict[str, deque] = defaultdict(deque)
WINDOW = 3600.0


def client_ip(request: Request) -> str:
    """The caller's IP (first X-Forwarded-For hop behind Fly's proxy, else the socket peer)."""
    forwarded = request.headers.get("fly-client-ip") or request.headers.get("x-forwarded-for", "").split(",")[0]
    return forwarded.strip() or (request.client.host if request.client else "unknown")


def limit_runs(request: Request) -> None:
    """FastAPI dependency: 429 when this IP started too many runs in the last hour."""
    limit = get_settings().public_runs_per_hour
    if not limit:
        return
    now, hits = time.monotonic(), _hits[client_ip(request)]
    while hits and now - hits[0] > WINDOW:
        hits.popleft()
    if len(hits) >= limit:
        raise HTTPException(429, f"Demo limit: {limit} runs per hour from one address. Please try again later.")
    hits.append(now)
