"use client";

/**
 * Counters.tsx — The headline numbers of a run: risks caught, steps, pending approvals,
 * agent time and AED saved.
 *
 * Honesty rule: the duty figure is shown as "≤ AED X": the MFN duty a 0% CEPA rate would remove, computed
 * from cited tariff lines. The preferential rate itself still needs human confirmation (Annex 2B), so it is
 * never presented as a certain saving. A dash means no cited analysis was possible.
 */

import { useI18n } from "@/i18n/I18nProvider";
import type { RunView } from "@/lib/runView";
import { cx } from "@/components/ui/primitives";

export function Counters({ view, savingUpTo }: { view: RunView | null; savingUpTo?: number | null }) {
  const { t } = useI18n();
  const c = t.demo.counters;
  const items = [
    { label: c.risks, value: view ? String(view.risksCaught) : "0", tone: view && view.risksCaught > 0 ? "text-risk" : "text-ink" },
    { label: c.steps, value: view ? String(view.steps) : "0", tone: "text-ink" },
    { label: c.pending, value: view ? String(view.pendingApprovals.length) : "0", tone: view?.pendingApprovals.length ? "text-warn" : "text-ink" },
    { label: c.time, value: view?.agentSeconds != null ? `${view.agentSeconds.toFixed(1)}s` : "—", tone: "text-ink" },
    { label: c.aed, value: savingUpTo != null ? `≤ ${Math.round(savingUpTo).toLocaleString("en-US")}` : "—",
      tone: savingUpTo ? "text-ok" : "text-ink-3", note: c.aedNote },
  ];
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {items.map((item) => (
        <div key={item.label} className="rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3 shadow-card" title={item.note}>
          <dt className="text-xs text-ink-3">{item.label}</dt>
          <dd className={cx("mt-1 text-2xl font-semibold tabular-nums", item.tone)}>
            <bdi>{item.value}</bdi>
          </dd>
          {item.note && <p className="mt-0.5 text-[11px] leading-tight text-ink-3">{item.note}</p>}
        </div>
      ))}
    </dl>
  );
}
