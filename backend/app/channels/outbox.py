"""
outbox.py — The ONLY way anything leaves Jisr (a message, later documents).

Why this file exists:
    Governance decides; this module performs. Both paths end here: a human approving a held action, and an action
    the policies and autonomy level allow automatically (e.g. a fixed-text acknowledgement). Keeping one door means
    one place to enforce the kill switch (checked again here, defence in depth), one audit format and one event.

Delivery: the real WhatsApp Cloud API when it is configured and the run has a WhatsApp contact (within Meta's
24-hour service window; outside it a template would be needed, so the send is refused and audited), otherwise the
simulator. The audit records the text's SHA-256, never the text.
"""

import hashlib
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.whatsapp import WhatsAppClient, within_service_window
from app.config import get_settings
from app.db.models import Contact, OrgSettings, Run
from app.governance.audit import append_audit


class KillSwitchEngaged(Exception):
    """Raised when something tries to leave while the organisation's kill switch is on."""


class OutsideServiceWindow(Exception):
    """WhatsApp free-form messages are only allowed within 24 h of the buyer's last message."""


_client: WhatsAppClient | None = None


def whatsapp_client() -> WhatsAppClient | None:
    """The configured Cloud API client, or None when WhatsApp is not enabled (simulator)."""
    global _client
    s = get_settings()
    if not (s.whatsapp_enabled and s.whatsapp_access_token and s.whatsapp_phone_number_id):
        return None
    if _client is None:
        _client = WhatsAppClient(s.whatsapp_access_token, s.whatsapp_phone_number_id, s.whatsapp_api_version)
    return _client


def set_whatsapp_client(client: WhatsAppClient | None) -> None:
    """Tests inject a client with a mocked transport."""
    global _client
    _client = client


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


async def service_window_open(db: AsyncSession, run_id: str | None) -> bool:
    """False only when the reply would go to real WhatsApp and the buyer's 24 h window has closed."""
    run = await db.get(Run, run_id) if run_id else None
    contact = await db.get(Contact, run.contact_key) if run is not None and run.contact_key else None
    if whatsapp_client() is None or contact is None or contact.channel != "whatsapp":
        return True
    return within_service_window(contact.last_inbound_at)


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
    run = await db.get(Run, run_id) if run_id else None
    contact = await db.get(Contact, run.contact_key) if run is not None and run.contact_key else None
    client = whatsapp_client()
    if contact is not None and contact.channel == "a2a":           # a buyer's agent: complete its A2A task
        from app.interop.a2a_server import deliver

        sent |= await deliver(contact.address, payload, org_id)
    elif client is not None and contact is not None and contact.channel == "whatsapp":
        if not within_service_window(contact.last_inbound_at):
            await append_audit(db, org_id=org_id, actor="channel:whatsapp", action="send.refused_window",
                               run_id=run_id, details={"action_type": action_type, "approval_id": approval_id})
            raise OutsideServiceWindow("More than 24 h since the buyer's last message: a template is required.")
        sent["provider_message_id"] = await client.send_text(contact.address, text)
        sent["channel"] = "whatsapp"
    action = ("action.autonomous_sent" if autonomous else
              "message.sent_whatsapp" if sent["channel"] == "whatsapp" else
              "message.sent_a2a" if sent["channel"] == "a2a" else "message.sent_simulated")
    await append_audit(db, org_id=org_id, actor="channel:simulator", action=action, run_id=run_id,
                       details={"approval_id": approval_id, "by": actor, **sent})
    return sent
