/**
 * /[lang]/privacy — how Jisr handles personal data (summary of docs/DATA_PROTECTION.md), EN and AR.
 */

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

export const metadata: Metadata = { title: "Data protection" };

export default async function PrivacyPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const p = getDictionary(lang).privacy;
  return (
    <article className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{p.title}</h1>
        <p className="mt-1 text-sm text-ink-2">{p.intro}</p>
      </header>
      {p.sections.map((s) => (
        <section key={s.h} className="rounded-[var(--radius-card)] border border-line bg-surface p-5 shadow-card">
          <h2 className="font-semibold text-ink">{s.h}</h2>
          <ul className="mt-2 list-disc space-y-1 ps-5 text-sm text-ink-2">
            {s.items.map((it) => <li key={it}>{it}</li>)}
          </ul>
        </section>
      ))}
      <p className="text-xs text-ink-3">{p.note}</p>
    </article>
  );
}
