"""
test_channels.py — WhatsApp Cloud API boundary, voice notes, simulator, 24 h window and collections (Phase 8).

No network: the Graph API is mocked with httpx.MockTransport; voice notes are the synthetic files in replay/voice.
"""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.agents.collections import reminder_text, run_collections, seed_demo_invoices, tone_for
from app.channels import outbox
from app.channels.whatsapp import WhatsAppClient, parse_webhook, sign, verify_signature, within_service_window
from app.db.models import Approval, AuditEntry, Contact, Invoice, Run
from app.db.session import session_scope
from app.llm.router import LLMPolicyError, TranscribeRequest, get_router

SIM = "/channels/whatsapp/simulate?sync=true"           # wait for the agents (the dashboard does not)


@pytest.fixture
async def client(db_ready):
    from app.main import create_app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://test") as c:
        yield c


def payload(text: str = "We need 100 brass lamps CIF Dubai", msg_id: str = "wamid.TEST1") -> dict:
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
        "contacts": [{"profile": {"name": "Ahmed"}, "wa_id": "971501234567"}],
        "messages": [{"from": "971501234567", "id": msg_id, "timestamp": "1760000000", "type": "text",
                      "text": {"body": text}}]}}]}]}


# ---------- boundary ------------------------------------------------------------------------------


def test_signature_must_match_the_raw_body():
    raw = json.dumps(payload()).encode()
    assert verify_signature(raw, sign(raw, "s3cret"), "s3cret")
    assert not verify_signature(raw + b" ", sign(raw, "s3cret"), "s3cret")          # body changed
    assert not verify_signature(raw, sign(raw, "other"), "s3cret")                   # wrong secret
    assert not verify_signature(raw, None, "s3cret") and not verify_signature(raw, sign(raw, ""), "")


def test_parse_text_and_voice_messages():
    voice = payload()
    voice["entry"][0]["changes"][0]["value"]["messages"][0] = {
        "from": "971501234567", "id": "wamid.V", "timestamp": "1760000000", "type": "audio",
        "audio": {"id": "MEDIA1", "mime_type": "audio/ogg; codecs=opus", "voice": True}}
    [text_msg] = parse_webhook(payload())
    [voice_msg] = parse_webhook(voice)
    assert text_msg.kind == "text" and text_msg.profile_name == "Ahmed" and text_msg.text.startswith("We need")
    assert voice_msg.kind == "audio" and voice_msg.media_id == "MEDIA1"


def test_24_hour_service_window():
    now = datetime.now(UTC)
    assert within_service_window(now - timedelta(hours=23), now)
    assert not within_service_window(now - timedelta(hours=25), now) and not within_service_window(None, now)


async def test_graph_client_fetches_media_and_sends_text():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "lookaside.example":
            return httpx.Response(200, content=b"OGG")
        if request.url.path.endswith("/MEDIA1"):
            return httpx.Response(200, json={"url": "https://lookaside.example/MEDIA1", "mime_type": "audio/ogg"})
        assert request.headers["authorization"] == "Bearer TOKEN"
        body = json.loads(request.content)
        assert body["to"] == "971501234567" and body["type"] == "text"
        return httpx.Response(200, json={"messages": [{"id": "wamid.OUT"}]})

    c = WhatsAppClient("TOKEN", "PNID", "v23.0", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await c.fetch_media("MEDIA1") == (b"OGG", "audio/ogg")
    assert await c.send_text("971501234567", "hello") == "wamid.OUT"


# ---------- webhook + simulator ----------------------------------------------------------------------


async def test_webhook_verification_handshake(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "my-token")
    from app.config import get_settings

    get_settings.cache_clear()
    ok = await client.get("/channels/whatsapp/webhook",
                          params={"hub.mode": "subscribe", "hub.verify_token": "my-token", "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    bad = await client.get("/channels/whatsapp/webhook",
                           params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"})
    assert bad.status_code == 403


async def test_unsigned_webhook_is_rejected_and_audited(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "s3cret")
    from app.config import get_settings

    get_settings.cache_clear()
    r = await client.post("/channels/whatsapp/webhook", content=json.dumps(payload()).encode(),
                          headers={"x-hub-signature-256": "sha256=deadbeef"})
    assert r.status_code == 401
    async with session_scope() as db:
        actions = [a.action for a in (await db.scalars(select(AuditEntry))).all()]
    assert "webhook.rejected_signature" in actions


async def test_simulated_text_creates_one_run_and_duplicates_are_ignored(client):
    r = await client.post(SIM, json={"text": "We need 100 brass lamps CIF Dubai"})
    data = r.json()
    assert data["status"] == "created"
    from app.api.channels import process_payload
    from app.config import get_settings

    raw = json.dumps(payload(msg_id="wamid.DUP")).encode()
    secret = get_settings().simulator_secret
    first = await process_payload(raw, sign(raw, secret), secret, source="simulator", wait=True,
                                  run_in_background=False)
    again = await process_payload(raw, sign(raw, secret), secret, source="simulator", wait=True,
                                  run_in_background=False)
    assert first[0]["status"] == "created" and again[0] == {"status": "duplicate", "run_id": first[0]["run_id"]}
    async with session_scope() as db:
        run = await db.get(Run, first[0]["run_id"])
        contact = await db.get(Contact, run.contact_key)
    assert run.channel == "whatsapp" and contact.address == "971501234567"
    assert "971501234567" not in run.raw_redacted                                     # never in the run


async def test_synthetic_voice_note_becomes_a_quote(client):
    samples = (await client.get("/channels/whatsapp/voice-samples")).json()
    ar = next(s for s in samples if s["language"] == "ar")
    audio = await client.get(ar["audio_url"])
    assert audio.status_code == 200 and len(audio.content) > 10_000
    r = (await client.post(SIM, json={"voice_sample": ar["name"]})).json()
    assert r["status"] == "created"
    async with session_scope() as db:
        run = await db.get(Run, r["run_id"])
    assert run.status == "needs_approval" and len(run.state["quote"]["lines"]) == 2
    assert run.state["rfq"]["language"] == "ar"


async def test_real_voice_notes_never_go_to_a_free_tier_model(db_ready, monkeypatch):
    monkeypatch.setenv("LLM_PROFILE", "dev")                  # dev = free tiers
    from app.config import get_settings
    from app.llm.router import LLMRouter

    get_settings.cache_clear()
    with pytest.raises(LLMPolicyError):
        await LLMRouter().transcribe(TranscribeRequest(audio=b"x", data_class="real"))


async def test_fake_stt_only_knows_the_synthetic_notes(db_ready):
    from app.llm.router import LLMBackendError

    with pytest.raises(LLMBackendError):
        await get_router().transcribe(TranscribeRequest(audio=b"not a demo note"))


# ---------- outbound over WhatsApp -------------------------------------------------------------------


async def test_approved_reply_goes_to_whatsapp_and_window_is_enforced(client, monkeypatch):
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.OUT1"}]})

    fake = WhatsAppClient("T", "P", "v23.0", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(outbox, "whatsapp_client", lambda: fake)
    r = (await client.post(SIM, json={"text": "Need 50 pashmina shawls CIF Dubai"})).json()
    run_id = r["run_id"]
    approvals = [a for a in (await client.get("/approvals")).json() if a["run_id"] == run_id]
    assert sent and sent[0]["to"] == "971500000001"                                # the acknowledgement (L2)
    assert (await client.post(f"/approvals/{approvals[0]['id']}/approve")).status_code == 200
    assert len(sent) == 2
    # Close the window: a new held reply can no longer be approved.
    r2 = (await client.post(SIM, json={"text": "Need 20 table runners CIF Dubai"})).json()
    async with session_scope() as db:
        run = await db.get(Run, r2["run_id"])
        contact = await db.get(Contact, run.contact_key)
        contact.last_inbound_at = datetime.now(UTC) - timedelta(hours=30)
    held = next(a for a in (await client.get("/approvals")).json() if a["run_id"] == r2["run_id"])
    resp = await client.post(f"/approvals/{held['id']}/approve")
    assert resp.status_code == 409 and "24 h" in resp.json()["detail"]


# ---------- collections ----------------------------------------------------------------------------


def test_reminder_tone_and_bank_safety():
    inv = Invoice(id="INV-1", org_id="demo", buyer_name="Acme", language="en", amount_aed=1000.0,
                  issued_on=datetime.now(UTC), due_on=datetime.now(UTC) - timedelta(days=40))
    text = reminder_text(inv, 40)
    assert tone_for(3) == "gentle" and tone_for(20) == "firm" and tone_for(40) == "final"
    assert "never change bank details" in text and "IBAN" not in text.upper()


async def test_collections_queue_reminders_for_approval_only(db_ready):
    assert await seed_demo_invoices("demo") == 3
    created = await run_collections("demo")
    assert {c["invoice_id"] for c in created} == {"INV-2026-031", "INV-2026-034"}      # the third is not due yet
    assert all(c["effect"] == "require_approval" for c in created)
    assert next(c for c in created if c["invoice_id"] == "INV-2026-034")["risk"] == "high"   # 45 days, Arabic
    assert await run_collections("demo") == []                                       # not again within 7 days
    async with session_scope() as db:
        run_ids = [c["run_id"] for c in created]
        approvals = (await db.scalars(select(Approval).where(Approval.run_id.in_(run_ids)))).all()
    arabic = next(a for a in approvals if a.payload["language"] == "ar")
    assert "لا نغيّر بيانات الحساب البنكي" in arabic.payload["text"]


def test_spoken_arabic_quantities_are_parsed():
    from app.tools.rfq_rules import find_items

    items = find_items("نحتاج ثلاثمئة مصباح نحاسي ومئتي مفرش طاولة قطني، وألف صندوق خشبي")
    assert [(i.description, i.quantity) for i in items] == [("مصباح نحاسي", 300), ("مفرش طاولة قطني", 200),
                                                            ("صندوق خشبي", 1000)]
    assert find_items("نشرب الماء ونحتاج 50 شال")[0].quantity == 50          # no number word: unchanged
