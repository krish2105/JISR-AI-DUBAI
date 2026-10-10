"use client";

/**
 * ChecksCard.tsx — Two deterministic checks side by side: document consistency findings and buyer trust signals.
 *
 * Why: both are "risks caught" the owner must see before anything ships. Findings show the field, what was expected,
 * what was found and how to fix it (with the treaty article when the CEPA preference is at stake). Buyer signals are
 * shown with their evidence and why they matter; positive signals are shown too, so the picture is balanced.
 */

import { AlertTriangle, CheckCircle2, FileSearch, UserCheck } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import type { BuyerSignal, DocIssue } from "@/lib/api";
import { Badge, Card, CardHeader } from "@/components/ui/primitives";

const TONE = { high: "risk", medium: "warn", low: "neutral", positive: "ok", info: "neutral" } as const;

export function ChecksCard({ issues, signals }: { issues: DocIssue[]; signals: BuyerSignal[] }) {
  const { t } = useI18n();
  const r = t.demo.result;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader
          title={<span className="inline-flex items-center gap-2"><FileSearch className="h-4 w-4 text-accent" aria-hidden />{r.docChecks}</span>}
          aside={<Badge tone={issues.length ? "risk" : "ok"}><bdi>{issues.length}</bdi></Badge>}
        />
        <div className="space-y-2 p-4 text-sm">
          {issues.length === 0 ? (
            <p className="flex gap-2 text-ink-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />{r.docChecksOk}</p>
          ) : (
            issues.map((f) => (
              <div key={`${f.type}-${f.field}`} className="rounded-lg border border-line p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-risk" aria-hidden />
                  <span className="font-medium text-ink"><bdi>{f.type}</bdi></span>
                  <Badge tone={TONE[f.severity]}>{f.severity}</Badge>
                  <code className="text-xs text-ink-3"><bdi>{f.field}</bdi></code>
                </div>
                <p className="mt-1 text-ink-2" dir="auto">{f.message}</p>
                <p className="mt-1 text-xs text-ink-2"><span className="font-medium">{r.fix}:</span> {f.fix}</p>
                {f.citation && (
                  <p className="mt-1 text-xs text-ink-3">
                    {f.citation.document}{f.citation.section ? ` · ${f.citation.section}` : ""}
                    {f.citation.page ? <> · <bdi>p. {f.citation.page}</bdi></> : null}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </Card>
      <Card>
        <CardHeader
          title={<span className="inline-flex items-center gap-2"><UserCheck className="h-4 w-4 text-accent" aria-hidden />{r.trust}</span>}
          aside={<span className="text-xs text-ink-3">{r.trustNote}</span>}
        />
        <ul className="space-y-2 p-4 text-sm">
          {signals.map((s) => (
            <li key={s.signal} className="flex gap-2">
              <Badge tone={TONE[s.risk]}>{s.risk}</Badge>
              <div>
                <span className="font-medium text-ink"><bdi>{s.signal}</bdi></span>
                <span className="text-ink-3"> · <bdi dir="auto">{s.evidence}</bdi></span>
                <p className="text-xs text-ink-2">{s.why}</p>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
