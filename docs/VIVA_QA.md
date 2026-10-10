# Viva Q&A (45 questions)

Short answers with the evidence to point at. Numbers: `docs/EVAL_REPORT.md` (synthetic data unless stated).

## Product and business
1. **Who is the customer?** Indian SME exporters (handicrafts, home textiles) selling to UAE buyers over WhatsApp; first user: my family's Jaipur business.
2. **What job does Jisr do?** Turns an enquiry (text, voice, or a buyer's agent) into a priced INR/AED quote, a cited CEPA duty analysis, checked draft documents, buyer signals and a bilingual reply, waiting for approval.
3. **Why now?** India–UAE trade above USD 100 bn a year (CLAIMS 1) and CEPA in force since 2022 (CLAIMS 3); buyers expect WhatsApp speed.
4. **What is the measurable value?** Time per quote, errors caught before shipping, preference preserved. The Impact Ledger measures runs; the time-saved figure is a labelled assumption until the pilot.
5. **How do you make money?** Per-seat subscription for exporters; later per-shipment document checks. Not validated yet; the pilot comes first.
6. **Competition?** Generic chatbots draft text; ERPs store data; customs brokers do documents. Nobody combines a governed agent, cited CEPA rules and Arabic/English WhatsApp for SMEs.
7. **Biggest risk?** Wrong HS or origin advice. Mitigations: citations, top-3 candidates, "needs human check", no automatic sending.

## Agents and architecture
8. **Why multiple agents?** Separate responsibilities (quote, duty, docs, trust, outreach) with separate tools and passports; each is testable and limited.
9. **Is the supervisor an LLM?** No, deterministic by design (DECISIONS A1): predictable routing; re-plans (clarify, skip CEPA outside the UAE) are visible events.
10. **Where are LLMs used?** Extraction (grounded by rules), reply drafting, injection classification. Never for policy decisions.
11. **What if the model hallucinates a quantity?** The rules parser reconciles: quantities not in the text are dropped and reported (Phase 4).
12. **How fast?** p95 1.9 s per enquiry on the offline model (eval); on Claude the target is under 2 minutes end to end.
13. **What happens if the model provider is down?** Extraction falls back to the rules parser; a daily budget cap or outage degrades to the deterministic model, labelled; finals fallback is `make replay`.
14. **Memory?** Buyer memory keeps facts (counts, last Incoterm, languages), never text; it fills a missing Incoterm and flags it for review.

## RAG and correctness
15. **Where do CEPA facts come from?** The official Final Agreement (UAE MoET), the Dubai Customs tariff master, DGFT/ICEGATE guides; SHA-256 recorded; the Abu Dhabi pre-final copy is excluded.
16. **How do you stop invented facts?** Claims must cite retrieved passages, and every number must appear verbatim in a cited passage, checked in code: grounded 100%, numbers 100% on 92 test questions.
17. **What is the origin rule for lamps?** Chapter 94: CTH + VA 40% (Annex 3B page 9); VA is FOB-based, 5 points lower on Ex-Works (Rule 1).
18. **Why "up to" savings?** The UAE preferential schedule (Annex 2B) is not available officially; we show the MFN duty a 0% rate would remove and flag the rate.
19. **HS accuracy?** Seller phrases: top-1 86.8%, top-3 96.2% (53 test phrases); uncovered goods 73%. Labels need an advisor's review.
20. **Retrieval pipeline?** Exact codes + BM25 (EN/AR) + e5 vectors + RRF + bge reranker + agentic corrective loop; ablation recall@5 0.600 → 0.825.
21. **Weakest point?** Arabic questions over the English treaty text; "no tariff line fits" detection. Both published.
22. **How did you avoid overfitting?** Dev/test splits; thresholds calibrated on dev only; first-shot test numbers recorded when a bug was fixed (DECISIONS K13).

## Governance and safety
23. **What can Jisr do alone?** Only a fixed-text acknowledgement, when every policy allows it (autonomy L2).
24. **What can it never do?** Change bank details, change payment instructions, mark invoices paid (NEVER).
25. **Prompt injection?** Normalisation + rules + classifier guard; policy engine blocks dangerous actions regardless: 0/30 attacks succeeded.
26. **Kill switch?** Per organisation, audited, re-checked in the outbox; approvals return 409 while it is on.
27. **Audit?** Hash-chained per organisation; `/audit/verify` recomputes it and finds the first tampered row.
28. **Agent Passports?** Purpose, data, models, actions, enforced tool allow-list, live metrics, 24 h activity (`/governance`).
29. **How are policies tested?** Every rule has trigger and non-trigger tests; 20 owner-readable governance scenarios; 50 trajectories × 3 runs.
30. **Buyer trust: isn't this profiling?** Signals with evidence, never scores or verdicts; positive signals shown; sanctions wording is "possible match, for review".

## Data protection
31. **What do models see?** Masked text only; a router tripwire refuses remaining identifiers.
32. **Free-tier models?** Synthetic data only, enforced in code; real data only to paid no-training providers.
33. **Voice notes?** Transcribed, not stored; real audio refused on free-tier STT.
34. **Phone numbers?** Stored only to reply; agents and models see a hashed contact id.
35. **Laws?** Designed with the UAE PDPL and India's DPDP Act in mind; counsel review before the pilot (DATA_PROTECTION.md).

## Interoperability and channels
36. **WhatsApp?** Cloud API with signature verification, idempotency, 24 h service window; simulator uses the same path.
37. **MCP?** Six read/analyse tools for assistants like Claude Desktop; no approve or send tools; audited.
38. **A2A?** Buyer agents request quotes; the task completes only after approval; a hostile agent is rejected.
39. **Arabic?** EN/AR extraction, Arabic analyser, RTL dashboard, Arabic drafts and spoken Arabic quantities.

## Evaluation and engineering
40. **How do I know the numbers are real?** Every number comes from `backend/eval/results` with commit, dataset version and split; a CI gate fails on regressions.
41. **Synthetic data bias?** Stated on every suite; hand-written held-out enquiries and adversarial sets are test-only; pilot data next.
42. **Biggest bug you found?** Heading claims were dropped by grounding (0.367 → 1.000 after fix, diagnosed on dev); third-party payment risk mismatch between signal and policy (trajectory suite).
43. **Tests?** 286 automated tests; real-index tests pin treaty facts.
44. **Deployment?** Fly (API) + Neon (Postgres) + Vercel (dashboard); rate limit and token budget for the public demo (DEPLOY.md).
45. **What would you do with the prize?** Run the pilot properly (advisor review, paid no-training STT, Annex 2B), get the Dubai AI Seal, and onboard the first ten exporters.
