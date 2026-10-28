"use client";

/**
 * BillingTab.tsx — plan and this month's usage; owners can switch plan (test mode: recorded, no payment) (Phase 19).
 */

import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type BillingUsage } from "@/lib/api";
import plansData from "@/data/plans.json";
import { Button, cx } from "@/components/ui/primitives";
import { useCan } from "@/components/auth/SessionProvider";

function Meter({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = Math.min(100, Math.round((used / Math.max(1, limit)) * 100));
  return (
    <div>
      <div className="flex justify-between text-sm"><span>{label}</span><bdi>{used} / {limit}</bdi></div>
      <div className="mt-1 h-2 rounded-full bg-muted" role="meter" aria-valuenow={used} aria-valuemax={limit} aria-label={label}>
        <div className={cx("h-2 rounded-full", pct >= 90 ? "bg-risk" : pct >= 70 ? "bg-warn" : "bg-accent")} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function BillingTab() {
  const { t } = useI18n();
  const b = t.billing;
  const canChange = useCan("billing.manage");
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.billing().then(setUsage).catch((e) => setError((e as Error).message));
  }, []);

  if (error) return <p className="text-sm text-risk" dir="auto">{error}</p>;
  if (!usage) return <p className="text-sm text-ink-3">{t.common.loading}</p>;
  return (
    <div className="space-y-5">
      <p className="rounded-lg bg-sand-soft px-3 py-2 text-xs text-sand">{b.testMode}</p>
      <p className="text-sm">{b.current}: <span className="font-semibold">{usage.plan_name}</span></p>
      <div className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-3">{b.usage}</p>
        <Meter label={b.enquiries} used={usage.quotes.used} limit={usage.quotes.limit} />
        <Meter label={b.seats} used={usage.seats.used} limit={usage.seats.limit} />
        <p className="text-xs text-ink-3">{b.resets}</p>
      </div>
      {canChange ? (
        <div className="flex flex-wrap gap-2">
          {Object.entries(plansData.plans).filter(([key]) => key !== usage.plan).map(([key, plan]) => (
            <Button key={key} variant="secondary" onClick={() => api.changePlan(key).then(setUsage).catch((e) => setError((e as Error).message))}>
              {b.change} {plan.name}
            </Button>
          ))}
        </div>
      ) : <p className="text-xs text-ink-3">{b.ownerOnly}</p>}
    </div>
  );
}
