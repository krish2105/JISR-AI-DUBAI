# Hand-labelled gold sets

## hs_products.jsonl (seller phrase -> HS heading)

80 descriptions of 45 goods commonly exported from India to the UAE, written the way a seller would
(45 English, 35 Arabic). Each row has the accepted 4-digit HS 2022 heading(s); the first is the primary.
Goods that are genuinely ambiguous (a brass oil lamp: 9405 lamp or 7419 copper article) accept both, with a note.

- **Labelled by:** Claude Code (Opus 5.5) from the WCO HS 2022 heading texts, 2026-10-09.
  **Advisor review pending.** Until then these labels are a second opinion, not ground truth; the duty agent always
  shows top-3 headings and "needs human check".
- **Split:** by product (both languages of a product share one split), stable SHA-1 of the product id:
  dev 27 rows / test 53 rows. Only dev is looked at when changing the classifier; test is reported.
- **Bias note:** the same author wrote the search glossary (`backend/app/rag/trade_terms.py`), written before
  this set was evaluated. The eval reports products the glossary covers and products it does not, separately.
