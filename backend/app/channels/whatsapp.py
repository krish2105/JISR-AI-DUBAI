"""
whatsapp.py — WhatsApp Cloud API (Meta): verify webhooks, parse messages, fetch voice notes, send replies.

Why this file exists:
    Indian exporters and Gulf buyers live on WhatsApp. This module is the thin, testable boundary to Meta's Cloud API:
      * webhook verification (GET with hub.challenge) and payload SIGNATURE checks (X-Hub-Signature-256 =
        HMAC-SHA256 of the raw body with the app secret): an unsigned or wrongly signed request is rejected;
      * parsing text and audio (voice note) messages into a small, typed shape;
      * downloading voice-note media (two Graph API calls: media id -> short-lived URL -> bytes);
      * sending a text reply. Sending happens ONLY from app/channels/outbox.py, after governance allowed it.

    Meta's 24-hour customer-service window: a free-form reply is only allowed within 24 h of the buyer's last message;
    after that a pre-approved template is required. The outbox enforces this (see `within_service_window`).

Configuration (.env): WHATSAPP_ENABLED, WHATSAPP_VERIFY_TOKEN, WHATSAPP_APP_SECRET, WHATSAPP_ACCESS_TOKEN,
WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_API_VERSION. Without them the simulator path is used (same parsing, no network).
"""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

GRAPH = "https://graph.facebook.com"
SERVICE_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class InboundMessage:
    """One message from a buyer, as Jisr needs it."""

    message_id: str                  # Meta's id (wamid...), used for idempotency
    wa_id: str                       # the sender's WhatsApp id (a phone number): personal data, never sent to models
    timestamp: datetime
    kind: str                        # "text" | "audio" | other types are acknowledged and ignored
    text: str = ""
    media_id: str | None = None
    mime_type: str | None = None
    profile_name: str | None = None


def verify_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    """True when X-Hub-Signature-256 matches HMAC-SHA256(app_secret, raw body). Constant-time comparison."""
    if not signature_header or not app_secret or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))


def sign(raw_body: bytes, app_secret: str) -> str:
    """The signature header Meta would send (used by the simulator and tests)."""
    return "sha256=" + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()


def parse_webhook(payload: dict) -> list[InboundMessage]:
    """Messages in a webhook payload (status updates and other events are skipped)."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", [])}
            for m in value.get("messages", []):
                kind = m.get("type", "")
                ts = datetime.fromtimestamp(int(m.get("timestamp", "0")), tz=UTC)
                audio = m.get("audio") or {}
                out.append(InboundMessage(
                    message_id=m.get("id", ""), wa_id=m.get("from", ""), timestamp=ts, kind=kind,
                    text=(m.get("text") or {}).get("body", ""), media_id=audio.get("id"),
                    mime_type=audio.get("mime_type"), profile_name=names.get(m.get("from"))))
    return out


def within_service_window(last_inbound: datetime | None, now: datetime | None = None) -> bool:
    """Meta allows free-form replies only within 24 hours of the buyer's last message."""
    if last_inbound is None:
        return False
    return (now or datetime.now(UTC)) - last_inbound <= SERVICE_WINDOW


class WhatsAppClient:
    """Minimal Graph API client (media download + text send)."""

    def __init__(self, access_token: str, phone_number_id: str, api_version: str,
                 http: httpx.AsyncClient | None = None) -> None:
        self.token, self.phone_number_id, self.version = access_token, phone_number_id, api_version
        self.http = http or httpx.AsyncClient(timeout=30)

    @property
    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    async def fetch_media(self, media_id: str) -> tuple[bytes, str]:
        """Voice-note bytes and MIME type (step 1: metadata with a short-lived URL; step 2: the bytes)."""
        meta = await self.http.get(f"{GRAPH}/{self.version}/{media_id}", headers=self._auth)
        meta.raise_for_status()
        info = meta.json()
        media = await self.http.get(info["url"], headers=self._auth)
        media.raise_for_status()
        return media.content, info.get("mime_type", "audio/ogg")

    async def send_text(self, to: str, body: str) -> str:
        """Send a text message; returns Meta's message id."""
        r = await self.http.post(f"{GRAPH}/{self.version}/{self.phone_number_id}/messages", headers=self._auth,
                                 json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
                                       "type": "text", "text": {"preview_url": False, "body": body[:4096]}})
        r.raise_for_status()
        return (r.json().get("messages") or [{}])[0].get("id", "")
