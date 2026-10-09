# Synthetic evaluation data — datasheet (`synthetic-v1`)

Regenerate with `make data` (deterministic, seed 20261009; `MANIFEST.json` holds counts and SHA-256).
A test checks that the committed files are byte-identical to the generator's output.

| File | Rows | What | Split |
|---|---|---|---|
| `enquiries.jsonl` | 300 | Buyer enquiries: 150 English, 105 Arabic, 45 code-switched; easy / medium / hard; 10 hard negatives | 180 train / 60 dev / 60 test, stratified by language × difficulty |
| `adversarial.jsonl` | 30 | Hand-written attacks: instruction override, prompt/secret extraction, bank-detail change, payment pressure, approval bypass, hidden instructions in attachment text / file names / metadata; obfuscated, Arabic and code-switched variants | all `test` (never tuned on) |
| `docsets.jsonl` | 40 | Export document sets (invoice, packing list, CoO, shipping, export declaration); 20 clean, 20 with 1–2 planted mistakes covering 9 mistake types | 24 train / 8 dev / 8 test |

## How it was built and labelled

- **Enquiries** come from templates (`backend/eval/synth/enquiries.py`). Every label is known **by construction**:
  items and quantities, Incoterm, destination country, deadline (structured: date / end of month / within N days),
  language, and the personal data inserted (for redaction scoring). **No language model wrote or labelled any of it**,
  so evaluation is not biased towards the model under test.
- Hard cases mimic WhatsApp writing: lowercase, "1.2k", number words, Arabic-Indic digits (٥٠٠), "+" and "&" lists.
  Hard negatives contain legitimate bank/account/urgency wording that a guard must **not** flag.
- **Attacks** were written by hand (Claude Code, reviewed in this repo) with expected flags and the dangerous goal
  each one pursues. **Founder review pending:** add or edit cases you think a real attacker would send.
- **Document sets** are generated consistent, then mistakes are planted on purpose; the planted list is the gold label.
  HS codes are real 8-digit codes from the Dubai Customs tariff master, used as **consistent test fixtures, not
  classification advice**.

## Limits (state these honestly when reporting numbers)

- Synthetic text is cleaner and more regular than real buyer messages; real pilot data (anonymised) will be added in
  Phases 6–7 and reported separately.
- Product range and destinations are a demo catalogue (Jaipur handicrafts/textiles/gifting → UAE/GCC).
- The retrieval evaluation set (tariff/CEPA questions with gold passages) is **not** here: it must be built by hand
  from the official documents in Phase 5f.
- All names, companies, phone numbers, emails and account numbers are fictional.
