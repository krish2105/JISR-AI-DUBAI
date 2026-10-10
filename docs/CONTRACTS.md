# Frozen contracts (Phase 1)

The backend, the dashboard, the future 3D views and the replay recordings all depend on these
shapes. **Change them only with an entry in `docs/DECISIONS.md`**, and update both sides
(`backend/app/...` and `frontend/src/lib/api.ts`) in the same commit.

## 1. RunEvent (SSE + database + replay files)

Source of truth: [`backend/app/events.py`](../backend/app/events.py) · TypeScript mirror: [`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts)

```json
{
  "run_id": "run_93939c9a756a",
  "seq": 7,                         // 1, 2, 3 ... gap-free within a run
  "ts": "2026-10-09T13:56:41.120Z", // always UTC with zone
  "agent": "quote",                 // ingest|guard|supervisor|quote|duty|docs|trust|outreach|governance|system|channel|human:<who>
  "kind": "tool_call",              // see list below
  "payload": { "tool": "llm.rfq_extract", "role": "worker" },
  "risk": null                      // low|medium|high|null
}
```

`kind` values: `run_started`, `agent_started`, `agent_finished`, `plan`, `tool_call`, `tool_result`,
`retrieval_attempt`, `policy_decision`, `approval_needed`, `approval_decided`, `blocked`, `error`, `done`.

Payload conventions:
- `agent_finished.payload.why`: one-line reason shown in the timeline (every agent sets it).
- `payload.stub: true`: the agent is a placeholder for a later phase (the UI shows a "stub" badge).
- `payload.needs_human_check: true`: an output that must be verified by a person.
- `done` is terminal: the SSE stream closes after it. A run waiting for approval has no `done` yet.

## 2. REST API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | status, env, active LLM profile and models |
| POST | `/runs` | body `{message?, sample_id?, channel?}` → `{run_id}` (agents run in the background) |
| GET | `/runs` | recent runs of the caller's org |
| GET | `/runs/{id}` | status, redacted message, state (quote, drafts, impact), approvals |
| GET | `/runs/{id}/events` | **SSE**: stored events, then live ones, until `done`. Resume with `?after=<seq>` or the browser's `Last-Event-ID` |
| GET | `/approvals?status=pending\|approved\|rejected\|all` | approval inbox |
| POST | `/approvals/{id}/approve` | body `{note?, edited_text?}`; performs the action through the (simulated) channel |
| POST | `/approvals/{id}/reject` | body `{note?}` |
| GET | `/audit?limit=` | latest audit entries |
| GET | `/audit/verify` | recompute the hash chain → `{ok, entries, broken_at_id, reason}` |
| GET | `/demo/samples` | built-in demo enquiries |
| GET | `/governance` | kill switch state, every policy rule, autonomy level per action type (P7) |
| POST | `/governance/kill-switch` | body `{engaged, reason?}`; audited; while on, nothing leaves (P7) |
| GET | `/governance/autonomous?hours=24` | actions done without a human + blocks, from the audit chain (P7) |
| GET | `/passports` | Agent Passports: enforced tools, data, autonomy, live eval metrics, 24 h activity (P7) |
| GET | `/channels/whatsapp/webhook` | Meta verification handshake (`hub.mode`, `hub.verify_token`, `hub.challenge`) (P8) |
| POST | `/channels/whatsapp/webhook` | signed deliveries (`X-Hub-Signature-256`); 401 if unsigned (P8) |
| POST | `/channels/whatsapp/simulate?sync=` | `{text}` or `{voice_sample}` → same path as a real delivery → `{status, run_id}` (P8) |
| GET | `/channels/whatsapp/voice-samples` · `/channels/whatsapp/voice/{name}` | synthetic voice notes and their audio (P8) |
| GET | `/collections/invoices` · POST `/collections/run` | invoices; draft overdue reminders into the approval inbox (P8) |

Organisation: optional `X-Org-Id` header (default `demo`). Every query filters by org; other orgs get 404.

Planned (not yet built): `GET /kb/tree` (P11, 3D tariff tree), `GET /roi` (P10).

`run_started` payload may carry `source` (`whatsapp` | `simulator`) and `voice_note` `{stt_model, provider, audio_sha256, language}` (additive, P8).

## 3. RunState

Source of truth: [`backend/app/agents/state.py`](../backend/app/agents/state.py) (v3 §8.1 plus `channel` and typed `pending_actions`). Additive in Phase 9: `contact_key`, `memory` (DECISIONS A2).

## 4. Governance files

- `backend/app/governance/policies.yaml`: rules evaluated by `policy_engine.py` (strongest effect wins: block > require_approval > allow; default require_approval).
- `backend/app/governance/autonomy.yaml`: autonomy level per action type (NEVER, L0–L3, default L1). Final effect = strongest of policy effect and autonomy cap (autonomy only adds caution).
- `backend/app/governance/passports.yaml`: Agent Passports; tool calls outside an agent's list are refused by `RunEmitter` (event `blocked`, rule `PASSPORT`).
- `backend/app/channels/outbox.py`: the single outbound path (approved and autonomous actions); re-checks the kill switch.
- Audit chain: `hash = sha256(canonical_json(org_id, ts, actor, action, run_id, details, prev_hash))`, per organisation, starting from `GENESIS`.
