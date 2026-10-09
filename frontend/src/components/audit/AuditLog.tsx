"use client";

/**
 * AuditLog.tsx — The /audit page: hash-chain status plus the latest entries.
 *
 * Why: "can we trust it?" is answered with evidence. The badge is computed by the API
 * re-hashing the whole chain; a tampered row would show "Chain broken" and its id.
 */

import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, ShieldX } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type AuditEntry, type ChainReport } from "@/lib/api";
import { Badge, Button, Card } from "@/components/ui/primitives";

export function AuditLog() {
  const { t } = useI18n();
  const [rows, setRows] = useState<AuditEntry[] | null>(null);
  const [chain, setChain] = useState<ChainReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch data; state is only set in the promise callbacks (never synchronously in an effect).
  const load = useCallback(() => {
    Promise.all([api.audit(100), api.verifyAudit()])
      .then(([entries, report]) => {
        setRows(entries);
        setChain(report);
      })
      .catch(() => setError(t.common.error));
  }, [t.common.error]);

  useEffect(load, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t.audit.title}</h1>
          <p className="mt-1 text-sm text-ink-2">{t.audit.subtitle}</p>
        </div>
        {chain && (
          <Badge tone={chain.ok ? "ok" : "risk"} className="px-3 py-1.5 text-sm">
            {chain.ok ? <ShieldCheck className="h-4 w-4" aria-hidden /> : <ShieldX className="h-4 w-4" aria-hidden />}
            {chain.ok ? t.audit.verified : `${t.audit.broken} #${chain.broken_at_id}`} · <bdi>{chain.entries}</bdi> {t.audit.entries}
          </Badge>
        )}
      </div>

      {error && (
        <p className="text-sm text-risk">
          {error} <Button variant="ghost" onClick={() => { setError(null); load(); }}>{t.common.retry}</Button>
        </p>
      )}

      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-xs text-ink-3">
            <tr className="border-b border-line">
              <th className="px-4 py-2 text-start font-medium">#</th>
              <th className="px-4 py-2 text-start font-medium">{t.audit.time}</th>
              <th className="px-4 py-2 text-start font-medium">{t.audit.actor}</th>
              <th className="px-4 py-2 text-start font-medium">{t.audit.action}</th>
              <th className="px-4 py-2 text-start font-medium">{t.audit.run}</th>
              <th className="px-4 py-2 text-start font-medium">{t.audit.hash}</th>
            </tr>
          </thead>
          <tbody>
            {rows?.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-ink-3">{t.audit.empty}</td></tr>
            )}
            {rows?.map((e) => (
              <tr key={e.id} className="border-b border-line last:border-0 odd:bg-muted/40">
                <td className="px-4 py-2 tabular-nums text-ink-3"><bdi>{e.id}</bdi></td>
                <td className="px-4 py-2 whitespace-nowrap tabular-nums"><bdi>{new Date(e.ts).toISOString().replace("T", " ").slice(0, 19)}</bdi></td>
                <td className="px-4 py-2"><bdi>{e.actor}</bdi></td>
                <td className="px-4 py-2">
                  <Badge tone={e.action.startsWith("policy.blocked") ? "risk" : e.action.includes("approved") || e.action.includes("sent") ? "ok" : "neutral"}>
                    <bdi>{e.action}</bdi>
                  </Badge>
                </td>
                <td className="px-4 py-2 font-mono text-xs text-ink-2"><bdi>{e.run_id ?? "—"}</bdi></td>
                <td className="px-4 py-2 font-mono text-xs text-ink-3" title={`prev ${e.prev_hash}`}><bdi>{e.hash.slice(0, 12)}…</bdi></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
