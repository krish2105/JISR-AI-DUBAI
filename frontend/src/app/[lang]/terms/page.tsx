/**
 * /[lang]/terms — draft terms of service for the pilot (Phase 19), EN and AR. Not legal advice.
 */

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

export const metadata: Metadata = { title: "Terms" };

export default async function TermsPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const t = getDictionary(lang).terms;
  return (
    <article className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t.title}</h1>
        <p className="mt-2 rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">{t.draft}</p>
      </header>
      {t.sections.map((s) => (
        <section key={s.h} className="rounded-[var(--radius-card)] border border-line bg-surface p-5 shadow-card">
          <h2 className="font-semibold text-ink">{s.h}</h2>
          <ul className="mt-2 list-disc space-y-1 ps-5 text-sm text-ink-2">
            {s.items.map((it) => <li key={it}>{it}</li>)}
          </ul>
        </section>
      ))}
    </article>
  );
}
