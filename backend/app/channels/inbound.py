"""
inbound.py — One entry point for messages arriving on a channel (WhatsApp webhook or the local simulator).

Why this file exists:
    A message must be handled exactly once (webhooks are retried), its sender remembered for the reply (the phone
    number is personal data: stored for delivery, never shown to a model; runs only carry a hash), and a voice note
    turned into text before the agents see it. Both the real webhook and the simulator call `handle_inbound`, so the
    demo exercises the production path.

Data class of audio: a voice note from the real WhatsApp number is "real" data, so the router refuses to send it
to a free-tier STT model; the simulator's synthetic voice notes are "synthetic".
"""

import hashlib
from typing import Literal

from app.channels.whatsapp import InboundMessage, WhatsAppClient
from app.db.models import Contact, InboundLog
from app.db.session import session_scope
from app.governance.audit import append_audit
from app.llm.router import LLMBackendError, LLMPolicyError, TranscribeRequest, get_router


def contact_key(org_id: str, channel: str, address: str) -> str:
    """Stable, non-reversible id for a sender (what runs and logs refer to)."""
    return hashlib.sha256(f"{org_id}:{channel}:{address}".encode()).hexdigest()[:32]


async def handle_inbound(msg: InboundMessage, *, org_id: str, source: Literal["whatsapp", "simulator"],
                         audio: bytes | None = None, mime_type: str | None = None,
                         client: WhatsAppClient | None = None, background: bool = True) -> dict:
    """Process one inbound message. Returns {"status": created|duplicate|ignored|refused, "run_id"?, "reason"?}."""
    from app.runs.service import create_run  # local import: the service imports the agent graph

    key = contact_key(org_id, "whatsapp", msg.wa_id)
    async with session_scope() as db:
        seen = await db.get(InboundLog, msg.message_id)
        if seen is not None:
            return {"status": "duplicate", "run_id": seen.run_id}
        db.add(InboundLog(message_id=msg.message_id, org_id=org_id, kind=msg.kind))
        contact = await db.get(Contact, key)
        if contact is None:
            contact = Contact(contact_key=key, org_id=org_id, channel="whatsapp", address=msg.wa_id)
            db.add(contact)
        contact.display_name = msg.profile_name or contact.display_name
        contact.last_inbound_at = msg.timestamp

    meta: dict = {"source": source}
    if msg.kind == "text" and msg.text.strip():
        text = msg.text
    elif msg.kind == "audio":
        try:
            if audio is None:
                if client is None or not msg.media_id:
                    raise LLMBackendError("no media client configured")
                audio, mime_type = await client.fetch_media(msg.media_id)
            transcript = await get_router().transcribe(TranscribeRequest(
                audio=audio, mime_type=mime_type or "audio/ogg",
                data_class="synthetic" if source == "simulator" else "real"))
        except (LLMPolicyError, LLMBackendError) as exc:
            async with session_scope() as db:
                await append_audit(db, org_id=org_id, actor="channel:whatsapp", action="inbound.voice_not_transcribed",
                                   details={"message_id": msg.message_id, "reason": str(exc)[:300]})
            return {"status": "refused", "reason": str(exc)}
        text = transcript.text
        meta["voice_note"] = {"stt_model": transcript.model, "provider": transcript.provider,
                              "audio_sha256": transcript.audio_sha256[:12], "language": transcript.language}
    else:
        async with session_scope() as db:
            await append_audit(db, org_id=org_id, actor="channel:whatsapp", action="inbound.unsupported",
                               details={"message_id": msg.message_id, "kind": msg.kind})
        return {"status": "ignored", "reason": f"unsupported message type {msg.kind!r}"}

    run_id = await create_run(message=text, channel="whatsapp", org_id=org_id, contact_key=key, meta=meta,
                              background=background)
    async with session_scope() as db:
        log = await db.get(InboundLog, msg.message_id)
        log.run_id = run_id
    return {"status": "created", "run_id": run_id}
