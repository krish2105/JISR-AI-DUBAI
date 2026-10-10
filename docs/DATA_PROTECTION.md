# Data protection in Jisr

Plain-language summary for exporters, buyers, judges and auditors. Every statement points to the code that enforces
it. Jisr is designed with the UAE Personal Data Protection Law (Federal Decree-Law 45/2021) and India's Digital
Personal Data Protection Act 2023 in mind; this page is not legal advice, and the pilot needs a review by counsel.

## What Jisr stores

| Data | Why | Where / how long |
|---|---|---|
| The enquiry **with personal data masked** (emails, phones, IBANs, Emirates ID, tax numbers, cards) | to run the agents and show the timeline | `runs.raw_redacted`; the unmasked message is never stored (`app/runs/service.py`) |
| The buyer's WhatsApp number | only to reply on WhatsApp | `contacts.address`; runs and models only see a hashed `contact_key` (`app/channels/inbound.py`) |
| Buyer memory: counts, last Incoterm, languages, last quote total, high-risk signal names | to help the owner (returning buyer, missing Incoterm) | `buyer_memory`; facts only, no message text (`app/agents/memory.py`) |
| Quotes, approvals, audit entries | the business record and accountability | org-scoped tables; the audit chain is hash-linked and verifiable (`/audit/verify`) |
| Voice notes | transcribed, then discarded | the audio is not stored; only its SHA-256 is logged |

## What models see

- Only masked text. A last-line tripwire in the router refuses any request that still contains an email, IBAN, Emirates
  ID, tax number or card number (`app/llm/router.py`, tested).
- **Free-tier models only ever receive synthetic data** (enforced in the router; real data and real voice notes are
  refused there). Real data goes only to paid providers whose terms exclude training on it (Claude via the official
  Anthropic API in the `prod` profile; speech-to-text needs the same before the pilot).
- The model call log stores metadata (role, model, tokens, latency, a hash of the prompt), never the text.

## What leaves Jisr

Nothing leaves without a human, except a fixed-text acknowledgement ("we received your enquiry") on WhatsApp/email when
every policy allows it. Quotes, documents and reminders wait in the approval inbox; bank-detail and payment actions are
never performed. A kill switch stops everything. All of it is recorded in the audit chain (`app/governance/`).

## Who can see what

Every table carries the organisation id and every query filters by it; another organisation's run returns 404
(tested). The public demo uses a separate demo organisation with synthetic data only.

## Third parties

| Service | Purpose | Data |
|---|---|---|
| Anthropic (Claude) | extraction and drafting in `prod` | masked text |
| Meta WhatsApp Cloud API | receiving / sending WhatsApp messages | the messages themselves (the channel) |
| Frankfurter (ECB rates) | exchange rates | none (public rates) |
| Neon / Fly.io / Vercel | hosting | the stored data above |

## Rights and retention (pilot)

Before the pilot: retention period agreed with the exporter (proposal: runs 12 months, contacts until the buyer
relationship ends), a deletion procedure per buyer (contact + memory + masked runs), and the exporter's privacy notice
to buyers. These are founder tasks, listed in `docs/PROGRESS.md`.
