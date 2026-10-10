# Pitch notes — finals (live demo ~100 s + trust moment ~30 s)

Rule for every sentence: if it is a number, it is in `docs/EVAL_REPORT.md` or `docs/CLAIMS_REGISTER.md`.

## Opening (15 s)
"My family exports handicrafts from Jaipur to Dubai. Every enquiry takes hours: price it in rupees and dirhams, find
the HS code and the CEPA origin rule, prepare the documents, answer in Arabic, and watch for fraud. Jisr is a team of
AI agents that does this in seconds, and a governance layer that makes sure nothing leaves without the owner."

## Live demo (100 s) — `/ar/demo`, 3D graph on
1. **Voice note** (Arabic): press "Send as voice note". Point at the timeline: the transcript appears, then the
   3D graph lights up agent by agent. (20 s)
2. **Quote**: INR/AED, Incoterm charges, live ECB rate with its date. "Incoterm not stated" is flagged, not guessed. (15 s)
3. **CEPA card**: brass diya lamps → 9405.50 non-electrical luminaires (it used to say vapour lamps; we fixed that
   with measurement), 5% duty, CTH + VA 40%, Annex 3B page 9, the evidence the exporter must hold, "up to AED X".
   "Every number here appears verbatim in the cited official passage — checked in code." (25 s)
4. **Document mismatch sample**: run it; open the 3D document pack: the red beam joins 4202 on the invoice and
   6305 on the certificate. "This is the mistake that costs the preference at customs." (20 s)
5. **Approve**: edit one word, approve; open `/audit`: the hash chain is verified. (20 s)

## Trust moment (30 s)
- Run **"Hostile: bank-detail change"**: the gate flashes red, P-BANK-001 blocks it, audit row written.
- Optional: `buyer_agent.py --malicious` — a hostile *agent* is rejected the same way.
- Open `/governance`: kill switch, autonomy levels, Agent Passports with their measured quality.
"Models can propose. Only plain rules decide what leaves."

## Close (15 s)
"0 of 30 attacks succeeded, 100% of answers grounded in cited sources, every number reproducible. Next: a shadow-mode
pilot with real enquiries, then the Dubai AI Seal."

## If something fails
- No network / API down: start with `make replay` (same demo from the recorded cassette, no network for models).
- Hosted link slow: switch to the local laptop (second laptop pre-warmed with `make demo`).
- 3D stutters: click **2D** (same information).

## Likely judge questions → where the answer is
Accuracy → EVAL_REPORT; governance → `/governance` + DECISIONS G1–G5; data → DATA_PROTECTION; cost →
`/health` budget + Impact Ledger; what is not done → SUBMISSION "Honest limits". Full list: VIVA_QA.md.
