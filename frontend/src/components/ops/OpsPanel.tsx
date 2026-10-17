"use client";

/**
 * OpsPanel.tsx — /ops: volume, speed, errors and model cost for owners and admins (Phase 14).
 */

import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type OpsMetrics } from "@/lib/api";
import { Badge, Card, CardHeader } from "@/components/ui/primitives";

const usd = (n: number | null | undefined) => (n == null ? "—" : `$${n.toFixed(n < 1 ? 4 : 2)}`);

export function OpsPanel() {
  const { t } = useI18n();
  const o = t.ops;
  const [days, setDays] = useState(7);
  const [m, setM] = useState<OpsMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.opsMetrics(days).then(setM).catch((e) => setError((e as Error).message));
  }, [days]);

  if (error) return <p className="py-16 text-center text-sm text-risk">{error}</p>;
  if (!m) return <p className="py-16 text-center text-sm text-ink-3">{t.common.loading}</p>;
  const tiles = [
    { label: o.runs, value: String(m.runs) },
    { label: o.p50, value: m.agent_seconds.p50 == null ? "—" : `${m.agent_seconds.p50} s` },
    { label: o.p95, value: m.agent_seconds.p95 == null ? "—" : `${m.agent_seconds.p95} s` },
    { label: o.errors, value: `${(m.error_rate * 100).toFixed(1)}%` },
    { label: o.cost, value: usd(m.cost.total_usd) },
    { label: o.perQuote, value: usd(m.cost.per_quote_usd) },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{o.title}</h1>
          <p className="mt-1 max-w-3xl text-sm text-ink-2">{o.subtitle}</p>
        </div>
        <select aria-label="days" value={days} onChange={(e) => setDays(Number(e.target.value))}
          className="rounded-lg border border-line bg-surface px-3 py-2 text-sm">
          {[1, 7, 30].map((d) => <option key={d} value={d}>{d}d</option>)}
        </select>
      </div>
      <div className="flex flex-wrap gap-2 text-xs">
        <Badge>{o.profile}: {m.llm_profile}</Badge>
        <Badge>{o.prices} <bdi>{m.cost.prices_as_of}</bdi></Badge>
        <Badge tone={m.budget.fallback_active ? "risk" : "neutral"}>
          {o.budget}: {m.budget.daily_token_budget ? <bdi>{m.budget.used_today.toLocaleString()} / {m.budget.daily_token_budget.toLocaleString()}</bdi> : o.unlimited}
        </Badge>
        {m.budget.fallback_active && <Badge tone="risk">{o.fallback}</Badge>}
        <Badge tone={m.approvals.pending ? "warn" : "ok"}>
          {o.pending}: <bdi>{m.approvals.pending}</bdi>{m.approvals.oldest_minutes != null && <> · {o.oldest} <bdi>{m.approvals.oldest_minutes}</bdi> min</>}
        </Badge>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {tiles.map((tile) => (
          <Card key={tile.label} className="p-4">
            <p className="text-xs text-ink-3">{tile.label}</p>
            <p className="mt-1 text-xl font-semibold"><bdi>{tile.value}</bdi></p>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader title={o.perDay} />
        {Object.keys(m.per_day).length === 0 ? <p className="p-4 text-sm text-ink-3">{o.none}</p> : (
          <table className="w-full text-sm">
            <thead className="text-xs text-ink-3"><tr className="border-b border-line">
              <th className="px-4 py-2 text-start font-medium">{o.day}</th><th className="px-4 py-2 text-end font-medium">{o.runs}</th>
              <th className="px-4 py-2 text-end font-medium">{o.tokens}</th><th className="px-4 py-2 text-end font-medium">{o.cost}</th>
            </tr></thead>
            <tbody>
              {Object.entries(m.per_day).map(([day, d]) => (
                <tr key={day} className="border-b border-line/60">
                  <td className="px-4 py-2"><bdi>{day}</bdi></td><td className="px-4 py-2 text-end"><bdi>{d.runs}</bdi></td>
                  <td className="px-4 py-2 text-end"><bdi>{d.tokens.toLocaleString()}</bdi></td><td className="px-4 py-2 text-end"><bdi>{usd(d.cost_usd)}</bdi></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
