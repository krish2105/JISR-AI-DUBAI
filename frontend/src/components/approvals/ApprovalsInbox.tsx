"use client";

/**
 * ApprovalsInbox.tsx — The /approvals page: the money screen (Phase 16 v2).
 *
 * Pending actions come highest risk first, then oldest first; each says in plain words which policy rule needs a
 * human ("why this needs you") and how long it has waited. Keyboard: J/K move, A approve, R reject, E edit.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Keyboard } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type Approval } from "@/lib/api";
import { Button, cx } from "@/components/ui/primitives";
import { useCan } from "@/components/auth/SessionProvider";
import { ApprovalCard } from "./ApprovalCard";

const RISK_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

export function ApprovalsInbox() {
  const { t, locale } = useI18n();
  const [items, setItems] = useState<Approval[] | null>(null);
  const [rules, setRules] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [collections, setCollections] = useState<number | null>(null);
  const [focus, setFocus] = useState(0);
  const [now, setNow] = useState(0);                       // set when data arrives (render stays pure)
  const canCollect = useCan("collections.run");
  const listRef = useRef<HTMLDivElement>(null);

  // Fetch data; state is only set in the promise callbacks (never synchronously in an effect).
  const load = useCallback(() => {
    api.approvals("all").then((list) => { setItems(list); setNow(Date.now()); }).catch(() => setError(t.common.error));
    api.governance().then((g) => setRules(Object.fromEntries(g.policies.map((p) => [p.id, p.description]))))
      .catch(() => undefined);
  }, [t.common.error]);
  useEffect(load, [load]);

  const pending = useMemo(() => (items ?? []).filter((a) => a.status === "pending").sort((a, b) =>
    (RISK_RANK[b.risk] ?? 0) - (RISK_RANK[a.risk] ?? 0) || a.created_at.localeCompare(b.created_at)), [items]);
  const decided = items?.filter((a) => a.status !== "pending").slice(0, 10) ?? [];

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (e.metaKey || e.ctrlKey || e.altKey || !target || target.closest("input, textarea, select, [contenteditable=true]")) return;
      const key = e.key.toLowerCase();
      if (key === "j" || key === "k") {
        e.preventDefault();
        setFocus((f) => Math.max(0, Math.min(pending.length - 1, f + (key === "j" ? 1 : -1))));
        return;
      }
      const action = { a: "approve", r: "reject", e: "edit" }[key];
      const card = listRef.current?.querySelector<HTMLElement>(`[data-index="${focus}"]`);
      const button = action ? card?.querySelector<HTMLButtonElement>(`[data-action="${action}"]:not(:disabled)`) : null;
      if (button) {
        e.preventDefault();
        button.click();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pending.length, focus]);

  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-index="${focus}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focus]);

  const waited = (iso: string) => {
    const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
    return minutes < 120 ? `${minutes} ${t.inbox.minutes}` : `${Math.round(minutes / 60)} ${t.inbox.hours}`;
  };

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
      {pending.length > 0 && (
        <p className="flex flex-wrap items-center gap-3 text-xs text-ink-3">
          <span>{t.inbox.sorted}</span>
          <span className="hidden items-center gap-1 sm:inline-flex"><Keyboard className="h-3.5 w-3.5" aria-hidden />{t.inbox.shortcuts}</span>
        </p>
      )}

      <div ref={listRef} className="space-y-4">
        {pending.map((a, i) => (
          <div key={a.id} data-index={i} onFocusCapture={() => setFocus(i)} onClick={() => setFocus(i)}
            className={cx("rounded-[var(--radius-card)] transition", i === focus && "ring-2 ring-accent/50 ring-offset-2 ring-offset-bg")}>
            <ApprovalCard approval={a} onDecided={load} waited={waited(a.created_at)}
              why={a.rule_id.split(",").map((id) => rules[id.trim()]).filter((x): x is string => !!x)} />
          </div>
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
