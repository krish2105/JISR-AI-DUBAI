"""
test_audit.py — The hash-chained audit log detects tampering.
"""

from sqlalchemy import delete, select, update

from app.db.models import AuditEntry
from app.db.session import session_scope
from app.governance.audit import GENESIS, append_audit, verify_chain


async def _seed(org: str = "org_a", n: int = 3) -> None:
    """Append n entries for one organisation."""
    async with session_scope() as db:
        for i in range(n):
            await append_audit(db, org_id=org, actor="test", action=f"step.{i}", details={"i": i, "text": "مرحبا"})


async def test_chain_verifies_when_untouched(db_ready):
    """A clean chain verifies, and the first entry links to GENESIS."""
    await _seed()
    async with session_scope() as db:
        report = await verify_chain(db, "org_a")
        first = await db.scalar(select(AuditEntry).order_by(AuditEntry.id).limit(1))
    assert report.ok and report.entries == 3
    assert first.prev_hash == GENESIS


async def test_modified_row_is_detected(db_ready):
    """Changing a past row's details breaks its hash."""
    await _seed()
    async with session_scope() as db:
        await db.execute(update(AuditEntry).where(AuditEntry.action == "step.1").values(details={"i": 999}))
    async with session_scope() as db:
        report = await verify_chain(db, "org_a")
    assert not report.ok
    assert report.reason == "content was modified"


async def test_deleted_row_is_detected(db_ready):
    """Deleting a middle row breaks the link from the next row."""
    await _seed()
    async with session_scope() as db:
        await db.execute(delete(AuditEntry).where(AuditEntry.action == "step.1"))
    async with session_scope() as db:
        report = await verify_chain(db, "org_a")
    assert not report.ok
    assert report.reason == "link to previous entry broken"


async def test_chains_are_separate_per_organisation(db_ready):
    """Each organisation has its own chain; one org's entries never affect another's."""
    await _seed("org_a", 2)
    await _seed("org_b", 2)
    async with session_scope() as db:
        assert (await verify_chain(db, "org_a")).entries == 2
        assert (await verify_chain(db, "org_b")).ok


async def test_timestamps_come_back_timezone_aware(db_ready):
    """Stored times are returned in UTC with their zone (SQLite would otherwise drop it)."""
    await _seed(n=1)
    async with session_scope() as db:
        entry = await db.scalar(select(AuditEntry).limit(1))
    assert entry.ts.tzinfo is not None and entry.ts.utcoffset().total_seconds() == 0
