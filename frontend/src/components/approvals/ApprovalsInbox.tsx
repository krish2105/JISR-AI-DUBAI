"use client";

/**
 * ApprovalsInbox.tsx — The /approvals page: pending actions first, then recent decisions.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type Approval } from "@/lib/api";
import { Button } from "@/components/ui/primitives";
import { useCan } from "@/components/auth/SessionProvider";
import { ApprovalCard } from "./ApprovalCard";

export function ApprovalsInbox() {
  const { t, locale } = useI18n();
  const [items, setItems] = useState<Approval[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch data; state is only set in the promise callbacks (never synchronously in an effect).
  const [collections, setCollections] = useState<number | null>(null);
  const canCollect = useCan("collections.run");
  const load = useCallback(() => {
    api.approvals("all").then(setItems).catch(() => setError(t.common.error));
  }, [t.common.error]);

  useEffect(load, [load]);

  const pending = items?.filter((a) => a.status === "pending") ?? [];
  const decided = items?.filter((a) => a.status !== "pending").slice(0, 10) ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t.approvals.title}</h1>
          <p className="mt-1 text-sm text-ink-2">{t.approvals.subtitle}</p>
        </div>
        {canCollect && <div className="text-end">
          <Button variant="secondary" onClick={() => api.runCollections()
            .then((r) => { setCollections(r.drafted); load(); })
            .catch(() => setError(t.common.error))}>
            {t.approvals.collections}
          </Button>
          {collections !== null && (
            <p className="mt-1 text-xs text-ink-3"><bdi>{collections}</bdi> {t.approvals.collectionsDone}</p>
          )}
        </div>}
      </div>

      {error && (
        <p className="text-sm text-risk">
          {error} <Button variant="ghost" onClick={() => { setError(null); load(); }}>{t.common.retry}</Button>
        </p>
      )}
      {items === null && !error && <p className="text-sm text-ink-3">{t.common.loading}</p>}
      {items !== null && pending.length === 0 && (
        <p className="rounded-[var(--radius-card)] border border-dashed border-line p-8 text-center text-sm text-ink-3">
          {t.approvals.empty}{" "}
          <Link href={`/${locale}/demo`} className="font-medium text-accent hover:underline">{t.nav.demo}</Link>
        </p>
      )}

      <div className="space-y-4">
        {pending.map((a) => (
          <ApprovalCard key={a.id} approval={a} />
        ))}
      </div>

      {decided.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-ink-2">{t.approvals.history}</h2>
          {decided.map((a) => (
            <ApprovalCard key={a.id} approval={a} />
          ))}
        </section>
      )}
    </div>
  );
}
