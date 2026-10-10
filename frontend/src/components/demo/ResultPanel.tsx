"use client";

/**
 * ResultPanel.tsx — What the agents produced: the quote table, any blocked action, and the
 * draft waiting for approval (approve/reject right here, or in the inbox).
 *
 * Data: once governance finishes, we fetch the run detail (quote, drafts) and its approvals.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type Approval, type RunDetail } from "@/lib/api";
import type { RunView } from "@/lib/runView";
import { ApprovalCard } from "@/components/approvals/ApprovalCard";
import dynamic from "next/dynamic";
import { use3D } from "@/components/three/use3D";
import type { DraftDocs } from "@/components/three/DocPack3D";
import { ChecksCard } from "./ChecksCard";

const DocPack3D = dynamic(() => import("@/components/three/DocPack3D"), { ssr: false });
import { DutyCard } from "./DutyCard";
import { Badge, Card, CardHeader } from "@/components/ui/primitives";

const aed = (n: number) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function ResultPanel({ runId, view }: { runId: string; view: RunView }) {
  const { t, locale } = useI18n();
  const r = t.demo.result;
  const [run, setRun] = useState<RunDetail | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const three = use3D();

  // Load the results once the governance gate has decided (the quote and drafts exist by then).
  useEffect(() => {
    if (!view.governanceFinished) return;
    let cancelled = false;
    Promise.all([api.run(runId), api.approvals("all")]).then(([detail, all]) => {
      if (cancelled) return;
      setRun(detail);
      setApprovals(all.filter((a) => a.run_id === runId));
    });
    return () => {
      cancelled = true;
    };
  }, [runId, view.governanceFinished]);

  const quote = run?.state.quote;

  return (
    <div className="space-y-4">
      {view.blocked.map((b) => (
        <Card key={b.seq} className="border-risk/40 bg-risk-soft">
          <div className="flex gap-3 p-4">
            <ShieldAlert className="mt-0.5 h-6 w-6 shrink-0 text-risk" aria-hidden />
            <div className="space-y-1 text-sm">
              <p className="font-semibold text-risk">{r.blockedTitle}: {String(b.payload.title ?? "")}</p>
              <p className="text-ink-2">{r.blockedBody}</p>
              <p className="text-ink-2">
                <bdi>{((b.payload.rule_ids as string[]) ?? []).join(", ")}</bdi> —{" "}
                {((b.payload.reasons as string[]) ?? [])[0]}
              </p>
              <Link href={`/${locale}/audit`} className="inline-block font-medium text-accent underline-offset-4 hover:underline">
                {r.openAudit}
              </Link>
            </div>
          </div>
        </Card>
      ))}

      {quote && quote.lines.length > 0 && (
        <Card>
          <CardHeader
            title={<>{r.quote} · <bdi>{quote.incoterm}</bdi>{quote.incoterm_assumed && <span className="text-ink-3"> ({r.assumed})</span>}</>}
            aside={
              <Badge tone={quote.fx?.stale ? "warn" : "neutral"} title={quote.fx?.source ?? quote.fx_source}>
                {r.fxFrom} <bdi>1 INR = {quote.fx_inr_to_aed} AED{quote.fx?.rate_date ? ` · ${quote.fx.rate_date}` : ""}</bdi>
              </Badge>
            }
          />
          {(quote.pricing_flags?.length ?? 0) > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 border-b border-line bg-warn-soft px-4 py-2 text-xs">
              <span className="font-medium text-warn">{r.review}:</span>
              {quote.pricing_flags!.map((f) => <Badge key={f} tone="warn"><bdi>{f}</bdi></Badge>)}
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-ink-3">
                <tr className="border-b border-line">
                  <th className="px-4 py-2 text-start font-medium">{r.item}</th>
                  <th className="px-4 py-2 text-end font-medium">{r.qty}</th>
                  <th className="px-4 py-2 text-end font-medium">{r.unitAed}</th>
                  <th className="px-4 py-2 text-end font-medium">{r.totalAed}</th>
                </tr>
              </thead>
              <tbody>
                {quote.lines.map((ln) => (
                  <tr key={ln.description} className="border-b border-line last:border-0">
                    <td className="px-4 py-2 text-ink">{ln.description}</td>
                    <td className="px-4 py-2 text-end tabular-nums"><bdi>{ln.quantity}</bdi></td>
                    <td className="px-4 py-2 text-end tabular-nums"><bdi>{aed(ln.unit_price_aed)}</bdi></td>
                    <td className="px-4 py-2 text-end tabular-nums"><bdi>{aed(ln.total_aed)}</bdi></td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                {(quote.charges ?? []).map((c) => (
                  <tr key={c.code} className="text-ink-2">
                    <td className="px-4 py-1.5" colSpan={3} title={c.basis}>{c.description}</td>
                    <td className="px-4 py-1.5 text-end tabular-nums"><bdi>{aed(c.total_aed)}</bdi></td>
                  </tr>
                ))}
                <tr className="font-semibold">
                  <td className="px-4 py-2" colSpan={3}>{r.totalAed}</td>
                  <td className="px-4 py-2 text-end tabular-nums"><bdi>AED {aed(quote.total_aed)}</bdi></td>
                </tr>
                <tr className="text-ink-3">
                  <td className="px-4 pb-3 text-xs" colSpan={3}>{r.totalInr} · <bdi>{quote.incoterm ?? "—"}</bdi></td>
                  <td className="px-4 pb-3 text-end text-xs tabular-nums"><bdi>INR {aed(quote.total_inr)}</bdi></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Card>
      )}

      {run?.state.duty && <DutyCard duty={run.state.duty} docs={run.state.docs} />}

      {run && (run.state.buyer_signals?.length ?? 0) > 0 && (
        <ChecksCard issues={run.state.doc_issues ?? []} signals={run.state.buyer_signals ?? []} />
      )}

      {three.enabled && Boolean(run?.state.docs?.draft) && run && (
        <Card>
          <CardHeader title={r.docPack3d} aside={<span className="text-xs text-ink-3">{r.docPack3dNote}</span>} />
          <DocPack3D draft={run.state.docs!.draft as DraftDocs} issues={run.state.doc_issues ?? []}
            titles={{ invoice: r.invoice, packing: r.packingList, coo: r.coo }} />
        </Card>
      )}

      {approvals.map((a) => (
        <ApprovalCard key={a.id} approval={a} />
      ))}
    </div>
  );
}
