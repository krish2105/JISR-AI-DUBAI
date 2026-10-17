"use client";

/**
 * OwnerDashboard.tsx — /today: what needs the owner now, the last 24 hours in numbers, alerts and recent enquiries
 * (Phase 16). Built from existing endpoints only; every number links to where it comes from.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, Inbox } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type Approval, type AutonomousLog, type Governance, type Impact } from "@/lib/api";
import { Badge, Card, CardHeader } from "@/components/ui/primitives";
import { useSession } from "@/components/auth/SessionProvider";

type Runs = Awaited<ReturnType<typeof api.runs>>;

export function OwnerDashboard() {
  const { t, locale } = useI18n();
  const h = t.home;
  const { me } = useSession();
  const [pending, setPending] = useState<Approval[] | null>(null);
  const [impact, setImpact] = useState<Impact | null>(null);
  const [auto, setAuto] = useState<AutonomousLog | null>(null);
  const [gov, setGov] = useState<Governance | null>(null);
  const [fallback, setFallback] = useState(false);
  const [runs, setRuns] = useState<Runs>([]);

  useEffect(() => {
    api.approvals("pending").then(setPending).catch(() => setPending([]));
    api.impact(1).then(setImpact).catch(() => undefined);
    api.autonomous(24).then(setAuto).catch(() => undefined);
    api.governance().then(setGov).catch(() => undefined);
    api.health().then((x) => setFallback(!!x.budget?.fallback_active)).catch(() => undefined);
    api.runs(6).then(setRuns).catch(() => undefined);
  }, []);

  const high = pending?.filter((a) => a.risk === "high").length ?? 0;
  const m = impact?.measured;
  const tiles = [
    { label: h.enquiries, value: m?.enquiries, href: "impact" },
    { label: h.quotes, value: m?.quotes_drafted, href: "impact" },
    { label: h.sent, value: m?.approved_and_sent, href: "audit" },
    { label: h.blocked, value: m?.blocked_by_policy, href: "governance" },
    { label: h.alone, value: auto?.done_alone, href: "governance" },
  ];
  const alerts = [gov?.kill_switch && h.killOn, fallback && h.budget].filter(Boolean) as string[];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{h.title}</h1>
        <p className="mt-1 text-sm text-ink-2">{h.subtitle}</p>
      </div>
      {me?.onboarding && !me.onboarding.done && (
        <Link href={`/${locale}/onboarding`} className="block rounded-lg bg-accent-soft px-4 py-3 text-sm font-medium text-accent">{h.setup} →</Link>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title={<span className="inline-flex items-center gap-2"><Inbox className="h-4 w-4" aria-hidden />{h.needsYou}</span>}
            aside={pending && pending.length > 0 && <Badge tone={high ? "risk" : "warn"}><bdi>{pending.length}</bdi>{high ? ` · ${high} ${h.high}` : ""}</Badge>} />
          <div className="p-4">
            {pending === null ? <p className="text-sm text-ink-3">{t.common.loading}</p> : pending.length === 0 ? (
              <p className="flex items-center gap-2 text-sm text-ok"><CheckCircle2 className="h-4 w-4" aria-hidden />{h.noneWaiting}</p>
            ) : (
              <ul className="space-y-2">
                {pending.slice(0, 5).map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-3 text-sm">
                    <span className="truncate" dir="auto">{a.title}</span>
                    <Badge tone={a.risk === "high" ? "risk" : a.risk === "medium" ? "warn" : "ok"}>{t.risk[a.risk]}</Badge>
                  </li>
                ))}
              </ul>
            )}
            <Link href={`/${locale}/approvals`} className="mt-4 inline-block text-sm font-medium text-accent hover:underline">{h.openInbox} →</Link>
          </div>
        </Card>
        <Card>
          <CardHeader title={<span className="inline-flex items-center gap-2"><AlertTriangle className="h-4 w-4" aria-hidden />{h.alerts}</span>} />
          <div className="space-y-2 p-4 text-sm">
            {alerts.length === 0 ? <p className="text-ink-3">{h.allClear}</p> : alerts.map((a) => <p key={a} className="text-risk">{a}</p>)}
          </div>
        </Card>
      </div>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-ink-2">{h.today}</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {tiles.map((tile) => (
            <Link key={tile.label} href={`/${locale}/${tile.href}`} className="rounded-[var(--radius-card)] border border-line bg-surface p-4 shadow-card hover:border-accent/40">
              <p className="text-xs text-ink-3">{tile.label}</p>
              <p className="mt-1 text-2xl font-semibold"><bdi>{tile.value ?? "—"}</bdi></p>
            </Link>
          ))}
        </div>
      </section>

      <Card>
        <CardHeader title={h.recent} />
        <ul className="divide-y divide-line">
          {runs.map((r) => (
            <li key={r.id}>
              <Link href={`/${locale}/run?id=${r.id}`} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm hover:bg-muted">
                <bdi className="font-mono text-xs">{r.id}</bdi>
                <span className="text-ink-3">{r.channel}</span>
                <Badge tone={r.status === "sent" ? "ok" : r.status === "blocked" ? "risk" : "accent"}>{t.status[r.status] ?? r.status}</Badge>
                <span className="text-xs text-ink-3"><bdi>{new Date(r.created_at).toLocaleString(locale)}</bdi></span>
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
