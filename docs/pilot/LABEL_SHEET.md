# Label sheet: `data/pilot_raw/enquiries.csv`

One row per past enquiry. Copy the message text exactly as received (WhatsApp export or email body). The prepare
script removes emails, phone numbers, IBANs, IDs and names after honorifics before anything else reads it, and
refuses to write a row if a high-risk identifier survives.

| Column | Example | Notes |
|---|---|---|
| `id` | `001` | unique |
| `received_at` | `2026-09-02` | date |
| `channel` | `whatsapp` | whatsapp / email / form |
| `language` | `en` | en / ar / mixed |
| `text` | the message | as received |
| `owner_items` | `brass diya lamps:500\|cotton table runners:200` | what was really asked: product:quantity, separated by `\|` |
| `owner_incoterm` | `CIF` | if the buyer named one |
| `owner_quote_total_aed` | `14800` | what you actually quoted (blank if you did not quote) |
| `owner_minutes` | `40` | how long it took you by hand: reading, pricing, duty lookup, writing the reply |

Tip: label 10 first, run `make pilot`, look at the failures, then label the rest. Do not change labels after seeing
Jisr's answer for `test` rows.
