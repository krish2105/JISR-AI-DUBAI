"use client";

/**
 * ImpactPanel.tsx — What Jisr did for the business, from the run records (GET /impact).
 *
 * Honesty rules on this page: measured numbers and estimates are shown in separate sections; the estimate shows its
 * assumptions and their source; duty amounts are "up to" (the preferential rate still needs a human).
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type Impact } from "@/lib/api";
import { Badge, Card, CardHeader } from "@/components/ui/primitives";

const fmt = (n: number | null | undefined, digits = 0) =>
  n == null ? "—" : n.toLocaleString("en-US", { maximumFractionDigits: digits });

export function ImpactPanel() {
  const { t, locale } = useI18n();
  const g = t.impact;
  const [data, setData] = useState<Impact | null>(null);
  const [days, setDays] = useState(30);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.impact(days).then(setData).catch(() => setError(t.common.error));
  }, [days, t.common.error]);

  const m = data?.measured;
  const cards = m ? [
    { label: g.enquiries, value: fmt(m.enquiries) },
    { label: g.quotes, value: fmt(m.quotes_drafted) },
    { label: g.sent, value: fmt(m.approved_and_sent) },
    { label: g.agentTime, value: m.median_agent_seconds == null ? "—" : `${fmt(m.median_agent_seconds, 1)} s` },
    { label: g.ack, value: m.median_seconds_to_acknowledge == null ? "—" : `${fmt(m.median_seconds_to_acknowledge, 1)} s` },
    { label: g.risks, value: fmt(m.risks_caught), tone: "text-risk" },
    { label: g.duty, value: `≤ AED ${fmt(m.duty_upto_aed)}`, tone: "text-ok" },
  ] : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{g.title}</h1>
          <p className="mt-1 max-w-3xl text-sm text-ink-2">{g.subtitle}</p>
        </div>
        <div role="group" aria-label={g.period} className="inline-flex rounded-full border border-line p-0.5 text-xs">
          {[7, 30, 90].map((d) => (
            <button key={d} type="button" aria-pressed={d === days} onClick={() => setDays(d)}
              className={d === days ? "rounded-full bg-accent px-3 py-1 text-white" : "px-3 py-1 text-ink-3"}>
              <bdi>{d}</bdi> {g.days}
            </button>
          ))}
        </div>
      </div>
      {error && <p className="text-sm text-risk">{error}</p>}

      <section>
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-ink-3">{g.measured}</h2>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
          {cards.map((c) => (
            <div key={c.label} className="rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3 shadow-card">
              <dt className="text-xs text-ink-3">{c.label}</dt>
              <dd className={`mt-1 text-xl font-semibold tabular-nums ${c.tone ?? "text-ink"}`}><bdi>{c.value}</bdi></dd>
            </div>
          ))}
        </dl>
      </section>

      {data && (
        <Card>
          <CardHeader title={g.estimated} aside={<Badge tone="warn">{g.assumption}</Badge>} />
          <div className="p-4 text-sm">
            <p className="text-2xl font-semibold text-ink"><bdi>{fmt(data.estimated.minutes_saved)}</bdi> {g.minutes}</p>
            <p className="mt-1 text-ink-2">
              {g.formula} (<bdi>{data.estimated.assumptions.manual_minutes_per_quote}</bdi> − <bdi>{data.estimated.assumptions.review_minutes_per_quote}</bdi> {g.minutesShort}).
              {" "}{g.source}: {data.estimated.assumptions.source}
            </p>
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title={g.ledger} />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-ink-3">
              <tr className="border-b border-line">
                {[g.when, g.kind, g.buyer, g.status, g.total, g.dutyCol, g.risksCol, g.secs].map((h) => (
                  <th key={h} className="px-3 py-2 text-start font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data?.ledger.map((r) => (
                <tr key={r.run_id} className="border-b border-line last:border-0">
                  <td className="px-3 py-2"><Link className="text-accent hover:underline" href={`/${locale}/demo?run=${r.run_id}`}>
                    <bdi>{new Date(r.created_at).toLocaleString()}</bdi></Link></td>
                  <td className="px-3 py-2"><Badge tone="neutral">{r.kind}</Badge></td>
                  <td className="px-3 py-2" dir="auto">{r.buyer ?? "—"}</td>
                  <td className="px-3 py-2">{t.status[r.status] ?? r.status}</td>
                  <td className="px-3 py-2 tabular-nums"><bdi>{r.quote_total_aed == null ? "—" : `AED ${fmt(r.quote_total_aed, 2)}`}</bdi></td>
                  <td className="px-3 py-2 tabular-nums"><bdi>{r.duty_upto_aed == null ? "—" : `≤ ${fmt(r.duty_upto_aed)}`}</bdi></td>
                  <td className="px-3 py-2 tabular-nums"><bdi>{r.risks}</bdi></td>
                  <td className="px-3 py-2 tabular-nums"><bdi>{r.agent_seconds ?? "—"}</bdi></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
