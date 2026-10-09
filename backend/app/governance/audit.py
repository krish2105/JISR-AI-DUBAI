"""
audit.py — Append-only, hash-chained audit log.

Why this file exists:
    Judges and pilot users must be able to trust "who or what did what, when". Each audit
    entry stores the hash of the previous entry of the same organisation, and its own hash
    covers its content plus that previous hash. If anyone edits or deletes a past row, the
    chain no longer adds up and `verify_chain` reports the first broken row.

    entry_1.hash = sha256(content_1 + "GENESIS")
    entry_2.hash = sha256(content_2 + entry_1.hash)   ... and so on.

Phase 1 version (v0): one in-process lock serialises appends. Phase 7 adds a database-level
lock so several API instances can append safely.
"""

import asyncio
import hashlib
import json
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEntry, utcnow

GENESIS = "GENESIS"
_append_lock = asyncio.Lock()


def _iso_utc(ts: datetime) -> str:
    """Format a timestamp the same way at write time and verify time (SQLite drops tzinfo)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC).isoformat()


def compute_hash(
    *, org_id: str, ts: datetime, actor: str, action: str, run_id: str | None, details: dict, prev_hash: str
) -> str:
    """Hash the canonical JSON of an entry's content together with the previous hash."""
    canonical = json.dumps(
        {
            "org_id": org_id,
            "ts": _iso_utc(ts),
            "actor": actor,
            "action": action,
            "run_id": run_id,
            "details": details,
            "prev_hash": prev_hash,
        },
        sort_keys=True,          # same key order every time, so the same content -> same hash
        ensure_ascii=False,      # keep Arabic text as-is
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def append_audit(
    db: AsyncSession, *, org_id: str, actor: str, action: str, run_id: str | None = None, details: dict | None = None
) -> AuditEntry:
    """Add one entry to the organisation's chain and return it (caller commits)."""
    details = details or {}
    async with _append_lock:
        last = await db.scalar(
            select(AuditEntry).where(AuditEntry.org_id == org_id).order_by(AuditEntry.id.desc()).limit(1)
        )
        prev_hash = last.hash if last else GENESIS
        ts = utcnow()
        entry = AuditEntry(
            org_id=org_id,
            ts=ts,
            actor=actor,
            action=action,
            run_id=run_id,
            details=details,
            prev_hash=prev_hash,
            hash=compute_hash(
                org_id=org_id, ts=ts, actor=actor, action=action, run_id=run_id, details=details, prev_hash=prev_hash
            ),
        )
        db.add(entry)
        await db.flush()          # assigns the id now, so the next append sees this row
        return entry


class ChainReport(BaseModel):
    """Result of verifying an organisation's audit chain."""

    ok: bool
    entries: int
    broken_at_id: int | None = None
    reason: str | None = None


async def verify_chain(db: AsyncSession, org_id: str) -> ChainReport:
    """Recompute every hash in order; report the first row that does not match."""
    rows = (
        await db.scalars(select(AuditEntry).where(AuditEntry.org_id == org_id).order_by(AuditEntry.id))
    ).all()
    expected_prev = GENESIS
    for row in rows:
        if row.prev_hash != expected_prev:
            return ChainReport(ok=False, entries=len(rows), broken_at_id=row.id, reason="link to previous entry broken")
        recomputed = compute_hash(
            org_id=row.org_id, ts=row.ts, actor=row.actor, action=row.action,
            run_id=row.run_id, details=row.details, prev_hash=row.prev_hash,
        )
        if recomputed != row.hash:
            return ChainReport(ok=False, entries=len(rows), broken_at_id=row.id, reason="content was modified")
        expected_prev = row.hash
    return ChainReport(ok=True, entries=len(rows))
