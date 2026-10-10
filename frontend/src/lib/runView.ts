/**
 * runView.ts — Turn a list of RunEvents into what the screen needs to show.
 *
 * Why: the agent graph, the counters and the result panel must all agree. Deriving them
 * from the event list with one pure function (no fetching, no side effects) keeps them in
 * sync and makes the same logic reusable by the 3D graph and by offline replay.
 */

import type { RunEvent } from "./api";

export type NodeState = "idle" | "active" | "done" | "held" | "blocked" | "waiting";

/** Nodes of the agent graph, in pipeline order ("human" = the approver). */
export const GRAPH_NODES = [
  "ingest", "guard", "supervisor", "quote", "duty", "docs", "trust", "outreach", "governance", "human",
] as const;
export type GraphNode = (typeof GRAPH_NODES)[number];

export type RunView = {
  nodes: Record<GraphNode, NodeState>;
  plan: string[];
  risksCaught: number;
  steps: number;
  pendingApprovals: string[];       // approval ids still waiting for a human
  blocked: RunEvent[];              // governance "blocked" events
  agentSeconds: number | null;      // run_started -> governance finished
  governanceFinished: boolean;
  finalStatus: string | null;       // from the `done` event
};

/** Pure reducer: events in, view out. */
export function deriveRunView(events: RunEvent[]): RunView {
  const nodes = Object.fromEntries(GRAPH_NODES.map((n) => [n, "idle"])) as Record<GraphNode, NodeState>;
  let plan: string[] = [];
  let risksCaught = 0;
  let steps = 0;
  const pending = new Set<string>();
  const blocked: RunEvent[] = [];
  let startTs: number | null = null;
  let govEndTs: number | null = null;
  let finalStatus: string | null = null;

  for (const e of events) {
    const node = e.agent as GraphNode;
    const isNode = (GRAPH_NODES as readonly string[]).includes(e.agent);
    switch (e.kind) {
      case "run_started":
        startTs = Date.parse(e.ts);
        break;
      case "agent_started":
        if (isNode) nodes[node] = "active";
        break;
      case "agent_finished": {
        steps += 1;
        if (!isNode) break;
        nodes[node] = "done";
        if (e.agent === "guard") risksCaught += ((e.payload.flags as string[]) ?? []).length;
        if (e.agent === "trust") {
          const signals = (e.payload.signals as { risk: string }[]) ?? [];
          risksCaught += signals.filter((s) => s.risk !== "low").length;
        }
        if (e.agent === "governance") {
          govEndTs = Date.parse(e.ts);
          if (Number(e.payload.blocked) > 0 && Number(e.payload.held) === 0) nodes.governance = "blocked";
          else if (Number(e.payload.held) > 0) nodes.governance = "held";
        }
        break;
      }
      case "plan":
        plan = (e.payload.plan as string[]) ?? [];
        break;
      case "approval_needed":
        pending.add(String(e.payload.approval_id));
        nodes.human = "waiting";
        break;
      case "approval_decided":
        pending.delete(String(e.payload.approval_id));
        if (pending.size === 0) nodes.human = "done";
        break;
      case "blocked":
        blocked.push(e);
        break;
      case "done":
        finalStatus = String(e.payload.status ?? "");
        break;
    }
  }

  return {
    nodes,
    plan,
    risksCaught,
    steps,
    pendingApprovals: [...pending],
    blocked,
    agentSeconds: startTs !== null && govEndTs !== null ? (govEndTs - startTs) / 1000 : null,
    governanceFinished: govEndTs !== null,
    finalStatus,
  };
}

/** One-line human description of an event for the timeline (falls back to the payload's "why"). */
export function describe(e: RunEvent): string {
  const p = e.payload;
  if (typeof p.why === "string") return p.why;
  switch (e.kind) {
    case "tool_call":
      return String(p.tool ?? "tool");
    case "tool_result":
      return [p.tool, p.model, p.items !== undefined ? `${p.items} item(s)` : null].filter(Boolean).join(" · ");
    case "policy_decision":
      return `${String(p.action_type)} → ${String(p.effect)} (${((p.rule_ids as string[]) ?? []).join(", ")})`;
    case "approval_needed":
    case "blocked":
      return String(p.title ?? p.action_type ?? "");
    case "approval_decided":
      return `${String(p.decision)}${p.edited ? " (edited)" : ""}`;
    case "run_started": {
      const voice = p.voice_note as { stt_model?: string } | undefined;
      return voice
        ? `${String(p.channel ?? "")} · voice note → “${String(p.message_redacted ?? "").slice(0, 120)}” (${voice.stt_model ?? "stt"})`
        : String(p.channel ?? "");
    }
    case "error":
      return String(p.message ?? "");
    case "done":
      return String(p.status ?? "");
    default:
      return "";
  }
}
