/**
 * api.ts — Typed client for the Jisr API (FastAPI on :8000 by default).
 *
 * Why: one place that knows the API's URL and the shapes of its responses. The types
 * mirror the frozen backend contracts (docs/CONTRACTS.md): RunEvent, runs, approvals, audit.
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Risk = "low" | "medium" | "high";

export type EventKind =
  | "run_started" | "agent_started" | "agent_finished" | "plan" | "tool_call" | "tool_result"
  | "retrieval_attempt" | "policy_decision" | "approval_needed" | "approval_decided"
  | "blocked" | "error" | "done";

/** One step of a run, exactly as the backend streams it. */
export type RunEvent = {
  run_id: string;
  seq: number;
  ts: string;
  agent: string;
  kind: EventKind;
  payload: Record<string, unknown>;
  risk: Risk | null;
};

export type Sample = {
  id: string; label: string; label_ar: string; channel: string; message: string; hostile: boolean;
};

export type QuoteLine = {
  description: string; quantity: number; unit: string; unit_price_aed: number; unit_price_inr: number;
  total_aed: number; total_inr: number; catalogue_match: boolean;
};

export type QuoteCharge = { code: string; description: string; basis: string; total_aed: number; total_inr: number };

export type Quote = {
  lines: (QuoteLine & { discount_pct?: number; effective_margin_pct?: number; catalogue_item?: string | null })[];
  charges?: QuoteCharge[];
  incoterm: string | null; incoterm_assumed?: boolean; destination_country?: string;
  margin_pct: number; min_effective_margin_pct?: number | null;
  fx_inr_to_aed: number; fx_source: string;
  fx?: { rate: number; source: string; rate_date: string | null; fetched_at: string; stale: boolean };
  goods_total_aed?: number; charges_total_aed?: number; total_inr: number; total_aed: number;
  validity_days: number; pricing_flags?: string[]; notes?: string[];
};

export type Citation = {
  chunk_id: string; kind?: string; document: string; issuer?: string; document_date?: string; url?: string;
  section?: string; page?: number | null; page_label?: string | null; excerpt?: string; excerpt_ar?: string;
};

export type DutyLine = {
  description: string;
  hs_candidates?: { heading: string; best_line: string; best_line_desc: string; duty_pct: string | null; confidence: number }[];
  hs_confidence?: number;
  catalogue_hint?: string | null; hint_agrees?: boolean | null;
  rule?: { rule_id: string; scope: string; text: string; page_label: string; is_ex: boolean } | null;
  evidence_needed?: string[];
  mfn_duty_pct?: string | null; mfn_duty_aed?: number | null; cif_value_aed?: number;
  claims?: { text: string; citations: string[] }[];
  needs_human_check?: boolean;
};

export type DutyAnalysis = {
  status: string; lines: DutyLine[]; total_mfn_duty_aed?: number; max_potential_saving_aed?: number | null;
  preferential_rate?: string; common_requirements?: { text: string; citation: string | null }[];
  citations?: Record<string, Citation>; note?: string; needs_human_check?: boolean;
};

export type RunDetail = {
  id: string; status: string; channel: string; sample_id: string | null; created_at: string;
  message_redacted: string;
  state: {
    quote?: Quote | null; drafts?: { language: string; text: string }[]; impact?: Record<string, number>;
    duty?: DutyAnalysis | null;
    docs?: { status: string; documents: { document: string; citation: Citation | null }[]; note?: string } | null;
    doc_issues?: DocIssue[];
    buyer_signals?: BuyerSignal[];
  };
  approvals: { id: string; title: string; status: string; risk: Risk }[];
};

export type DocIssue = {
  type: string; field: string; severity: "high" | "medium" | "low"; message: string; fix: string;
  expected?: unknown; found?: unknown; rule_ref?: string | null; citation?: Citation | null;
};

export type BuyerSignal = {
  signal: string; risk: "high" | "medium" | "low" | "positive" | "info"; evidence: string; why: string; source?: string;
};

export type Governance = {
  kill_switch: boolean; kill_reason: string | null; updated_by: string | null; updated_at: string | null;
  policies: { id: string; description: string; effect: "allow" | "require_approval" | "block"; risk: Risk;
              when: Record<string, unknown> }[];
  default_effect: string;
  autonomy: { action_type: string; level: string; why: string }[];
  default_level: string;
};

export type AutonomousLog = {
  since: string; done_alone: number; blocked: number;
  items: { id: number; ts: string; action: string; run_id: string | null; details: Record<string, unknown> }[];
};

export type Passport = {
  id: string; name: string; purpose: string; tools: string[]; data: string[]; models: string[]; actions: string[];
  autonomy: Record<string, string>;
  metrics: { suite: string; metric: string; value: number | null; result_file: string | null; git_sha: string | null }[];
  activity_24h: Record<string, number>;
};

export type VoiceSample = { name: string; language: "ar" | "en"; transcript: string; audio_url: string };

export type Approval = {
  id: string; run_id: string; created_at: string; action_type: string; title: string;
  payload: { text?: string; language?: string; channel?: string; edited_by_human?: boolean };
  reason: string; evidence: string[]; risk: Risk; rule_id: string; status: "pending" | "approved" | "rejected";
  decided_by: string | null; decided_at: string | null; decision_note: string | null;
};

export type AuditEntry = {
  id: number; ts: string; actor: string; action: string; run_id: string | null;
  details: Record<string, unknown>; hash: string; prev_hash: string;
};

export type ChainReport = { ok: boolean; entries: number; broken_at_id: number | null; reason: string | null };

/** fetch() wrapper: JSON in/out, throws on HTTP errors with the API's message. */
async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  samples: () => call<Sample[]>("/demo/samples"),
  startRun: (body: { sample_id?: string; message?: string; channel?: string }) =>
    call<{ run_id: string }>("/runs", { method: "POST", body: JSON.stringify(body) }),
  run: (id: string) => call<RunDetail>(`/runs/${id}`),
  approvals: (status: "pending" | "all" = "pending") => call<Approval[]>(`/approvals?status=${status}`),
  approve: (id: string, body: { note?: string; edited_text?: string } = {}) =>
    call<Approval>(`/approvals/${id}/approve`, { method: "POST", body: JSON.stringify(body) }),
  reject: (id: string, body: { note?: string } = {}) =>
    call<Approval>(`/approvals/${id}/reject`, { method: "POST", body: JSON.stringify(body) }),
  audit: (limit = 100) => call<AuditEntry[]>(`/audit?limit=${limit}`),
  verifyAudit: () => call<ChainReport>("/audit/verify"),
  eventsUrl: (runId: string) => `${API_URL}/runs/${runId}/events`,
  governance: () => call<Governance>("/governance"),
  killSwitch: (engaged: boolean, reason?: string) =>
    call<Governance>("/governance/kill-switch", { method: "POST", body: JSON.stringify({ engaged, reason }) }),
  autonomous: (hours = 24) => call<AutonomousLog>(`/governance/autonomous?hours=${hours}`),
  passports: () => call<Passport[]>("/passports"),
  voiceSamples: () => call<VoiceSample[]>("/channels/whatsapp/voice-samples"),
  simulateWhatsApp: (body: { text?: string; voice_sample?: string }) =>
    call<{ status: string; run_id?: string; reason?: string }>("/channels/whatsapp/simulate", { method: "POST", body: JSON.stringify(body) }),
  runCollections: () => call<{ drafted: number; reminders: { invoice_id: string; days_overdue: number; tone: string }[] }>(
    "/collections/run", { method: "POST" }),
};
