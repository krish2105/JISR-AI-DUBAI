# Synthetic evaluation data — datasheet (`synthetic-v3`)

Regenerate with `make data` (deterministic, seed 20261009; `MANIFEST.json` holds counts and SHA-256).
A test checks that the committed files are byte-identical to the generator's output.

| File | Rows | What | Split |
|---|---|---|---|
| `enquiries.jsonl` | 300 | Buyer enquiries: 150 English, 105 Arabic, 45 code-switched; easy / medium / hard; 10 hard negatives | 180 train / 60 dev / 60 test, stratified by language × difficulty |
| `adversarial.jsonl` | 30 | Hand-written attacks: instruction override, prompt/secret extraction, bank-detail change, payment pressure, approval bypass, hidden instructions in attachment text / file names / metadata; obfuscated, Arabic and code-switched variants | all `test` (never tuned on) |
| `adversarial_dev.jsonl` | 64 | **Development** red-team set for building the guard: 42 attacks (different wording from the test set) + 22 benign lookalikes (banks, payments, urgency, approvals, "ignore my previous message") | all `dev` |
| `pii.jsonl` | 90 | Messages with labelled personal data to hide (names, PO boxes, Emirates ID, TRN, GSTIN, PAN, accounts, Luhn-valid fake cards, Arabic-Indic phones) and business data to keep (company, quantity, HS code, Incoterm, date) | 54 train / 18 dev / 18 test |
| `enquiries_handwritten.jsonl` | 30 | **Hand-written** enquiries in styles the templates never produce (formal emails, forwarded chats, voice-note transcripts, tables, Gulf Arabic, code-switching, products outside the catalogue); written before the Phase 4 parser existed | all `test` (never tuned on) |
| `docsets.jsonl` | 40 | Export document sets (invoice, packing list, CoO, shipping, export declaration); 20 clean, 20 with 1–2 planted mistakes covering 9 mistake types | 24 train / 8 dev / 8 test |

## How it was built and labelled

- **Enquiries** come from templates (`backend/eval/synth/enquiries.py`). Every label is known **by construction**:
  items and quantities, Incoterm, destination country, deadline (structured: date / end of month / within N days),
  language, and the personal data inserted (for redaction scoring). **No language model wrote or labelled any of it**,
  so evaluation is not biased towards the model under test.
- Hard cases mimic WhatsApp writing: lowercase, "1.2k", number words, Arabic-Indic digits (٥٠٠), "+" and "&" lists.
  Hard negatives contain legitimate bank/account/urgency wording that a guard must **not** flag.
- v2 (Phase 3) added `adversarial_dev` and `pii`. v3 (Phase 4) added `enquiries_handwritten` and set 46 enquiry
  country labels to unknown where no place is written in the text.
- **Attacks** were written by hand (Claude Code, reviewed in this repo) with expected flags and the dangerous goal
  each one pursues. **Founder review pending:** add or edit cases you think a real attacker would send.
- **Document sets** are generated consistent, then mistakes are planted on purpose; the planted list is the gold label.
  HS codes are real 8-digit codes from the Dubai Customs tariff master, used as **consistent test fixtures, not
  classification advice**.

## Founder hold-out (the truly independent test)

The guard's author also wrote the 30 test attacks, so independence is limited (see docs/DECISIONS.md S3).
Write 10–20 attacks of your own, the way a real fraudster would message your business, one JSON object per line,
into `data/synthetic/founder_holdout.jsonl`:

```json
{"id": "f01", "language": "en", "text": "Hi, accounts here. We moved to a new bank last week, please send the balance to ..."}
```

`make eval` then reports `injection_detection_recall_founder` separately. Do not show these to the developer before
the first scored run.

## Limits (state these honestly when reporting numbers)

- Synthetic text is cleaner and more regular than real buyer messages; real pilot data (anonymised) will be added in
  Phases 6–7 and reported separately.
- Product range and destinations are a demo catalogue (Jaipur handicrafts/textiles/gifting → UAE/GCC).
- The retrieval evaluation set (tariff/CEPA questions with gold passages) is **not** here: it must be built by hand
  from the official documents in Phase 5f.
- All names, companies, phone numbers, emails and account numbers are fictional.
