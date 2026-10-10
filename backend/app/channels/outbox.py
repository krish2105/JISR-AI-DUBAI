"""
outbox.py — The ONLY way anything leaves Jisr (a message, later documents).

Why this file exists:
    Governance decides; this module performs. Both paths end here: a human approving a held action, and an action
    the policies and autonomy level allow automatically (e.g. a fixed-text acknowledgement). Keeping one door means
    one place to enforce the kill switch (checked again here, defence in depth), one audit format and one event.

Phase 7 delivers through the simulator (the text's SHA-256 is recorded, not the text). Phase 8 plugs the real
WhatsApp Cloud API in behind the same function.
"""

import hashlib
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OrgSettings
from app.governance.audit import append_audit


class KillSwitchEngaged(Exception):
    """Raised when something tries to leave while the organisation's kill switch is on."""


async def kill_switch_on(db: AsyncSession, org_id: str) -> bool:
    """Is the organisation's kill switch engaged?"""
    row = await db.get(OrgSettings, org_id)
    return bool(row and row.kill_switch)


async def set_kill_switch(db: AsyncSession, org_id: str, engaged: bool, actor: str, reason: str | None) -> OrgSettings:
    """Turn the kill switch on or off (audited)."""
    row = await db.get(OrgSettings, org_id)
    if row is None:
        row = OrgSettings(org_id=org_id)
        db.add(row)
    row.kill_switch, row.kill_reason = engaged, reason if engaged else None
    row.updated_by, row.updated_at = actor, datetime.now(UTC)
    await append_audit(db, org_id=org_id, actor=actor, action="kill_switch.on" if engaged else "kill_switch.off",
                       details={"reason": reason})
    return row


async def send(db: AsyncSession, *, org_id: str, run_id: str, action_type: str, payload: dict, actor: str,
               approval_id: str | None = None, autonomous: bool = False) -> dict:
    """Deliver an allowed action (simulator) and write the audit entry. Raises KillSwitchEngaged when stopped."""
    if await kill_switch_on(db, org_id):
        await append_audit(db, org_id=org_id, actor="channel:outbox", action="send.refused_kill_switch",
                           run_id=run_id, details={"action_type": action_type, "approval_id": approval_id})
        raise KillSwitchEngaged("Kill switch is on: nothing leaves Jisr.")
    text = payload.get("text", "")
    sent = {"channel": f"{payload.get('channel', 'form')}_simulator", "action_type": action_type,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], "autonomous": autonomous}
    action = "action.autonomous_sent" if autonomous else "message.sent_simulated"
    await append_audit(db, org_id=org_id, actor="channel:simulator", action=action, run_id=run_id,
                       details={"approval_id": approval_id, "by": actor, **sent})
    return sent
