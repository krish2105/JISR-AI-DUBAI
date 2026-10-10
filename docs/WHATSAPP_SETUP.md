# Connecting the real WhatsApp test number (founder steps)

Jisr works with the **simulator** out of the box (same code path, signed payloads). To use a real WhatsApp number
you need a Meta developer account. Nothing here sends anything by itself: every reply still waits for your approval
(except the fixed-text acknowledgement, which you can switch off by setting `send_acknowledgement` to `L1` in
`backend/app/governance/autonomy.yaml`).

1. **Create the app.** developers.facebook.com → My Apps → Create app → type *Business* → add the **WhatsApp**
   product. Meta gives you a **test phone number** and lets you add up to 5 recipient numbers for testing.
2. **Copy into `.env`** (never commit it):
   - `WHATSAPP_PHONE_NUMBER_ID` (WhatsApp → API Setup)
   - `WHATSAPP_ACCESS_TOKEN` (a *system user* token with `whatsapp_business_messaging`; the temporary token
     expires after 24 h)
   - `WHATSAPP_APP_SECRET` (App settings → Basic → App secret): used to verify every webhook signature
   - `WHATSAPP_VERIFY_TOKEN`: any long random string you choose
   - `WHATSAPP_ENABLED=true`
3. **Expose the webhook** over HTTPS: the hosted API (Phase 10) or, locally, a tunnel such as
   `cloudflared tunnel --url http://localhost:8000`.
4. **Register the webhook** in Meta: callback URL `https://<your-host>/channels/whatsapp/webhook`, verify token =
   `WHATSAPP_VERIFY_TOKEN`; subscribe to the `messages` field. Meta calls `GET …/webhook` once; Jisr answers the
   challenge only if the token matches.
5. **Test**: send a text or a voice note from a recipient number. The run appears on `/demo` (open the run id
   from `/approvals`). Approve the reply and it is delivered to WhatsApp.

Rules Jisr enforces:
- Unsigned or wrongly signed webhooks are rejected (401) and logged in the audit chain.
- Each message is handled once (Meta retries deliveries).
- Free-form replies only within **24 h** of the buyer's last message (Meta's customer-service window); after that
  the approval is refused with a clear message (templates are a later step).
- **Voice notes from real buyers are real personal data**: the router refuses to send them to a free-tier
  speech-to-text model. Before the pilot, switch the `stt` role in `backend/app/llm/profiles.yaml` to a paid
  provider whose terms exclude training on your data, and set `free_tier: false` (DECISIONS C3).
- Phone numbers are stored only to reply; agents and models see a hashed contact id, never the number.
