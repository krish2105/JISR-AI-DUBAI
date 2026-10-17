# Security policy

## Supported versions

Only the `main` branch receives fixes. The hosted demo runs the latest `main`.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately through GitHub's private vulnerability reporting:
<https://github.com/krish2105/JISR-AI-DUBAI/security/advisories/new>

Include, where you can:

- what you found and where (file, endpoint or page);
- steps to reproduce, or a proof of concept;
- the impact you expect (for example, approval bypass, data exposure, prompt injection that changes an action);
- whether you have shared it with anyone else.

We aim to acknowledge reports within a week. We will agree a disclosure date with you before publishing anything,
and we credit reporters who want credit.

## Scope

In scope:

- the FastAPI backend (`backend/app`), including governance, approvals, the outbox, the audit chain and the
  WhatsApp, A2A and MCP interfaces;
- the Next.js dashboard (`frontend`);
- the deployment configuration (`deploy/`, `fly.toml`, `docker-compose.yml`).

Out of scope:

- denial of service by volume against a public demo (the demo has rate limits, and load tests against it are not
  permitted without prior agreement);
- findings that require a compromised machine or a leaked secret of the reporter's own;
- issues in third-party services (Neon, Fly.io, Vercel, Meta, Anthropic) that should go to those vendors.

## Known limitations (read before testing)

These are documented, deliberate gaps on the road to a production system, not undisclosed flaws:

- **Accounts are new.** Sign-in, roles and the demo sandbox arrived in Phase 13 (DECISIONS S9–S16). Passwords use
  scrypt; tokens are short-lived bearer tokens kept in the browser's local storage (S10), so a cross-site scripting bug
  would expose a session: please report any you find. Email verification, password reset and multi-factor sign-in are
  not built yet.
- **Data.** All data in the repository and the demo is synthetic or public. Do not send real personal data to the demo.
- **Model providers.** Free-tier model profiles are restricted to synthetic data by code (`LLM_PROFILE=dev`); real data
  is only allowed with a paid, no-training provider.
- **In-memory state.** A2A tasks and the daily model-token budget live in process memory (rate limits are in the
  database); run one API machine until they move to shared storage.

## Security design (what is already enforced)

- Deterministic policy engine with autonomy levels; bank details, payment instructions and marking invoices paid are
  never allowed (`backend/app/governance/`).
- Sign-in with scrypt-hashed passwords and short HS256 tokens; the role is re-read on every request; production refuses
  to start without `AUTH_SECRET`. Every route checks a permission from `backend/app/governance/rbac.yaml` (7 roles);
  high-risk approvals need the Owner, with a four-eyes rule for the person who started the run.
- Demo visitors get a private, expiring sandbox that can never reach real WhatsApp.
- Every outbound message passes a single outbox that re-checks the kill switch and approval.
- Hash-chained audit log; `/audit/verify` recomputes the chain and reports the first tampered row.
- PII redaction before any model call, with a tripwire in the model router that refuses remaining identifiers.
- Prompt-injection guard plus policy checks; the red-team suite reports 0 of 30 attacks succeeding
  (see [docs/EVAL_REPORT.md](docs/EVAL_REPORT.md)).
- WhatsApp webhooks verify the `X-Hub-Signature-256` HMAC and are idempotent.
- MCP tools can analyse and read only; they cannot approve or send.
- Security headers on the API and the dashboard (CSP, frame denial, nosniff, HSTS in production); dependency audits
  and secret scanning in CI; database migrations under version control; per-buyer export and erasure.
- Threat model and OWASP ASVS level 1 status: [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).
