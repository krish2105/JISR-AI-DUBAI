# Plan to 95+ — from strong prototype to a real, deployed, secure SaaS

Starting point: `docs/SCORECARD.md` (2026-10-10): **Judge 74 · CTO 55 · CEO 32**.
Window: **10 Oct → 9 Dec 2026** (feature freeze 5 Dec). Same rules as `CLAUDE.md`: every number from eval results,
no tuning on test splits, deterministic governance, commit per phase, `make test` + `make eval` green.

## 0. Targets (honest)

| Perspective | Now | Target at submission | What it takes |
|---|---|---|---|
| Championship judge | 74 | **95+** | Live Claude demo on a hosted link, real pilot numbers, Annex 2B savings, RBAC + polished UX, video |
| CTO | 55 | **92+** | Auth + RBAC, migrations, observability, multi-instance-safe state, security scanning, load test |
| CEO | 32 | **75–80** by 9 Dec, **95** later | Pilot evidence + design partners + pricing + billing. A true 95 needs paying customers: realistic Q1 2027 |

## 1. Phase map (new phases 13–21)

| Phase | Weeks | Theme | Score gain (J/CTO/CEO) |
|---|---|---|---|
| 13 | W1 | Security foundation: authentication, **RBAC**, demo lock | +3 / +12 / +4 |
| 14 | W1–W2 | Deploy + real Claude + operations | +6 / +10 / +2 |
| 15 | W2–W3 | SaaS core: onboarding, settings, catalogue, team | +2 / +3 / +10 |
| 16 | W3–W5 | **UI/UX overhaul** | +5 / +2 / +4 |
| 17 | W4–W5 | Outputs and channels: PDFs, email, document upload, notifications, PWA | +4 / +2 / +5 |
| 18 | W1–W8 (parallel) | **Pilot and proof**: shadow mode, Claude evals, Annex 2B, advisor review | +10 / +3 / +12 |
| 19 | W6–W7 | Business: pricing, billing (test mode), metering, design partners | +2 / 0 / +12 |
| 20 | W6–W8 | Hardening: migrations, Redis, security scanning, load test, data rights, i18n | +1 / +10 / +2 |
| 21 | W8–W9 | Submission v2: video, deck, rehearsal, re-score, freeze | +4 / 0 / +1 |

Week numbering: W1 = 13–19 Oct · W2 = 20–26 Oct · W3 = 27 Oct–2 Nov · W4 = 3–9 Nov · W5 = 10–16 Nov ·
W6 = 17–23 Nov · W7 = 24–30 Nov · W8 = 1–5 Dec (freeze) · W9 = 6–9 Dec (submit).

---

## Phase 13 — Security foundation: authentication, RBAC, demo lock (W1)

### 13a Authentication
- **Auth.js (NextAuth v5) in the dashboard** with email magic links + Google sign-in; the backend verifies a signed
  JWT (HS256 shared secret or JWKS) on every request. Alternative if faster: Clerk (hosted UI, organisations built in).
  Decision recorded in DECISIONS (S9).
- Backend: `app/api/deps.py` replaces `org_id_header` with `current_principal()` → `Principal(user_id, org_id, role)`
  read from the verified token. **The `X-Org-Id` header is removed** (kept only behind `APP_ENV=test`).
- New tables: `users`, `organisations`, `memberships(user_id, org_id, role, status)`, `invitations`, `api_keys`
  (hashed, for MCP/A2A machine access, scoped).
- Sessions: 12 h access token, refresh; sign-out everywhere; login and failed-login events in the audit chain.

### 13b RBAC (role-based access control)

Roles (per organisation; a user can hold different roles in different organisations):

| Role | Who | Purpose |
|---|---|---|
| **Owner** | the exporter / founder | everything, incl. billing, ownership transfer, high-risk approvals |
| **Admin** | trusted manager | team, settings, policies within bounds; no billing, no ownership transfer |
| **Approver** | sales lead | approve/edit/reject low and medium risk actions |
| **Operator** | sales / back office | run enquiries, edit drafts, prepare documents; cannot approve |
| **Accountant** | finance | collections, invoices, payment status *recording* (never automatic); read quotes |
| **Auditor** | advisor / compliance | read-only everything incl. audit log export; cannot act |
| **Viewer** | demo judge / guest | read-only demo; cannot approve, change settings or toggle the kill switch |
| **Machine: mcp / a2a** | API keys | exactly the tools in their passport (already enforced), scoped to one organisation |

Permission matrix (✔ allowed · H = high-risk only for Owner · — denied):

| Permission | Owner | Admin | Approver | Operator | Accountant | Auditor | Viewer |
|---|---|---|---|---|---|---|---|
| `runs.create` (enquiry, voice, simulate) | ✔ | ✔ | ✔ | ✔ | — | — | demo only |
| `runs.read` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `drafts.edit` | ✔ | ✔ | ✔ | ✔ | — | — | — |
| `approvals.decide` low/medium | ✔ | ✔ | ✔ | — | collections only | — | — |
| `approvals.decide` **high risk** | ✔ | — | — | — | — | — | — |
| `governance.kill_switch` engage | ✔ | ✔ | ✔ | ✔ | ✔ | — | — |
| `governance.kill_switch` release | ✔ | ✔ | — | — | — | — | — |
| `governance.policies.edit` (within safe bounds) | ✔ | ✔ | — | — | — | — | — |
| `settings.business` (catalogue, costs, margins) | ✔ | ✔ | — | — | — | — | — |
| `team.manage` (invite, role, remove) | ✔ | ✔ (not Owner) | — | — | — | — | — |
| `billing.manage` | ✔ | — | — | — | — | — | — |
| `collections.run` / `invoices.manage` | ✔ | ✔ | — | — | ✔ | — | — |
| `audit.read` / `audit.export` | ✔ | ✔ | read | read | read | ✔ | read (demo) |
| `api_keys.manage` (MCP, A2A) | ✔ | ✔ | — | — | — | — | — |

Design rules:
- **Anyone may engage** the kill switch (safety first); only Owner/Admin may release it.
- **Separation of duties**: a user cannot approve an action they drafted when the action is high risk (four-eyes);
  for a solo exporter the Owner can override with a written reason, audited.
- **Policies decide the risk, RBAC decides who**: the policy engine's `Decision.risk` maps to the minimum role
  (`low/medium → Approver`, `high → Owner`). Implemented as a new `approver_role` field on `Approval`, checked in
  `runs/service.decide()`. Policies stay deterministic YAML; roles live in `app/governance/rbac.yaml`.
- Policy edits are bounded: NEVER actions (bank, payment) cannot be relaxed from the UI; autonomy can only be raised
  for `send_acknowledgement`. Every change is audited with before/after.
- Every audit entry carries `actor = user:<id>` with role; passports show which roles may trigger each agent action.

Implementation:
- `app/governance/rbac.py`: `require(permission)` FastAPI dependency; matrix loaded from `rbac.yaml`.
- Applied to every route (approvals, governance, collections, settings, team, billing, api keys, runs).
- Frontend: `useCan(permission)` hook hides/disables controls and explains why ("Only the owner can approve high-risk
  actions"); server is the source of truth.

Tests (acceptance): a parametrised matrix test (role × permission × expected status) over every route; four-eyes
test; Viewer cannot approve/toggle/change (403); cross-organisation access returns 404; API keys limited to their
passport; audit actor recorded. New eval suite `rbac` (scenario table like governance) with a hard gate of 1.00.

### 13c Hosted demo lock
- `DEMO_MODE=true`: anonymous visitors get a **Viewer** session on a per-visitor sandbox organisation (cloned demo
  data, auto-deleted after 24 h), so a judge can run enquiries and approve **inside their own sandbox** without
  affecting anyone else; the shared demo org is read-only. Real WhatsApp sending is impossible in demo mode.

---

## Phase 14 — Deploy, real Claude, operations (W1–W2)

1. Deploy Fly (API) + Neon (DB) + Vercel (dashboard) per `docs/DEPLOY.md` (founder accounts; commands prepared).
2. `ANTHROPIC_API_KEY`; switch `LLM_PROFILE=prod`; `make record` with Claude; replay test still green.
3. **Claude evaluation run** (new results files, profile `prod`): extraction F1 on the 30 hand-written enquiries,
   e2e on a 60-enquiry sample, trajectory suite with 3 repeats (now measuring real variance), latency p50/p95,
   **cost per quote** (tokens × published prices, recorded with the date).
4. **LLM-as-judge for drafts** (different model family from the drafter, pinned prompt, 20% human-checked):
   tone, correctness of figures (code-checked), Arabic fluency; judge-vs-human agreement reported.
5. Observability: Sentry (API + dashboard), structured JSON logs, Better Stack/UptimeRobot on `/health`,
   a `/admin/metrics` page (runs/day, p95, error rate, tokens and cost/day, budget fallback events).
6. Warm-up on boot (load models before accepting traffic); readiness vs liveness checks.

Acceptance: hosted link works on a fresh browser; Claude numbers published in EVAL_REPORT (good or bad); cost per
quote in CLAIMS; Sentry receives a test error; uptime monitor green for 7 days.

---

## Phase 15 — SaaS core (W2–W3)

1. **Business profile in the database** (replaces `business_profile.yaml`; YAML becomes the demo seed).
2. **Onboarding wizard** (≤ 5 minutes to first quote): business name and country → products (CSV import or quick add
   with HS suggestion from the tariff explorer) → costs and margin floor → logistics defaults (port, freight per CBM,
   insurance) → channels (WhatsApp optional) → "send a test enquiry" → first quote. Progress saved per step.
3. **Settings**: catalogue CRUD (search, bulk edit, CSV import/export, HS hint with "confirm with tariff"), pricing
   rules (margins, discount tiers, validity), logistics, autonomy toggles (bounded), notification preferences,
   languages, API keys (MCP/A2A), data retention.
4. **Team**: invite by email with role, pending invites, change role, remove, transfer ownership (Owner only).
5. Organisation switcher for users in several organisations (e.g. an advisor).

Acceptance: a new exporter signs up, completes onboarding and gets a correct quote without touching code; tests
for each settings endpoint (validation, RBAC, audit of changes).

---

## Phase 16 — UI/UX overhaul (W3–W5)

Principles: owner-first (a busy exporter on a phone), explain every decision ("why" is one tap away), calm by
default, bilingual parity, accessible (WCAG 2.2 AA), fast (Lighthouse ≥ 90 performance, ≥ 95 accessibility on
core pages).

1. **Information architecture**: left sidebar (Inbox, Runs, Buyers, Documents, Collections, Tariff, Impact,
   Governance, Settings) with role-aware items; the top bar keeps search, language, theme, organisation, user menu.
2. **Approval inbox v2** (the money screen): priority by risk and age; side-by-side draft and evidence; inline edit
   with a diff of what changed; keyboard shortcuts (A approve, E edit, R reject, J/K next); bulk approve for
   low-risk acknowledgements; "why this needs you" with the policy rule in plain language; mobile swipe actions.
3. **Run detail page** `/runs/[id]`: one shareable page per enquiry: summary card, quote, CEPA, documents,
   trust, timeline, audit trail of that run; print/PDF.
4. **Buyers page**: buyer memory, history, signals over time, last quotes (RBAC: sales roles).
5. **Documents page**: draft packs and uploaded documents with the 3D/2D check, fix suggestions, re-check.
6. **Home dashboard** for the owner: "needs you now", today's numbers (from the Impact Ledger), what the agent did
   on its own, alerts (kill switch, budget fallback, errors).
7. **Guided demo tour** for judges (5 steps, skippable, remembers progress) and empty states that teach.
8. **Explainability everywhere**: hover/tap on any number shows its source (tariff line, Annex 3B page, FX date,
   eval file); confidence shown as words + bars, never only colour.
9. **Arabic parity**: backend explanations localised (signals, findings, policy reasons, notes); Arabic numerals
   option; Arabic typography review (line height, Plex Arabic weights).
10. **Mobile/PWA**: installable, push notifications for "approval needed", offline read of the inbox.
11. **Design system doc**: tokens, components, states, motion rules, 3D rules (`frontend/DESIGN.md`), Storybook or a
    `/design` page with every component in light/dark and EN/AR.
12. **Quality gates**: Playwright e2e (sign-in, onboarding, approve, RBAC denial, RTL, reduced motion, dark),
    visual regression screenshots for 6 key screens, axe accessibility check in CI, Lighthouse CI budgets.

Acceptance: usability test with 3 exporters (task: first quote; approve an edit; find why something was blocked):
all complete without help in < 10 min; SUS score recorded; findings fixed.

---

## Phase 17 — Outputs and channels (W4–W5)

1. **PDF outputs** (bilingual, branded per organisation): quotation, proforma invoice, packing list, CEPA origin
   evidence checklist; generated from the approved data only; checksum in the audit.
2. **Email channel** (send via the outbox after approval; inbound parsing via a mailbox webhook).
3. **Document upload**: exporter uploads invoice/packing list/CoO PDFs or photos → extraction (Claude vision,
   grounded: values must be found on the page) → the existing consistency checker → findings with page highlights.
   New eval set: 30 real-looking document images (synthetic, rendered) + hand-labelled fields.
4. **Notifications**: approval needed / kill switch / budget fallback to the owner by email, WhatsApp or push
   (preferences per user); digest at 18:00.
5. **WhatsApp templates** for messages outside the 24 h window (quote follow-up, reminder) — submitted to Meta.

---

## Phase 18 — Pilot and proof (W1–W8, runs in parallel)

| Week | Activity | Output |
|---|---|---|
| W1 | Baseline interview: minutes per quote, error types, follow-up rate (owner + 1 staff) | `docs/pilot/BASELINE.md` |
| W1–W2 | Collect 30–50 past enquiries; anonymise with the Jisr redactor; owner labels the correct quote fields | `data/pilot/` (git-ignored) + label sheet |
| W2–W6 | **Shadow mode**: every new enquiry also goes through Jisr; the owner compares, never sends Jisr's output | pilot log, weekly numbers |
| W3 | Official **Annex 2B** obtained (MoET/DGFT/advisor) and ingested; savings become "AED X" with citation | DECISIONS, claims |
| W3–W4 | **Advisor review**: 50 HS labels + 30 retrieval gold items + CEPA rule mapping, with written sign-off | `docs/pilot/ADVISOR_REVIEW.md` |
| W4–W6 | Switch to **assisted mode** for low-risk replies (owner approves in Jisr) | real approvals, real sends |
| W6 | Pilot report: time per quote before/after, extraction accuracy on real data, errors caught, owner quote | `docs/pilot/PILOT_REPORT.md`, Impact Ledger with real numbers |
| W2–W7 | 5 interviews with other exporters / Dubai buyers; 3 design-partner letters of intent | `docs/pilot/INTERVIEWS.md`, LOIs |

Eval additions: `pilot` suite (real anonymised enquiries, owner labels) reported separately from synthetic sets;
never used for tuning beyond a declared dev part.

---

## Phase 19 — Business (W6–W7)

1. Pricing hypothesis from interviews (e.g. Starter per month for 1 seat + N quotes; Growth with WhatsApp + team +
   documents; per-shipment document check add-on); a pricing page.
2. **Stripe** in test mode: checkout, plans, usage metering (quotes/month), customer portal; plan limits enforced
   (RBAC + quotas); invoices. Live mode only after company registration.
3. Unit economics sheet from measured cost per quote (Phase 14) and hosting costs: gross margin per plan.
4. Go-to-market one-pager: channel (export councils, EPCH, Dubai Chamber), first 10 customers plan.
5. Legal: terms, privacy policy (from DATA_PROTECTION.md), DPA template for customers.

---

## Phase 20 — Hardening (W6–W8)

1. **Alembic** migrations (baseline from the current schema; CI checks upgrade/downgrade); Neon backups + a tested
   restore drill.
2. **Redis** (Upstash or Fly) for rate limits, token budget counters, A2A task store, SSE fan-out → safe with 2+
   machines; then run 2 machines.
3. Security: CSP/HSTS/frame-ancestors headers, CSRF on cookie auth, dependency scanning (pip-audit, npm audit) and
   secret scanning (gitleaks) in CI, threat model (`docs/THREAT_MODEL.md`), OWASP ASVS L1 checklist, rate limits per
   user and per API key.
4. **Load test** (k6/Locust): 20 concurrent enquiries, p95 under target, no errors; reranker CPU profile; consider a
   hosted reranker or caching for heavy pages.
5. **Data rights**: per-buyer export and deletion (contact, memory, runs masked text), retention job, audit export
   (CSV/JSON with chain proof).
6. Backend i18n for all user-facing explanations (EN/AR).

---

## Phase 21 — Submission v2 (W8–W9)

1. Re-run the full eval on `prod` and `fake`; update EVAL_REPORT, CLAIMS, SCORECARD (target scores recorded).
2. Video 2–3 min with captions (EN, Arabic subtitles): voice note → quote → CEPA → doc mismatch → approve → hostile
   blocked → pilot numbers.
3. Deck (10 slides): problem, user, demo, trust, proof (pilot + evals), business, roadmap, team.
4. SUBMISSION.md v2 with pilot numbers; VIVA_QA refresh; two full rehearsals with the replay fallback.
5. Organiser confirmation of deadline/eligibility in writing; Dubai licence and AI Seal application started.

---

## 2. Definition of done for "95+"

- Hosted link live ≥ 3 weeks, uptime ≥ 99.5%, Sentry clean, judges get a sandbox (Viewer) automatically.
- Auth + RBAC with a 100% passing permission-matrix suite; no route without a permission check.
- Claude numbers published: extraction F1 ≥ 0.90 on hand-written and on pilot data; draft judge agreement reported;
  p95 per enquiry < 60 s; cost per quote known.
- Pilot report with real before/after numbers and an owner quote; advisor sign-off; Annex 2B savings with citation.
- Onboarding to first quote < 10 min for a new exporter (measured in the usability test).
- 3 design-partner LOIs; pricing page; billing works in test mode.
- All existing gates still green; new gates: rbac 1.00, pilot extraction ≥ 0.90 (target), e2e on Claude ≥ 0.95.

## 3. Cut order if behind (most cuttable first)

Storybook/design page → PWA push → email inbound → Stripe metering (keep pricing page) → document upload eval set →
Redis multi-machine (keep single machine) → per-visitor sandboxes (keep read-only Viewer demo).
**Never cut:** auth + RBAC, demo lock, Claude evaluation, pilot report, Annex 2B attempt, video.

## 4. Founder-only tasks (cannot be done from code)

Fly/Neon/Vercel accounts and card · Anthropic API key · Meta WhatsApp app and number · Annex 2B source · advisor ·
pilot time with the family business · interviews and LOIs · Stripe account · company/Dubai licence · organiser
confirmation · video recording.
