"use client";

/**
 * DutyCard.tsx — The CEPA duty analysis: per line HS candidate, MFN duty, origin rule, evidence, and sources.
 *
 * Why: this is the "wow" of the demo, so it must also be the most honest screen. Every fact links to its
 * official source (document, issuer, date, page), the saving is shown as "up to" with its condition, and anything
 * uncertain carries a "needs human check" badge.
 */

import { BookOpen, FileCheck2 } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import type { Citation, DutyAnalysis } from "@/lib/api";
import { Badge, Card, CardHeader } from "@/components/ui/primitives";

const aed = (n: number) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function SourceItem({ c }: { c: Citation }) {
  return (
    <li className="text-xs text-ink-2">
      <span className="font-medium text-ink">{c.document}</span>
      {c.issuer ? <> · {c.issuer}</> : null}
      {c.document_date ? <> · <bdi>{c.document_date}</bdi></> : null}
      {c.page_label || c.page ? <> · <bdi>{c.page_label ?? `p. ${c.page}`}</bdi></> : null}
      {c.section && c.kind !== "tariff" ? <> · {c.section}</> : null}
      {c.excerpt ? <q dir="auto" className="mt-0.5 block text-ink-3">{c.excerpt}</q> : null}
    </li>
  );
}

export function DutyCard({ duty, docs }: {
  duty: DutyAnalysis;
  docs?: { documents: { document: string; citation: Citation | null }[]; note?: string } | null;
}) {
  const { t } = useI18n();
  const r = t.demo.result;
  if (duty.status !== "analysed") {
    return (
      <Card className="p-4 text-sm text-ink-2">
        <span className="font-medium text-ink">{r.cepa}: </span>{r.kbMissing}
      </Card>
    );
  }
  const citations = Object.values(duty.citations ?? {});
  return (
    <Card>
      <CardHeader
        title={<span className="inline-flex items-center gap-2"><FileCheck2 className="h-4 w-4 text-accent" aria-hidden />{r.cepa}</span>}
        aside={
          duty.max_potential_saving_aed != null && (
            <Badge tone="ok" title={duty.preferential_rate}>
              {r.upTo} <bdi>AED {aed(duty.max_potential_saving_aed)}</bdi>
            </Badge>
          )
        }
      />
      <div className="space-y-3 p-4 text-sm">
        <p className="text-xs text-ink-3">{r.upTo} AED · {r.savingNote}</p>
        {duty.lines.map((ln) => {
          const top = ln.hs_candidates?.[0];
          return (
            <div key={ln.description} className="rounded-lg border border-line p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-ink">{ln.description}</span>
                {ln.needs_human_check && <Badge tone="warn">{t.demo.needsHumanCheck}</Badge>}
              </div>
              <dl className="mt-2 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
                {top && (
                  <div><dt className="text-ink-3">{r.hsLikely}</dt>
                    <dd><bdi>{top.best_line}</bdi> · {Math.round((ln.hs_confidence ?? 0) * 100)}% {r.confidence}
                      <span className="block text-ink-3">{top.best_line_desc.replace(/^HS \d+ /, "").slice(0, 90)}</span>
                      {ln.catalogue_hint && ln.hint_agrees === false && (
                        <span className="block text-warn">{r.catalogueDiffers} <bdi>{ln.catalogue_hint}</bdi></span>
                      )}
                    </dd></div>
                )}
                <div><dt className="text-ink-3">{r.mfn}</dt>
                  <dd><bdi>{ln.mfn_duty_pct ?? "—"}%</bdi>{ln.mfn_duty_aed != null && <> · <bdi>AED {aed(ln.mfn_duty_aed)}</bdi></>}</dd></div>
                {ln.rule && (
                  <div><dt className="text-ink-3">{r.rule}</dt>
                    <dd><bdi>{ln.rule.text}</bdi> · {ln.rule.scope} · <bdi>{ln.rule.page_label}</bdi></dd></div>
                )}
              </dl>
              {(ln.evidence_needed?.length ?? 0) > 0 && (
                <div className="mt-2 text-xs">
                  <span className="text-ink-3">{r.evidence}:</span>
                  <ul className="ms-4 list-disc text-ink-2">{ln.evidence_needed!.map((e) => <li key={e}>{e}</li>)}</ul>
                </div>
              )}
            </div>
          );
        })}
        {docs && docs.documents.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-3">{r.docsPack}</p>
            <ul className="space-y-1">
              {docs.documents.map((d) => (
                <li key={d.document} className="text-xs">
                  <span className="font-medium text-ink">{d.document}</span>
                  {d.citation && <span className="text-ink-3"> — {d.citation.document}{d.citation.page ? `, p. ${d.citation.page}` : ""}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
        <details className="text-xs">
          <summary className="cursor-pointer text-accent"><BookOpen className="me-1 inline h-3.5 w-3.5" aria-hidden />{r.sources} ({citations.length})</summary>
          <ul className="mt-2 space-y-2">{citations.map((c) => <SourceItem key={c.chunk_id} c={c} />)}</ul>
        </details>
      </div>
    </Card>
  );
}
