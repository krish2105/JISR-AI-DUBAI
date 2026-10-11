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

- **No authentication yet.** The organisation is taken from an optional `X-Org-Id` header. Anyone who can reach the API
  can act as any organisation. The hosted demo is public and uses synthetic data only. Authentication, role-based
  access and a demo lock are planned in [docs/PLAN_95.md](docs/PLAN_95.md) (Phase 13) and are a precondition for real
  customer data.
- **Data.** All data in the repository and the demo is synthetic or public. Do not send real personal data to the demo.
- **Model providers.** Free-tier model profiles are restricted to synthetic data by code (`LLM_PROFILE=dev`); real data
  is only allowed with a paid, no-training provider.
- **In-memory state.** A2A tasks and rate-limit counters live in process memory and reset on restart.

## Security design (what is already enforced)

- Deterministic policy engine with autonomy levels; bank details, payment instructions and marking invoices paid are
  never allowed (`backend/app/governance/`).
- Every outbound message passes a single outbox that re-checks the kill switch and approval.
- Hash-chained audit log; `/audit/verify` recomputes the chain and reports the first tampered row.
- PII redaction before any model call, with a tripwire in the model router that refuses remaining identifiers.
- Prompt-injection guard plus policy checks; the red-team suite reports 0 of 30 attacks succeeding
  (see [docs/EVAL_REPORT.md](docs/EVAL_REPORT.md)).
- WhatsApp webhooks verify the `X-Hub-Signature-256` HMAC and are idempotent.
- MCP tools can analyse and read only; they cannot approve or send.
