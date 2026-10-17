"use client";

/**
 * OnboardingWizard.tsx — From sign-up to a first quote with the exporter's own products, in about five minutes
 * (Phase 15). Each step saves to the server; progress is remembered, so closing the tab loses nothing.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type BusinessProfile, type ProfileView } from "@/lib/api";
import { Button, Card, cx } from "@/components/ui/primitives";
import { useSession } from "@/components/auth/SessionProvider";
import { BusinessForm } from "@/components/settings/BusinessForm";
import { CatalogueEditor } from "@/components/settings/CatalogueEditor";
import { LogisticsForm } from "@/components/settings/LogisticsForm";

export function OnboardingWizard() {
  const { t, locale } = useI18n();
  const o = t.onboarding;
  const router = useRouter();
  const { refresh, can } = useSession();
  const [view, setView] = useState<ProfileView | null>(null);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.profile().then((v) => { setView(v); setStep(Math.min(v.onboarding.step, v.onboarding.steps.length - 1)); })
      .catch((e) => setError((e as Error).message));
  }, []);

  if (!view) return <p className="py-16 text-center text-sm text-ink-3">{error ?? t.common.loading}</p>;
  const steps = view.onboarding.steps;
  const key = steps[step];
  const editable = can("settings.business");

  async function advance(save?: () => Promise<ProfileView>) {
    setBusy(true);
    setError(null);
    try {
      if (save) setView(await save());
      const next = Math.min(step + 1, steps.length - 1);
      setView(await api.onboardingStep(next));
      setStep(next);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function firstQuote() {
    setBusy(true);
    try {
      const product = view?.profile.catalogue[0]?.name ?? "brass lamps";
      const { run_id } = await api.startRun({ message: o.testMessage.replace("{product}", product), channel: "form" });
      await api.onboardingStep(steps.length, true);
      refresh();
      router.push(`/${locale}/demo?run=${run_id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  const patch = (sections: Partial<BusinessProfile>) => advance(() => api.patchProfile(sections));

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{o.title}</h1>
        <p className="mt-1 text-sm text-ink-2">{o.subtitle}</p>
      </div>
      <ol className="flex flex-wrap gap-2" aria-label={o.title}>
        {steps.map((name, i) => (
          <li key={name}>
            <button type="button" disabled={i > view.onboarding.step} onClick={() => setStep(i)} aria-current={i === step ? "step" : undefined}
              className={cx("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs",
                i === step ? "border-accent bg-accent-soft text-accent" : i < view.onboarding.step ? "border-line text-ink" : "border-line text-ink-3")}>
              {i < view.onboarding.step && <Check className="h-3 w-3" aria-hidden />}
              <bdi>{i + 1}</bdi>. {o.steps[name] ?? name}
            </button>
          </li>
        ))}
      </ol>
      {error && <p role="alert" className="text-sm text-risk" dir="auto">{error}</p>}

      <Card className="space-y-4 p-5">
        {key === "business" && (
          <BusinessForm key="business" part="business" profile={view.profile} disabled={!editable} saveLabel={o.next} onSave={patch} />
        )}
        {key === "products" && (
          <>
            <p className="text-sm text-ink-2">{o.productsHelp}</p>
            <CatalogueEditor items={view.profile.catalogue} disabled={!editable} onChanged={setView} />
            <Button disabled={busy || view.profile.catalogue.length === 0} onClick={() => advance()}>{o.next}</Button>
          </>
        )}
        {key === "pricing" && (
          <BusinessForm key="pricing" part="pricing" profile={view.profile} disabled={!editable} saveLabel={o.next} onSave={patch} />
        )}
        {key === "logistics" && (
          <LogisticsForm logistics={view.profile.logistics} disabled={!editable} saveLabel={o.next}
            onSave={(logistics) => patch({ logistics: logistics as BusinessProfile["logistics"] })} />
        )}
        {key === "first_quote" && (
          <div className="space-y-3">
            <h2 className="text-base font-semibold">{o.firstQuoteTitle}</h2>
            <p className="text-sm text-ink-2">{o.firstQuoteBody}</p>
            <pre dir="ltr" className="whitespace-pre-wrap rounded-lg bg-muted p-3 text-sm">
              {o.testMessage.replace("{product}", view.profile.catalogue[0]?.name ?? "brass lamps")}
            </pre>
            <Button disabled={busy} onClick={firstQuote}>{o.run}</Button>
          </div>
        )}
        {step > 0 && key !== "first_quote" && (
          <Button variant="ghost" onClick={() => setStep(step - 1)}>{o.back}</Button>
        )}
      </Card>
    </div>
  );
}
