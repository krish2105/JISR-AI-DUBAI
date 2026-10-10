/**
 * page.tsx — Landing / overview page (/en, /ar).
 *
 * A Server Component: static text in the right language, the bridge illustration, and the
 * one primary action ("Run the live demo"). The 3D bridge fades in over the SVG poster when allowed.
 */

import Link from "next/link";
import { ArrowRight, Languages, ScrollText, ShieldCheck } from "lucide-react";
import { HeroStage } from "@/components/landing/HeroStage";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { notFound } from "next/navigation";

const PILLAR_ICONS = [ShieldCheck, ScrollText, Languages];

export default async function Home({ params }: PageProps<"/[lang]">) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const t = getDictionary(lang);

  return (
    <div className="space-y-12">
      <section className="grid items-center gap-8 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-5">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-accent rtl:tracking-normal">{t.landing.eyebrow}</p>
          <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight text-ink sm:text-5xl rtl:leading-[1.35] rtl:tracking-normal">
            {t.landing.title}
          </h1>
          <p className="max-w-xl text-lg text-ink-2">{t.landing.subtitle}</p>
          <div className="flex flex-wrap gap-3">
            <Link href={`/${lang}/demo`} className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 font-medium text-accent-ink hover:opacity-90">
              {t.landing.cta} <ArrowRight className="h-4 w-4 rtl:rotate-180" aria-hidden />
            </Link>
            <Link href={`/${lang}/approvals`} className="inline-flex items-center rounded-full border border-line bg-surface px-5 py-2.5 font-medium text-ink hover:bg-muted">
              {t.landing.secondary}
            </Link>
          </div>
        </div>
        <div className="glass p-4">
          <HeroStage
            fromLabel={lang === "ar" ? "الهند" : "India"}
            toLabel={lang === "ar" ? "الإمارات" : "UAE"}
            gateLabel={t.agents.governance}
          />
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {t.landing.pillars.map((pillar, i) => {
          const Icon = PILLAR_ICONS[i];
          return (
            <div key={pillar.title} className="rounded-[var(--radius-card)] border border-line bg-surface p-5 shadow-card">
              <Icon className="h-6 w-6 text-accent" aria-hidden />
              <h2 className="mt-3 font-semibold text-ink">{pillar.title}</h2>
              <p className="mt-1 text-sm text-ink-2">{pillar.body}</p>
            </div>
          );
        })}
      </section>

      <p className="rounded-[var(--radius-card)] border border-dashed border-line px-4 py-3 text-sm text-ink-3">{t.landing.status}</p>
    </div>
  );
}
