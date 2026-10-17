"use client";

/**
 * PrintableDocument.tsx — A4 print layout for a trade document (/print?run=…&doc=…), bilingual labels (EN / AR),
 * "DRAFT" watermark until the reply is approved, checksum in the footer. "Print / save as PDF" uses the browser, which
 * shapes Arabic correctly and needs no PDF library on the server.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Printer } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type TradeDocument } from "@/lib/api";
import { getDictionary } from "@/i18n/dictionaries";
import { Button } from "@/components/ui/primitives";

const EN = getDictionary("en").doc;
const AR = getDictionary("ar").doc;
const fmt = (n: unknown, digits = 2) =>
  typeof n === "number" ? n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }) : "—";

function Label({ k }: { k: keyof typeof EN }) {
  return <span className="block leading-tight">{EN[k]}<span className="block text-[0.85em] text-ink-3" lang="ar" dir="rtl">{AR[k]}</span></span>;
}

export function PrintableDocument() {
  const { t, locale } = useI18n();
  const params = useSearchParams();
  const runId = params.get("run");
  const kind = params.get("doc") as TradeDocument["kind"] | null;
  const [doc, setDoc] = useState<TradeDocument | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !kind) return;
    api.documents(runId).then((all) => setDoc(all[kind] ?? null)).catch((e) => setError((e as Error).message));
  }, [runId, kind]);

  if (error || !runId || !kind) return <p className="py-16 text-center text-sm text-risk">{error ?? t.runDetail.notFound}</p>;
  if (!doc) return <p className="py-16 text-center text-sm text-ink-3">{t.common.loading}</p>;
  if (!doc.available) return <p className="py-16 text-center text-sm text-ink-3">{t.doc.notAvailable}: {doc.reason}</p>;
  const isOrigin = doc.kind === "origin_checklist";
  const isPacking = doc.kind === "packing_list";

  return (
    <div className="mx-auto max-w-[210mm] space-y-4">
      <div className="flex items-center justify-between print:hidden">
        <Link href={`/${locale}/run?id=${encodeURIComponent(runId)}`} className="text-sm text-accent hover:underline">← {t.runDetail.back}</Link>
        <Button onClick={() => window.print()}><Printer className="h-4 w-4" aria-hidden />{t.runDetail.print}</Button>
      </div>

      <article dir="ltr" className="relative overflow-hidden rounded-lg border border-line bg-white p-8 text-[13px] text-black shadow-card print:rounded-none print:border-0 print:p-0 print:shadow-none">
        {doc.status === "draft" && (
          <div aria-hidden className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <span className="-rotate-[30deg] text-7xl font-black tracking-widest text-black/10">DRAFT · مسودة</span>
          </div>
        )}
        <header className="flex items-start justify-between gap-6 border-b border-black/20 pb-4">
          <div>
            <h1 className="text-xl font-bold">{doc.title}</h1>
            <p className="text-base" lang="ar" dir="rtl">{doc.title_ar}</p>
            {doc.status === "draft" && <p className="mt-1 text-xs font-semibold text-red-700">{EN.draft} · <span lang="ar">{AR.draft}</span></p>}
          </div>
          <dl className="grid grid-cols-[auto_auto] gap-x-4 gap-y-1 text-end">
            <dt><Label k="number" /></dt><dd className="font-mono">{doc.number}</dd>
            <dt><Label k="date" /></dt><dd>{doc.date}</dd>
          </dl>
        </header>

        <section className="grid grid-cols-2 gap-6 border-b border-black/20 py-4">
          <div><Label k="seller" /><p className="mt-1 font-semibold">{doc.seller.name}</p><p>{doc.seller.country} · {doc.seller.port_of_loading}</p></div>
          <div><Label k="buyer" /><p className="mt-1 font-semibold" dir="auto">{doc.buyer.name}</p><p>{doc.buyer.country}</p></div>
        </section>

        <table className="mt-4 w-full border-collapse">
          <thead>
            <tr className="border-b border-black/30 text-start align-bottom">
              <th className="py-2 pe-2 text-start"><Label k="description" /></th>
              {isOrigin ? (
                <><th className="py-2 pe-2 text-start"><Label k="candidates" /></th><th className="py-2 text-start"><Label k="rule" /></th></>
              ) : (
                <>
                  {(doc.kind === "proforma_invoice" || isPacking) && <th className="py-2 pe-2 text-start"><Label k="hs" /></th>}
                  <th className="py-2 pe-2 text-end"><Label k="qty" /></th>
                  {isPacking ? <th className="py-2 text-end"><Label k="grossKg" /></th> : (
                    <><th className="py-2 pe-2 text-end"><Label k="unitPrice" /></th><th className="py-2 text-end"><Label k="amount" /></th></>
                  )}
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {(doc.lines ?? []).map((line, i) => (
              <tr key={i} className="border-b border-black/10 align-top">
                <td className="py-2 pe-2" dir="auto">{line.description}</td>
                {isOrigin ? (
                  <>
                    <td className="py-2 pe-2 font-mono text-xs">{(line.hs_candidates ?? []).filter(Boolean).join(", ") || "—"}{line.needs_human_check ? ` (${EN.humanCheck})` : ""}</td>
                    <td className="py-2 text-xs">{line.rule ?? "—"}{line.rule_ref ? ` [${line.rule_ref}]` : ""}
                      {(line.evidence_needed ?? []).length > 0 && <ul className="mt-1 list-disc ps-4">{line.evidence_needed!.map((e, j) => <li key={j}>{e}</li>)}</ul>}
                    </td>
                  </>
                ) : (
                  <>
                    {(doc.kind === "proforma_invoice" || isPacking) && <td className="py-2 pe-2 font-mono">{line.hs_code ?? "—"}</td>}
                    <td className="py-2 pe-2 text-end">{fmt(line.quantity, 0)}</td>
                    {isPacking ? <td className="py-2 text-end">{fmt(line.gross_kg)}</td> : (
                      <><td className="py-2 pe-2 text-end">{fmt(line.unit_price)}</td><td className="py-2 text-end">{fmt(line.amount)}</td></>
                    )}
                  </>
                )}
              </tr>
            ))}
            {(doc.charges ?? []).map((c, i) => (
              <tr key={`c${i}`} className="border-b border-black/10 text-black/70">
                <td className="py-1.5 pe-2" colSpan={doc.kind === "proforma_invoice" ? 4 : 3}>{c.description}</td>
                <td className="py-1.5 text-end">{fmt(c.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {doc.totals && !isOrigin && (
          <dl className="ms-auto mt-4 grid w-72 grid-cols-[1fr_auto] gap-x-4 gap-y-1">
            {isPacking ? (
              <><dt><Label k="grossKg" /></dt><dd className="text-end font-semibold">{fmt(doc.totals.gross_kg)}</dd></>
            ) : (
              <>
                <dt><Label k="goods" /></dt><dd className="text-end">{fmt(doc.totals.goods)}</dd>
                <dt><Label k="charges" /></dt><dd className="text-end">{fmt(doc.totals.charges)}</dd>
                <dt className="font-semibold"><Label k="total" /></dt>
                <dd className="text-end text-base font-bold">{String(doc.terms?.currency ?? "AED")} {fmt(doc.totals.total)}</dd>
              </>
            )}
          </dl>
        )}

        {doc.terms && (
          <dl className="mt-4 grid grid-cols-3 gap-4 border-t border-black/20 pt-4 text-xs">
            {"incoterm" in doc.terms && <div><Label k="incoterm" /><dd className="mt-1 font-semibold">{String(doc.terms.incoterm ?? "—")}</dd></div>}
            {"validity_days" in doc.terms && <div><Label k="validity" /><dd className="mt-1 font-semibold">{String(doc.terms.validity_days ?? "—")}</dd></div>}
            {"port_of_loading" in doc.terms && <div><Label k="port" /><dd className="mt-1 font-semibold">{String(doc.terms.port_of_loading ?? "—")}</dd></div>}
          </dl>
        )}

        {(doc.common_requirements ?? []).length > 0 && (
          <section className="mt-4 text-xs"><Label k="requirements" />
            <ul className="mt-1 list-disc ps-5">{doc.common_requirements!.filter(Boolean).map((x, i) => <li key={i}>{x}</li>)}</ul>
          </section>
        )}
        {(doc.notes ?? []).length > 0 && <ul className="mt-4 list-disc ps-5 text-xs text-black/70">{doc.notes!.map((n, i) => <li key={i}>{n}</li>)}</ul>}

        <footer className="mt-8 border-t border-black/20 pt-3 text-[10px] text-black/60">
          <p>{EN.generated} <span lang="ar" dir="rtl">{AR.generated}</span></p>
          <p className="mt-1 break-all font-mono">{EN.checksum}: {doc.checksum}</p>
        </footer>
      </article>
    </div>
  );
}
