"use client";

/**
 * RunDetail.tsx — One shareable page per enquiry (/run?id=…): results, live timeline, documents and the run's own
 * audit trail (Phase 16/17). Everything comes from the same records the dashboard already shows.
 */

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FileText, Printer, Stamp } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type AuditEntry, type RunDetail as RunRecord, type TradeDocument } from "@/lib/api";
import { deriveRunView } from "@/lib/runView";
import { useRunEvents } from "@/lib/useRunEvents";
import { Badge, Button, Card, CardHeader } from "@/components/ui/primitives";
import { useSession } from "@/components/auth/SessionProvider";
import { ResultPanel } from "@/components/demo/ResultPanel";
import { Timeline } from "@/components/demo/Timeline";

export function RunDetail() {
  const { t, locale } = useI18n();
  const r = t.runDetail;
  const id = useSearchParams().get("id");
  const { can } = useSession();
  const [run, setRun] = useState<RunRecord | null>(null);
  const [docs, setDocs] = useState<Record<string, TradeDocument> | null>(null);
  const [trail, setTrail] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [issued, setIssued] = useState<Record<string, string>>({});
  const stream = useRunEvents(id);
  const view = useMemo(() => deriveRunView(stream.events), [stream.events]);

  useEffect(() => {
    if (!id) return;
    api.run(id).then(setRun).catch(() => setError(r.notFound));
    api.documents(id).then(setDocs).catch(() => undefined);
    api.runAudit(id).then(setTrail).catch(() => undefined);
  }, [id, r.notFound, stream.done]);

  if (!id || error) return <p className="py-16 text-center text-sm text-ink-3">{error ?? r.notFound}</p>;
  const canIssue = can("drafts.edit") || can("invoices.manage");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs text-ink-3"><Link href={`/${locale}/approvals`} className="hover:underline">← {r.back}</Link></p>
          <h1 className="text-2xl font-semibold tracking-tight">{r.title} <bdi className="text-ink-3">{id}</bdi></h1>
          {run && (
            <p className="mt-1 flex flex-wrap gap-2 text-sm text-ink-2">
              <Badge tone={run.status === "sent" ? "ok" : run.status === "blocked" ? "risk" : "accent"}>{t.status[run.status] ?? run.status}</Badge>
              <span>{r.channel}: {run.channel}</span>
              <span>{r.created}: <bdi>{new Date(run.created_at).toLocaleString(locale)}</bdi></span>
            </p>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,380px)]">
        <div className="min-w-0 space-y-6">
          <ResultPanel runId={id} view={view} />
          <Card>
            <CardHeader title={<span className="inline-flex items-center gap-2"><FileText className="h-4 w-4" aria-hidden />{r.documents}</span>} />
            <p className="px-4 pt-3 text-xs text-ink-3">{r.draftNote}</p>
            <ul className="divide-y divide-line">
              {docs && Object.values(docs).map((d) => (
                <li key={d.kind} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{r.kinds[d.kind] ?? d.title}</p>
                    <p className="text-xs text-ink-3"><bdi>{d.number}</bdi>{d.available ? "" : ` · ${d.reason}`}</p>
                  </div>
                  <Badge tone={d.status === "final" ? "ok" : "warn"}>{d.status === "final" ? t.doc.final : t.doc.draft}</Badge>
                  {d.available && (
                    <Link href={`/${locale}/print?run=${encodeURIComponent(id)}&doc=${d.kind}`}
                      className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-xs hover:bg-muted">
                      <Printer className="h-3.5 w-3.5" aria-hidden />{r.print}
                    </Link>
                  )}
                  {d.available && d.status === "final" && canIssue && (
                    <Button variant="secondary" className="px-3 py-1.5 text-xs"
                      onClick={() => api.issueDocument(id, d.kind).then((x) => {
                        setIssued((m) => ({ ...m, [d.kind]: x.checksum }));
                        api.runAudit(id).then(setTrail).catch(() => undefined);
                      }).catch((e) => setError((e as Error).message))}>
                      <Stamp className="h-3.5 w-3.5" aria-hidden />{r.issue}
                    </Button>
                  )}
                  {issued[d.kind] && <p className="w-full text-xs text-ok">{r.issued} · <code dir="ltr">{issued[d.kind].slice(0, 16)}…</code></p>}
                </li>
              ))}
            </ul>
          </Card>
        </div>
        <div className="min-w-0 space-y-6">
          <Timeline events={stream.events} />
          <Card>
            <CardHeader title={r.trail} />
            <ol className="divide-y divide-line text-xs">
              {trail.map((e) => (
                <li key={e.id} className="flex flex-wrap gap-2 px-4 py-2">
                  <span className="text-ink-3"><bdi>{new Date(e.ts).toLocaleTimeString(locale)}</bdi></span>
                  <Badge>{e.action}</Badge>
                  <span className="truncate text-ink-2" dir="ltr">{e.actor}</span>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>
    </div>
  );
}
