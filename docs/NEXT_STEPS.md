# Next steps (saved 2026-10-28) — start here

State: everything up to commit `19fa822` is pushed and the dashboard is live at https://jisr-ai-eta.vercel.app
(frontend only; the backend has no host yet, so sign-in, demo and approvals need the backend). Backend tests 366
passed; frontend build clean. CI on `19fa822` not yet confirmed green online (check `gh run list`).

## To build (in this order)
1. **Arabic explanations** (Phase 20). Translate by stable code in the dashboard, not in the backend (audit text stays
   English): add an `explain` section to `frontend/src/i18n/dictionaries.ts` (English maps empty → fall back to the
   backend text; Arabic maps filled) and use it in:
   - `components/demo/ChecksCard.tsx` (doc issues `f.message` / `f.fix` by `f.type`; buyer signals `s.why` by `s.signal`),
   - `components/approvals/ApprovalsInbox.tsx` + `ApprovalCard.tsx` ("why this needs you": policy text by rule id),
   - `components/governance/GovernancePanel.tsx` (policy list, autonomy "why"), `components/settings/AutonomyTable.tsx`.
   Codes: policies P-BANK-001, P-OUT-001, P-INJ-001, P-MARGIN-001, P-DISC-001, P-PRICE-001, P-TRUST-001, P-KILL-001,
   P-ACK-001, P-INJ-002 (`backend/app/governance/policies.yaml`); autonomy actions in `autonomy.yaml`; signals:
   bank_change_request, business_email_domain, credit_terms_request, destination_outside_gcc, earlier_high_risk_signal,
   free_mail_domain, large_first_order, no_email_given, possible_sanctions_match, pressure_urgency, returning_buyer,
   sanctions_list_not_loaded, sanctions_no_close_match, sanctions_no_name, third_party_payment, trade_licence_given
   (`backend/app/tools/buyer_trust.py`, `app/agents/nodes.py`); doc issue types: consignment_gap, currency_mismatch,
   hs_mismatch, invoice_total_mismatch, line_total_mismatch, missing_coo, missing_export_declaration, qty_mismatch,
   weight_inconsistency (`backend/app/tools/doc_checker.py`; messages contain values → Arabic template per type using
   `expected` / `found`).
2. **Data retention job**: `org_settings.retention_days` (nullable = keep), purge runs + events + approvals older than N
   days (audit kept), run at start-up and every 24 h + `make retention`; settings endpoint and a field in Settings;
   Alembic migration (`make migration m="retention"`); tests.
3. **Password change / reset + two-factor sign-in**: `POST /auth/password` (signed in, bumps session_version);
   owner/admin generates a one-time reset link for a member (`password_resets` table, hashed token, fragment link like
   invitations); TOTP 2FA (stdlib RFC 6238, secret encrypted with a key derived from AUTH_SECRET; setup → confirm →
   required at login; owner can reset a member's 2FA). Migration + tests + sign-in UI field.
4. **Browser check** of the new sidebar (signed in, EN/AR, dark, phone width) with the local preview servers.
5. **Phase 21 submission pack**: full `make eval` on a clean commit (worktree method), re-score `docs/SCORECARD.md`
   (append a dated row), refresh `docs/SUBMISSION.md`, `docs/VIVA_QA.md`, `docs/DEMO_CHECKLIST.md`,
   `docs/PITCH_NOTES.md` with Phases 13–20 (login/roles/sandboxes, onboarding, documents, inbox v2, ops, pilot kit,
   plans), write the deck and the 2–3 min video script.
6. **After the Claude key**: uploaded-document checking (vision extraction → doc checker), email channel,
   `EVAL_PROFILE=prod make eval` (Claude numbers + measured cost per quote), `LLM_PROFILE=prod make record`.

## Waiting on the founder
1. Backend host: card on Fly (`fly apps create`, `docs/DEPLOY_E2E.md`; secrets incl. AUTH_SECRET) or Hugging Face PRO
   ($9/month; `scripts/hf_space_deploy.py`). Neon database `myneon` (Singapore) already exists. Then set
   `NEXT_PUBLIC_API_URL` on Vercel and redeploy.
2. Anthropic API key. 3. Pilot: 30–50 labelled past enquiries (`docs/pilot/LABEL_SHEET.md`, then `make pilot`).
4. Customs adviser, 5 interviews, 3 LOIs, organiser deadline confirmation, video recording.
5. Delete `jisr-ai/env.txt` (Neon password, never committed); revoke the Hugging Face token pasted earlier.

## Working rules
No AI co-author or "Generated with" lines in commits/PRs. Never tune on the test split. Every number from result files.
