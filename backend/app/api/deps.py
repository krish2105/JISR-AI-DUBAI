"""
deps.py — Shared request helpers for API routes.

Why: every route must know which organisation is asking, so it can only see that
organisation's data. Phase 1 reads an optional `X-Org-Id` header and falls back to the
public demo org; real authentication replaces this before the pilot (Phase 10).
"""

from fastapi import Header

from app.config import get_settings


def org_id_header(x_org_id: str | None = Header(default=None)) -> str:
    """Return the caller's organisation id (the demo org when no header is sent)."""
    return x_org_id or get_settings().default_org_id
