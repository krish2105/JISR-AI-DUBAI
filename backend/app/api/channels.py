"""
channels.py — WhatsApp webhook (Meta Cloud API) and the local simulator that takes the same path.

    GET  /channels/whatsapp/webhook          Meta's verification handshake (hub.verify_token -> hub.challenge)
    POST /channels/whatsapp/webhook          signed message delivery (X-Hub-Signature-256); unsigned = 401
    POST /channels/whatsapp/simulate         {text} or {voice_sample}: builds a webhook payload, signs it with the
                                             simulator secret and processes it exactly like a real delivery
    GET  /channels/whatsapp/voice-samples    the synthetic demo voice notes (language, transcript, audio URL)
    GET  /channels/whatsapp/voice/{name}     the audio file of a synthetic voice note (for the dashboard player)
"""

import asyncio
import json
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.api.ratelimit import limit_runs
from app.channels.inbound import handle_inbound
from app.channels.outbox import whatsapp_client
from app.channels.whatsapp import parse_webhook, sign, verify_signature
from app.config import get_settings
from app.db.session import session_scope
from app.governance.audit import append_audit
from app.llm.router import VOICE_MANIFEST

router = APIRouter(prefix="/channels/whatsapp", tags=["channels"])
_tasks: set[asyncio.Task] = set()
VOICE_DIR = VOICE_MANIFEST.parent


def _voice_samples() -> dict[str, dict]:
    """name -> {file, language, transcript, mime_type} for the synthetic voice notes."""
    if not VOICE_MANIFEST.exists():
        return {}
    manifest = json.loads(VOICE_MANIFEST.read_text(encoding="utf-8"))
    return {Path(v["file"]).stem: v for v in manifest.values()}


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(mode: str = Query("", alias="hub.mode"), token: str = Query("", alias="hub.verify_token"),
                         challenge: str = Query("", alias="hub.challenge")) -> str:
    """Meta calls this once when the webhook URL is registered."""
    expected = get_settings().whatsapp_verify_token
    if mode == "subscribe" and expected and token == expected:
        return challenge
    raise HTTPException(403, "verification failed")


async def process_payload(raw: bytes, signature: str | None, secret: str, *, source: str,
                          audio: bytes | None = None, mime_type: str | None = None, wait: bool = False,
                          run_in_background: bool = True) -> list[dict]:
    """Verify, parse and hand every message to the inbound handler. Shared by the webhook and the simulator."""
    if not verify_signature(raw, signature, secret):
        async with session_scope() as db:
            await append_audit(db, org_id=get_settings().whatsapp_org_id, actor="channel:whatsapp",
                               action="webhook.rejected_signature", details={"source": source, "bytes": len(raw)})
        raise HTTPException(401, "invalid signature")
    messages = parse_webhook(json.loads(raw))
    org_id = get_settings().whatsapp_org_id
    results = []
    for msg in messages:
        job = handle_inbound(msg, org_id=org_id, source=source, audio=audio, mime_type=mime_type,  # type: ignore[arg-type]
                             client=whatsapp_client(), background=run_in_background)
        if wait:
            results.append(await job)
        else:                                   # answer Meta fast; the work continues in the background
            task = asyncio.create_task(job)
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)
            results.append({"status": "accepted", "message_id": msg.message_id})
    return results


@router.post("/webhook")
async def receive_webhook(request: Request) -> dict:
    """Real deliveries from Meta. The signature is checked against the RAW body before anything is parsed."""
    secret = get_settings().whatsapp_app_secret
    if not secret:
        raise HTTPException(503, "WhatsApp is not configured on this server")
    raw = await request.body()
    results = await process_payload(raw, request.headers.get("x-hub-signature-256"), secret, source="whatsapp")
    return {"received": len(results)}


class SimulateBody(BaseModel):
    """A simulated WhatsApp message: text, or one of the synthetic voice notes."""

    text: str | None = Field(default=None, max_length=8000)
    voice_sample: str | None = None
    sender: str = "971500000001"               # a fictional number
    name: str = "Demo buyer"


@router.post("/simulate", dependencies=[Depends(limit_runs)])
async def simulate(body: SimulateBody, sync: bool = False) -> dict:
    """Build a webhook payload like Meta's, sign it, and process it through the same code as real deliveries."""
    if not body.text and not body.voice_sample:
        raise HTTPException(422, "text or voice_sample is required")
    message: dict = {"from": body.sender, "id": f"wamid.SIM{uuid.uuid4().hex[:20]}", "timestamp": str(int(time.time()))}
    audio = mime = None
    if body.voice_sample:
        sample = _voice_samples().get(body.voice_sample)
        if sample is None:
            raise HTTPException(404, "unknown voice sample")
        audio, mime = (VOICE_DIR / sample["file"]).read_bytes(), sample["mime_type"]
        message |= {"type": "audio",
                    "audio": {"id": f"media.SIM.{body.voice_sample}", "mime_type": mime, "voice": True}}
    else:
        message |= {"type": "text", "text": {"body": body.text}}
    value = {"messaging_product": "whatsapp", "metadata": {"display_phone_number": "SIM", "phone_number_id": "SIM"},
             "contacts": [{"profile": {"name": body.name}, "wa_id": body.sender}], "messages": [message]}
    payload = {"object": "whatsapp_business_account",
               "entry": [{"id": "SIM", "changes": [{"field": "messages", "value": value}]}]}
    raw = json.dumps(payload).encode()
    secret = get_settings().simulator_secret
    # Returns as soon as the run exists (the dashboard then follows it live); ?sync=true waits for the agents (tests).
    results = await process_payload(raw, sign(raw, secret), secret, source="simulator", audio=audio, mime_type=mime,
                                    wait=True, run_in_background=not sync)
    return results[0]


@router.get("/voice-samples")
async def voice_samples() -> list[dict]:
    """Synthetic voice notes available to the simulator."""
    return [{"name": name, "language": v["language"], "transcript": v["transcript"],
             "audio_url": f"/channels/whatsapp/voice/{name}"} for name, v in _voice_samples().items()]


@router.get("/voice/{name}")
async def voice_file(name: str) -> FileResponse:
    """Audio of a synthetic voice note."""
    sample = _voice_samples().get(name)
    if sample is None:
        raise HTTPException(404, "unknown voice sample")
    return FileResponse(VOICE_DIR / sample["file"], media_type=sample["mime_type"])
