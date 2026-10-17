/**
 * api.ts — Typed client for the Jisr API (FastAPI on :8000 by default).
 *
 * Why: one place that knows the API's URL and the shapes of its responses. The types
 * mirror the frozen backend contracts (docs/CONTRACTS.md): RunEvent, runs, approvals, audit.
 */

import { getToken, setToken } from "./session";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** An HTTP error from the API, with its status (401 = sign in again, 403 = your role cannot). */
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

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
    docs?: { status: string; documents: { document: string; citation: Citation | null }[]; note?: string;
             draft?: unknown } | null;
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

export type KbRule = { rule_id: string; text: string; scope: string; page_label: string; is_ex: boolean };
export type KbChapter = { code: string; title: string; title_ar: string; rule: string | null };
export type KbNode = { code: string; level: string; desc_en: string; desc_ar: string; duty_pct: string | null;
  rule: KbRule | null; children: KbNode[]; more: number; source?: { tariff: string; rules: string } };
export type KbLocate = { query: string; needs_human_check: boolean;
  candidates: { heading: string; line: string; desc: string; confidence: number; duty_pct: string | null; path: string[]; rule: KbRule | null }[] };

export type Impact = {
  since: string; days: number;
  measured: { enquiries: number; quotes_drafted: number; approved_and_sent: number; rejected: number; waiting: number;
    median_agent_seconds: number | null; acknowledged_automatically: number; median_seconds_to_acknowledge: number | null;
    risks_caught: number; blocked_by_policy: number; duty_upto_aed: number };
  estimated: { minutes_saved: number; assumptions: { manual_minutes_per_quote: number; review_minutes_per_quote: number; source: string } };
  ledger: { run_id: string; created_at: string; channel: string; status: string; buyer: string | null;
    quote_total_aed: number | null; duty_upto_aed: number | null; risks: number; agent_seconds: number | null; kind: string }[];
};

export type VoiceSample = { name: string; language: "ar" | "en"; transcript: string; audio_url: string };

export type Approval = {
  id: string; run_id: string; created_at: string; action_type: string; title: string;
  payload: { text?: string; language?: string; channel?: string; edited_by_human?: boolean };
  reason: string; evidence: string[]; risk: Risk; rule_id: string; status: "pending" | "approved" | "rejected";
  decided_by: string | null; decided_at: string | null; decision_note: string | null;
  approver_role?: "owner" | "approver"; can_decide?: boolean;
};

export type AuditEntry = {
  id: number; ts: string; actor: string; action: string; run_id: string | null;
  details: Record<string, unknown>; hash: string; prev_hash: string;
};

export type ChainReport = { ok: boolean; entries: number; broken_at_id: number | null; reason: string | null };

export type Role = "owner" | "admin" | "approver" | "operator" | "accountant" | "auditor" | "viewer";
export const ROLES: Role[] = ["owner", "admin", "approver", "operator", "accountant", "auditor", "viewer"];

export type Me = {
  user: { id: string; email: string; name: string };
  org: { id: string; name: string; is_sandbox: boolean; expires_at: string | null };
  role: Role; role_label: string; role_label_ar: string;
  permissions: string[];
  orgs: { id: string; name: string; role: Role; is_sandbox: boolean }[];
  onboarding?: { done: boolean; step: number };
};

export type CatalogueItem = {
  name: string; keywords: string[]; materials: string[]; unit_cost_inr: number; kg: number; cbm: number;
  hs_hint: string | null;
};
export type LogisticsSettings = {
  origin_port: string; inland_freight_inr_per_kg: number; export_clearance_inr: number;
  ocean_freight_aed_per_cbm: Record<string, number>; min_cbm: number; insurance_pct: number;
  destination_delivery_aed: number; destination_clearance_aed: number; import_duty_pct: number; import_duty_source: string;
};
export type BusinessProfile = {
  seller_name: string; home_currency: string; quote_currency: string; quote_validity_days: number;
  default_margin_pct: number; min_margin_pct: number; max_discount_pct: number;
  volume_discounts: { min_qty: number; pct: number }[]; fx_stub_inr_to_aed: number; catalogue: CatalogueItem[];
  default_unit_cost_inr: number; default_kg: number; default_cbm: number; logistics: LogisticsSettings;
  roi: { manual_minutes_per_quote: number; review_minutes_per_quote: number; source: string };
};
export type ProfileView = {
  profile: BusinessProfile; source: "organisation" | "demo";
  onboarding: { steps: string[]; step: number; done: boolean };
};
export type DocLine = {
  description: string; quantity?: number; unit?: string; unit_price?: number; amount?: number; hs_code?: string | null;
  gross_kg?: number | null; hs_candidates?: (string | undefined)[]; rule?: string | null; rule_ref?: string | null;
  evidence_needed?: string[]; needs_human_check?: boolean; catalogue_match?: boolean;
};
export type TradeDocument = {
  kind: "quotation" | "proforma_invoice" | "packing_list" | "origin_checklist"; title: string; title_ar: string;
  number: string; status: "draft" | "final"; date: string; run_id: string; available: boolean; reason?: string;
  seller: { name: string; country: string; port_of_loading: string }; buyer: { name: string; country: string };
  lines?: DocLine[]; charges?: { description: string; amount: number }[];
  totals?: Record<string, number | string | null>; terms?: Record<string, string | number | boolean | null>;
  notes?: string[]; common_requirements?: (string | null)[]; checksum: string;
};

export type Buyer = {
  contact_key: string; channel: string | null; contact: string; name: string | null; first_seen: string; last_seen: string;
  runs: number; quotes_sent: number; last_incoterm: string | null; last_quote_total_aed: number | null;
  languages: string[]; risk_signals: string[];
};

export type AutonomyItem = {
  action_type: string; default: string; level: string; allowed: string[]; locked: boolean; why: string;
};
export type Session = { token: string; me: Me };
export type AuthConfig = { demo_mode: boolean; allow_signup: boolean; sandbox_hours: number };
export type Member =
  | { user_id: string; email: string; name: string; role: Role; you: boolean; pending?: undefined }
  | { invitation_id: string; email: string; role: Role; pending: true; expires_at: string };
export type Invitation = { invitation_id: string; email: string; role: Role; token: string; expires_at: string };
export type ApiKey = { id: string; name: string; kind: string; prefix: string; created_at: string;
  last_used_at: string | null; revoked: boolean };

/** fetch() wrapper: JSON in/out, sends the session token, throws ApiError with the API's message. */
async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? getToken() : null;
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    if (res.status === 401 && token) setToken(null);          // expired or revoked: show the sign-in screen
    throw new ApiError((detail as { detail?: string }).detail ?? `HTTP ${res.status}`, res.status);
  }
  return res.json() as Promise<T>;
}

/** Same as call() for plain-text responses (CSV export). */
async function callText(path: string): Promise<string> {
  const token = typeof window !== "undefined" ? getToken() : null;
  const res = await fetch(`${API_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {}, cache: "no-store" });
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status);
  return res.text();
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });
const post = (body?: unknown): RequestInit => ({ method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  samples: () => call<Sample[]>("/demo/samples"),
  startRun: (body: { sample_id?: string; message?: string; channel?: string }) =>
    call<{ run_id: string }>("/runs", { method: "POST", body: JSON.stringify(body) }),
  run: (id: string) => call<RunDetail>(`/runs/${id}`),
  approvals: (status: "pending" | "all" = "pending") => call<Approval[]>(`/approvals?status=${status}`),
  approve: (id: string, body: { note?: string; edited_text?: string; override_reason?: string } = {}) =>
    call<Approval>(`/approvals/${id}/approve`, { method: "POST", body: JSON.stringify(body) }),
  reject: (id: string, body: { note?: string } = {}) =>
    call<Approval>(`/approvals/${id}/reject`, { method: "POST", body: JSON.stringify(body) }),
  audit: (limit = 100) => call<AuditEntry[]>(`/audit?limit=${limit}`),
  verifyAudit: () => call<ChainReport>("/audit/verify"),
  /** EventSource cannot send headers: get a short stream token for this run first. */
  eventsUrl: async (runId: string) => {
    const { token } = await call<{ token: string }>(`/runs/${runId}/stream-token`, { method: "POST" });
    return `${API_URL}/runs/${runId}/events?st=${encodeURIComponent(token)}`;
  },
  auditExport: () => call<{ org_id: string; verification: ChainReport; entries: AuditEntry[] }>("/audit/export"),
  governance: () => call<Governance>("/governance"),
  killSwitch: (engaged: boolean, reason?: string) =>
    call<Governance>("/governance/kill-switch", { method: "POST", body: JSON.stringify({ engaged, reason }) }),
  autonomous: (hours = 24) => call<AutonomousLog>(`/governance/autonomous?hours=${hours}`),
  passports: () => call<Passport[]>("/passports"),
  voiceSamples: () => call<VoiceSample[]>("/channels/whatsapp/voice-samples"),
  simulateWhatsApp: (body: { text?: string; voice_sample?: string }) =>
    call<{ status: string; run_id?: string; reason?: string }>("/channels/whatsapp/simulate", { method: "POST", body: JSON.stringify(body) }),
  kbChapters: () => call<KbChapter[]>("/kb/chapters"),
  kbTree: (chapter: string) => call<KbNode>(`/kb/tree?chapter=${encodeURIComponent(chapter)}`),
  kbLocate: (q: string) => call<KbLocate>(`/kb/locate?q=${encodeURIComponent(q)}`),
  impact: (days = 30) => call<Impact>(`/impact?days=${days}`),
  // --- Phase 13: sessions, team, machine keys
  authConfig: () => call<AuthConfig>("/auth/config"),
  me: () => call<Me>("/auth/me"),
  signup: (body: { email: string; password: string; name?: string; org_name?: string }) =>
    call<Session>("/auth/signup", post(body)),
  login: (body: { email: string; password: string }) => call<Session>("/auth/login", post(body)),
  demoSandbox: () => call<Session>("/auth/demo", post()),
  switchOrg: (org_id: string) => call<Session>("/auth/switch", post({ org_id })),
  logoutAll: () => call<{ ok: boolean }>("/auth/logout-all", post()),
  invitation: (token: string) =>
    call<{ org_name: string; email: string; role: Role; has_account: boolean }>(`/auth/invitations/${encodeURIComponent(token)}`),
  acceptInvitation: (body: { token: string; password: string; name?: string }) =>
    call<Session>("/auth/invitations/accept", post(body)),
  members: () => call<Member[]>("/team/members"),
  invite: (email: string, role: Role) => call<Invitation>("/team/invitations", post({ email, role })),
  revokeInvitation: (id: string) => call<{ ok: boolean }>(`/team/invitations/${id}`, { method: "DELETE" }),
  changeRole: (userId: string, role: Role) =>
    call<{ user_id: string; role: Role }>(`/team/members/${userId}`, { method: "PATCH", body: JSON.stringify({ role }) }),
  removeMember: (userId: string) => call<{ ok: boolean }>(`/team/members/${userId}`, { method: "DELETE" }),
  apiKeys: () => call<ApiKey[]>("/team/api-keys"),
  createApiKey: (name: string) => call<ApiKey & { key: string }>("/team/api-keys", post({ name })),
  revokeApiKey: (id: string) => call<{ ok: boolean }>(`/team/api-keys/${id}`, { method: "DELETE" }),
  health: () => call<{ status: string; llm_profile: string; budget?: { fallback_active?: boolean } }>("/health"),
  runs: (limit = 5) =>
    call<{ id: string; status: string; channel: string; sample_id: string | null; created_at: string }[]>(`/runs?limit=${limit}`),
  // --- Phase 20: buyers and data rights
  buyers: () => call<Buyer[]>("/buyers"),
  exportBuyer: (key: string) => call<Record<string, unknown>>(`/buyers/${encodeURIComponent(key)}/export`),
  eraseBuyer: (key: string) => call<{ erased: string; runs_scrubbed: number }>(`/buyers/${encodeURIComponent(key)}`, { method: "DELETE" }),
  // --- Phase 17: documents and the run's own audit trail
  documents: (runId: string) => call<Record<TradeDocument["kind"], TradeDocument>>(`/runs/${runId}/documents`),
  issueDocument: (runId: string, kind: string) =>
    call<{ kind: string; number: string; checksum: string }>(`/runs/${runId}/documents/${kind}/issue`, { method: "POST" }),
  runAudit: (runId: string) => call<AuditEntry[]>(`/audit?run_id=${encodeURIComponent(runId)}&limit=200`),
  // --- Phase 15: settings and onboarding
  profile: () => call<ProfileView>("/settings/profile"),
  patchProfile: (sections: Partial<BusinessProfile>) => call<ProfileView>("/settings/profile", json("PATCH", sections)),
  addProduct: (item: CatalogueItem) => call<ProfileView>("/settings/catalogue", json("POST", item)),
  replaceProduct: (name: string, item: CatalogueItem) =>
    call<ProfileView>(`/settings/catalogue/${encodeURIComponent(name)}`, json("PUT", item)),
  removeProduct: (name: string) => call<ProfileView>(`/settings/catalogue/${encodeURIComponent(name)}`, { method: "DELETE" }),
  importCatalogue: (csv: string, mode: "merge" | "replace") =>
    call<ProfileView & { import: { added: number; updated: number; errors: string[] } }>(
      "/settings/catalogue/import", json("POST", { csv, mode })),
  exportCatalogue: () => callText("/settings/catalogue/export"),
  autonomy: () => call<AutonomyItem[]>("/settings/autonomy"),
  setAutonomy: (action_type: string, level: string) =>
    call<AutonomyItem[]>("/settings/autonomy", json("PUT", { action_type, level })),
  onboardingStep: (step: number, done = false) => call<ProfileView>("/settings/onboarding", json("POST", { step, done })),
  runCollections: () => call<{ drafted: number; reminders: { invoice_id: string; days_overdue: number; tone: string }[] }>(
    "/collections/run", { method: "POST" }),
};
