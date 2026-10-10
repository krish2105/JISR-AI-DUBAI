# Scorecard — honest assessment (2026-10-10, after Phase 12)

Scored as a **real deployed MVP and a real SaaS**, not on intentions. Re-score after each plan phase
(`docs/PLAN_95.md`) and append a dated row to the history table at the bottom.

## 1. Championship judge (Best Business AI Agent) — 74 / 100

| Criterion | Score | Why |
|---|---|---|
| Problem and business relevance | 13/15 | Real India→UAE pain, founder with a family export business, UAE angle |
| Agentic depth and innovation | 14/15 | Multi-agent, grounded CEPA RAG, voice, MCP, A2A, memory, re-planning |
| Trust, safety, governance | 15/15 | Deterministic policies, graded autonomy, kill switch, passports, audit chain, 0/30 attacks |
| Evidence of quality | 10/15 | Excellent eval discipline, but synthetic data and the offline model only |
| Real-world impact | 4/15 | No pilot, no user, time saved is an assumption, savings only "up to" (no Annex 2B) |
| Demo and UX | 11/15 | RTL, themes, four 3D views; not hosted yet, Claude never answered live |
| Pitch readiness | 7/10 | Docs done; video and deck not yet |

## 2. CTO (deployed MVP) — 55 / 100

| Area | Score | Gap |
|---|---|---|
| Code quality and tests | 9/10 | 286 tests, lint, CI gate |
| Quality evaluation | 9/10 | Gates, baselines, ablations, honest reporting |
| **Security and auth** | **2/15** | **No authentication.** Org from an optional `X-Org-Id` header; on a public link anyone can approve, toggle the kill switch, read approvals |
| Real model integration | 3/10 | Claude path never run: extraction, Arabic drafting, latency and cost unknown |
| Deployment and operations | 4/10 | Not live; no error tracking, alerting, uptime |
| Data layer | 5/10 | Additive auto-upgrade, no Alembic migrations, no backup policy |
| Scalability | 4/10 | A2A tasks, rate limiter, token budget in process memory; CPU models on one shared machine |
| Channels | 6/10 | WhatsApp/voice tested against mocks only |
| Frontend | 9/10 | Polished, accessible, bilingual, fallbacks |
| Cost control | 4/10 | Budget cap exists; real cost per quote unknown |

## 3. CEO (real SaaS business) — 32 / 100

| Area | Score | Gap |
|---|---|---|
| Market and positioning | 8/10 | Clear wedge: SME exporters, WhatsApp, CEPA |
| Product–market fit evidence | 2/20 | No pilot, no logged interviews, no LOIs |
| Self-serve SaaS basics | 3/20 | No sign-up, onboarding, settings, billing; catalogue/costs/margins live in a YAML file |
| Business model | 3/15 | Pricing and unit economics unvalidated |
| Traction | 0/15 | No users, no revenue |
| Moat | 9/10 | Governance + cited CEPA knowledge |
| Team and execution | 7/10 | Fast execution; solo-founder risk |

## Everything missing (the gap list the plan closes)

**Blockers before any real user**
1. Authentication and multi-tenant isolation from a verified identity (not a header).
2. RBAC: who may approve what, who may touch governance, who may only view.
3. Hosted demo lock: judges see everything, cannot approve, toggle the kill switch or change settings.

**Proof of value**
4. Real Claude runs: extraction F1, Arabic draft quality, latency and cost per quote.
5. Shadow-mode pilot with real (anonymised) enquiries; baseline vs Jisr; testimonial.
6. Official CEPA Annex 2B → real "you save AED X" instead of "up to".
7. Advisor review of HS labels and a sample of the retrieval gold set.
8. Real WhatsApp test number and a real voice note in the demo.

**SaaS product**
9. Onboarding wizard (business, catalogue, costs, margins, logistics, policies) stored in the database.
10. Settings screens (catalogue CRUD with CSV import, pricing rules, autonomy and policy toggles within safe bounds).
11. Team management: invite, roles, remove, transfer ownership.
12. Billing and plans; usage metering (quotes/month).
13. Outputs a customer can use: PDF quote, proforma invoice, packing list, CoO application prefill; email channel.
14. Document upload: check the exporter's own invoice/packing list PDFs (extraction + consistency check).
15. Notifications (email/WhatsApp to the owner when something needs approval); mobile-friendly approval (PWA).
16. Data rights: export, retention, deletion per buyer; audit export.

**Engineering**
17. Alembic migrations, Neon backups and restore drill.
18. Sentry, structured logs, uptime checks, dashboards (latency, errors, cost).
19. Redis (or Postgres) for rate limits, budget counters and the A2A task store (multi-instance safe).
20. Security headers (CSP, HSTS), dependency and secret scanning in CI, threat model, pen-test checklist.
21. Load test (concurrent runs), model warm-up, reranker cost on shared CPU.
22. Backend strings localised (signal explanations and findings are English-only).

**Pitch**
23. Video (2–3 min, captions), deck, rehearsed demo with the replay fallback, organiser confirmation in writing.
24. Dubai licence and Dubai AI Seal application.

## Score history

| Date | Judge | CTO | CEO | Note |
|---|---|---|---|---|
| 2026-10-10 | 74 | 55 | 32 | After Phase 12, not yet deployed |
