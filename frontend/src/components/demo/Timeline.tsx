"use client";

/**
 * Timeline.tsx — Step-by-step story of a run, newest at the bottom.
 *
 * Why: the graph shows WHERE the run is; the timeline shows WHY each step happened
 * (each agent's short "why"), what tools it called, and every policy decision.
 * Placeholder agents carry a "stub" badge so nothing pretends to be finished.
 */

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useI18n } from "@/i18n/I18nProvider";
import type { RunEvent } from "@/lib/api";
import { describe } from "@/lib/runView";
import { Badge, RiskBadge, cx } from "@/components/ui/primitives";

// agent_started rows add noise; the finished row carries the useful summary.
const HIDDEN = new Set(["agent_started"]);

const DOT: Record<string, string> = {
  blocked: "bg-risk", error: "bg-risk", approval_needed: "bg-warn", policy_decision: "bg-sand",
  done: "bg-ok", approval_decided: "bg-ok", tool_call: "bg-ink-3", tool_result: "bg-ink-3",
};

export function Timeline({ events }: { events: RunEvent[] }) {
  const { t } = useI18n();
  const endRef = useRef<HTMLLIElement | null>(null);
  const visible = events.filter((e) => !HIDDEN.has(e.kind));
  const start = events[0] ? Date.parse(events[0].ts) : 0;

  // Keep the newest step in view as events stream in.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [visible.length]);

  if (visible.length === 0) {
    return <p className="px-4 py-10 text-center text-sm text-ink-3">{t.demo.emptyTimeline}</p>;
  }

  return (
    <ol className="max-h-[440px] space-y-1 overflow-y-auto p-3" aria-live="polite">
      <AnimatePresence initial={false}>
        {visible.map((e) => (
          <motion.li
            key={e.seq}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
            className={cx(
              "flex gap-3 rounded-lg px-2 py-2 text-sm",
              e.kind === "blocked" && "bg-risk-soft",
              e.kind === "approval_needed" && "bg-warn-soft",
            )}
          >
            <span className={cx("mt-1.5 h-2 w-2 shrink-0 rounded-full", DOT[e.kind] ?? "bg-accent")} aria-hidden />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="font-medium text-ink">
                  {/* "human:<who>" actors are shown as "You"; agents by their translated name. */}
                  {e.agent.startsWith("human:") ? t.agents.human : (t.agents[e.agent] ?? e.agent)}
                </span>
                <span className="text-ink-3">{t.kinds[e.kind] ?? e.kind}</span>
                {e.payload.stub === true && <Badge tone="sand">{t.demo.stub}</Badge>}
                {e.payload.needs_human_check === true && <Badge tone="warn">{t.demo.needsHumanCheck}</Badge>}
                <RiskBadge risk={e.kind === "agent_finished" && e.risk === "low" ? null : e.risk} label={t.risk[e.risk ?? ""] ?? ""} />
                <span className="ms-auto font-mono text-xs text-ink-3">
                  <bdi>+{((Date.parse(e.ts) - start) / 1000).toFixed(1)}s</bdi>
                </span>
              </div>
              {/* dir="auto": agent explanations may be English inside the Arabic UI; let the
                  browser pick the right direction so punctuation stays where it belongs. */}
              {describe(e) && <p dir="auto" className="mt-0.5 break-words text-start text-ink-2">{describe(e)}</p>}
              {/* Guard evidence: the exact text that triggered each flag (why it was flagged). */}
              {Array.isArray(e.payload.evidence) && (e.payload.evidence as { flag: string; snippet: string }[]).length > 0 && (
                <ul className="mt-1 space-y-0.5">
                  {(e.payload.evidence as { flag: string; snippet: string }[]).map((ev) => (
                    <li key={ev.flag} className="flex flex-wrap items-baseline gap-1.5 text-xs">
                      <Badge tone="risk"><bdi>{ev.flag}</bdi></Badge>
                      <q dir="auto" className="text-ink-3">{ev.snippet}</q>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </motion.li>
        ))}
      </AnimatePresence>
      <li ref={endRef} aria-hidden />
    </ol>
  );
}
