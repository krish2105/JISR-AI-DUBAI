"use client";

/**
 * AgentGraph2D.tsx — Live map of the agents, lit up by the event stream.
 *
 * Why: judges should SEE the system think: the supervisor fans work out to specialists,
 * everything converges on the governance gate, and only then does it reach a human.
 * A blocked action turns the gate red. The Phase 7 3D graph renders the same `RunView`.
 *
 * Accessibility: every node has a text label and a state word (not just a colour), and
 * the whole graph has an aria-label summary.
 */

import { motion } from "motion/react";
import { Check, Pause, ShieldAlert } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import type { GraphNode, NodeState, RunView } from "@/lib/runView";

const W = 1000;
// Left-to-right positions; mirrored for Arabic (right-to-left reading order).
const POS: Record<GraphNode, [number, number]> = {
  ingest: [60, 150], guard: [175, 150], supervisor: [300, 150],
  quote: [490, 40], duty: [490, 95], docs: [490, 150], trust: [490, 205], outreach: [490, 260],
  governance: [690, 150], human: [880, 150],
};
const WORKERS: GraphNode[] = ["quote", "duty", "docs", "trust", "outreach"];
const EDGES: [GraphNode, GraphNode][] = [
  ["ingest", "guard"], ["guard", "supervisor"],
  ...WORKERS.map((w) => ["supervisor", w] as [GraphNode, GraphNode]),
  ...WORKERS.map((w) => [w, "governance"] as [GraphNode, GraphNode]),
  ["supervisor", "governance"], ["governance", "human"],
];

const FILL: Record<NodeState, string> = {
  idle: "var(--muted)", active: "var(--accent)", done: "var(--accent-soft)",
  held: "var(--warn-soft)", blocked: "var(--risk)", waiting: "var(--warn-soft)",
};
const STROKE: Record<NodeState, string> = {
  idle: "var(--line)", active: "var(--accent)", done: "var(--accent)",
  held: "var(--warn)", blocked: "var(--risk)", waiting: "var(--warn)",
};

export function AgentGraph2D({ view }: { view: RunView }) {
  const { t, dir } = useI18n();
  const x = (n: GraphNode) => (dir === "rtl" ? W - POS[n][0] : POS[n][0]);
  const y = (n: GraphNode) => POS[n][1];
  const reached = (n: GraphNode) => view.nodes[n] !== "idle";
  const summary = Object.entries(view.nodes).map(([n, s]) => `${t.agents[n] ?? n}: ${s}`).join(", ");

  return (
    // direction:ltr keeps SVG coordinates and text-anchor predictable; we mirror positions ourselves.
    <svg viewBox={`0 0 ${W} 300`} className="h-auto w-full" role="img" aria-label={summary} style={{ direction: "ltr" }}>
      {/* Edges: drawn first so nodes sit on top. A traversed edge turns teal and "flows". */}
      {EDGES.map(([a, b]) => {
        const lit = reached(a) && reached(b);
        const bypass = a === "supervisor" && b === "governance";
        if (bypass && !(lit && view.plan[0] === "governance")) return null;   // only show the attack shortcut when taken
        return (
          <motion.line
            key={`${a}-${b}`}
            x1={x(a)} y1={y(a)} x2={x(b)} y2={y(b)}
            stroke={lit ? (bypass ? "var(--risk)" : "var(--accent)") : "var(--line)"}
            strokeWidth={lit ? 2.5 : 1.5}
            strokeDasharray={lit ? "6 6" : undefined}
            initial={false}
            animate={lit ? { strokeDashoffset: [24, 0] } : { strokeDashoffset: 0 }}
            transition={lit ? { duration: 1.2, repeat: Infinity, ease: "linear" } : undefined}
          />
        );
      })}

      {(Object.keys(POS) as GraphNode[]).map((n) => {
        const state = view.nodes[n];
        const isGate = n === "governance";
        const isWorker = WORKERS.includes(n);
        const r = isGate ? 30 : isWorker ? 18 : 22;
        // Worker labels sit beside the node (they are stacked vertically); others sit below.
        const labelX = isWorker ? (dir === "rtl" ? -(r + 10) : r + 10) : 0;
        const labelY = isWorker ? 5 : r + 18;
        const anchor = isWorker ? (dir === "rtl" ? "end" : "start") : "middle";
        return (
          <g key={n} transform={`translate(${x(n)} ${y(n)})`}>
            {state === "active" && (
              <motion.circle
                r={r}
                fill="none"
                stroke="var(--accent)"
                initial={{ scale: 1, opacity: 0.6 }}
                animate={{ scale: 1.7, opacity: 0 }}
                transition={{ duration: 1.1, repeat: Infinity }}
              />
            )}
            <motion.circle
              r={r}
              fill={FILL[state]}
              stroke={STROKE[state]}
              strokeWidth={isGate ? 3 : 2}
              initial={false}
              animate={state === "blocked" ? { scale: [1, 1.15, 1] } : { scale: 1 }}
              transition={{ duration: 0.5 }}
            />
            {state === "done" && <Check x={-8} y={-8} width={16} height={16} color="var(--accent)" />}
            {(state === "held" || state === "waiting") && <Pause x={-8} y={-8} width={16} height={16} color="var(--warn)" />}
            {state === "blocked" && <ShieldAlert x={-10} y={-10} width={20} height={20} color="var(--accent-ink)" />}
            <text
              x={labelX}
              y={labelY}
              textAnchor={anchor}
              fontSize={isWorker ? 13 : 14}
              fontWeight={isGate ? 600 : 500}
              fill={state === "idle" ? "var(--ink-3)" : "var(--ink)"}
              stroke="var(--surface)"            /* halo keeps labels readable over edge lines */
              strokeWidth={4}
              paintOrder="stroke"
            >
              {t.agents[n] ?? n}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
