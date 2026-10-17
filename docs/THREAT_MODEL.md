# Threat model (Phase 20)

Scope: the hosted Jisr API (FastAPI), dashboard (Next.js), database (Postgres/Neon), model providers, WhatsApp Cloud
API, A2A and MCP interfaces. Method: STRIDE per entry point; each row names the control in code and what remains.
Reviewed 2026-10-17. Re-review when an entry point or a data type is added.

## Assets

| Asset | Why it matters |
|---|---|
| Outbound channel (WhatsApp, A2A replies) | A wrong or forged message can change a payment or commit the exporter to a price |
| Approvals and the kill switch | They decide what leaves the building |
| Organisation data (enquiries, quotes, buyers, invoices) | Commercial secrets and personal data (PDPL / DPDP) |
| Audit chain | Evidence of who did what; must be tamper-evident |
| Secrets (AUTH_SECRET, model keys, WhatsApp token, MCP keys) | Each one grants impersonation or spending |

## Entry points and threats

| Entry point | Threat (STRIDE) | Control in code | Residual risk |
|---|---|---|---|
| Dashboard → API | **S**poofing another user | Signed HS256 tokens, role re-read per request, sign-out everywhere (`app/auth`) | Token in localStorage: an XSS bug would expose a session (CSP, no third-party scripts, React escaping; DECISIONS S10) |
| Dashboard → API | **E**levation of privilege | `require(permission)` on every route from `rbac.yaml`; high risk = owner; four-eyes; 50 RBAC tests + `rbac` eval (33 scenarios) | New routes must remember `require()`; the matrix test lists routes explicitly |
| Dashboard → API | Cross-organisation **I**nformation disclosure | Organisation only from the token; every query filtered by it; isolation tests return 404 | — |
| Sign-in | Credential guessing | scrypt, constant-time compare, dummy hash for unknown emails, per-IP attempt limit (DB-backed), audited failures | No MFA or account lockout yet |
| Enquiry text (WhatsApp, form, A2A, MCP) | Prompt injection → **T**ampering with actions | Injection guard + deterministic policy engine: models never decide; bank/payment actions are NEVER; red team 0/30 | A novel injection could still distort a *draft*; drafts always need a human |
| WhatsApp webhook | Forged deliveries (**S**) / replay | HMAC `X-Hub-Signature-256` on the raw body; idempotency table | Depends on the Meta app secret staying secret |
| A2A | Hostile buyer agent | Same pipeline and policies as a buyer's message; task completes only after owner approval | Open endpoint: rate limit applies to runs only |
| MCP | Data access by an assistant | Bearer key per organisation (hashed, revocable) or server token; read/analyse tools only; every call audited | A leaked key reads that organisation's analyses until revoked |
| Outbox | **R**epudiation of a send | Single door out: kill switch re-checked, approval required, audit entry with text hash | — |
| Audit log | **T**ampering | Hash chain per organisation; `/audit/verify` finds the first altered row; erasure never edits audit rows | A database superuser could rewrite the whole chain consistently; export the chain off-site for proof |
| Model provider | Personal data leaving | Redaction before any call + router tripwire; free tiers synthetic-only | Masked text still reaches the provider; paid no-training providers only for real data |
| Public demo | **D**enial of service / cost | Per-IP run limit (DB-backed), daily token budget with labelled offline fallback, bounded heavy retrieval | Volumetric attacks need the host's protection (Fly/Vercel) |
| Demo sandboxes | Abuse as a real channel | Sandboxes never reach real WhatsApp; cannot invite or create keys; expire and are purged | — |
| Dependencies | Supply chain | Locked versions (uv.lock, package-lock), pip-audit + npm audit + gitleaks in CI | Zero-day in a dependency |
| Browser | Clickjacking / sniffing | `frame-ancestors 'none'` / `X-Frame-Options: DENY`, `nosniff`, strict CSP on API responses, CSP on the dashboard | `'unsafe-inline'` scripts kept for Next's static bootstrap |

## OWASP ASVS 4.0 level 1 (selected)

| Area | Status |
|---|---|
| V2 Authentication | Passwords ≥ 10 chars, hashed with scrypt; generic error messages; attempt limiting. Missing: MFA, breached-password check, email verification, password reset |
| V3 Session management | Server-validated tokens, logout everywhere, short lifetime. Tokens not in cookies (no CSRF surface) |
| V4 Access control | Deny by default (unknown permission = denied), server-side checks on every route, tested matrix |
| V5 Validation | Pydantic models on every body; profile and catalogue validation; size limits on text fields |
| V7 Logging | Hash-chained audit of decisions, logins, settings, documents, data rights; no secrets or message text in logs |
| V8 Data protection | Redaction before models, masked contacts in lists, buyer export and erasure, sandboxes purged |
| V9 Communications | HTTPS enforced by the hosts; HSTS from the API in production |
| V10 Malicious code | Secret scanning and dependency audits in CI |
| V14 Configuration | Production refuses to start without AUTH_SECRET; security headers; `poweredByHeader` off |
