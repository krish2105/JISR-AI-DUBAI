/**
 * /[lang]/pricing — public plans (Phase 19). Static: the data is frontend/src/data/plans.json, generated from the
 * backend's plans.yaml and checked equal by a backend test, so the page works even when the API is offline.
 */

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Check } from "lucide-react";
import plansData from "@/data/plans.json";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

export const metadata: Metadata = { title: "Pricing", description: "Monthly plans for Indian exporters selling to the UAE." };

type Plan = { name: string; price_inr_month: number; price_aed_month_reference: number; quotes_per_month: number;
  seats: number; features: string[]; note: string | null };

export default async function PricingPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const t = getDictionary(lang).pricing;
  const plans = Object.entries(plansData.plans as Record<string, Plan>);
  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">{t.title}</h1>
        <p className="mx-auto mt-2 max-w-2xl text-sm text-ink-2">{t.subtitle}</p>
        <p className="mx-auto mt-3 max-w-2xl rounded-lg bg-sand-soft px-3 py-2 text-xs text-sand">{t.hypothesis}</p>
      </header>
      <div className="grid gap-4 md:grid-cols-3">
        {plans.map(([key, plan]) => (
          <section key={key} className={`flex flex-col rounded-[var(--radius-card)] border bg-surface p-5 shadow-card ${key === "starter" ? "border-accent" : "border-line"}`}>
            <h2 className="text-lg font-semibold">{plan.name}</h2>
            <p className="mt-2">
              <span className="text-3xl font-semibold"><bdi>{plan.price_inr_month ? `₹${plan.price_inr_month.toLocaleString("en-IN")}` : t.free}</bdi></span>
              {plan.price_inr_month > 0 && <span className="text-sm text-ink-3"> {t.perMonth}</span>}
            </p>
            {plan.price_inr_month > 0 && <p className="text-xs text-ink-3">{t.aed} <bdi>{plan.price_aed_month_reference}</bdi></p>}
            {plan.note && <p className="mt-1 text-xs text-ink-3">{plan.note}</p>}
            <p className="mt-3 text-sm"><bdi className="font-semibold">{plan.quotes_per_month}</bdi> {t.quotes} · <bdi className="font-semibold">{plan.seats}</bdi> {t.seats}</p>
            <ul className="mt-3 flex-1 space-y-1.5 text-sm text-ink-2">
              {plan.features.map((f) => (
                <li key={f} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />{t.features[f] ?? f}</li>
              ))}
            </ul>
            <Link href={`/${lang}/signin`} className={`mt-5 rounded-full px-4 py-2 text-center text-sm font-medium ${key === "starter" ? "bg-accent text-accent-ink" : "border border-line hover:bg-muted"}`}>
              {key === "trial" ? t.start : t.demo}
            </Link>
          </section>
        ))}
      </div>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t.faq}</h2>
        {[[t.q1, t.a1], [t.q2, t.a2], [t.q3, t.a3]].map(([q, a]) => (
          <details key={q} className="rounded-[var(--radius-card)] border border-line bg-surface p-4">
            <summary className="cursor-pointer font-medium">{q}</summary>
            <p className="mt-2 text-sm text-ink-2">{a}</p>
          </details>
        ))}
      </section>
    </div>
  );
}
