"use client";

/**
 * UserMenu.tsx — Organisation, role and session controls in the top bar (Phase 13).
 */

import Link from "next/link";
import { ChevronDown, FlaskConical } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/primitives";
import { useSession } from "./SessionProvider";

export function UserMenu() {
  const { t, locale } = useI18n();
  const a = t.auth;
  const { status, me, adopt, signOut } = useSession();

  if (status !== "signed-in" || !me) {
    return (
      <Link href={`/${locale}/signin`}
        className="inline-flex h-9 items-center rounded-full border border-line px-3 text-sm text-ink-2 hover:bg-muted hover:text-ink">
        {a.signIn}
      </Link>
    );
  }
  const roleLabel = locale === "ar" ? me.role_label_ar : me.role_label;

  return (
    <details className="relative">
      <summary className="flex h-9 cursor-pointer list-none items-center gap-2 rounded-full border border-line px-3 text-sm text-ink hover:bg-muted">
        {me.org.is_sandbox && <FlaskConical className="h-4 w-4 text-accent" aria-label={a.sandbox} />}
        <span className="hidden max-w-[10rem] truncate sm:inline" dir="auto">{me.org.is_sandbox ? a.sandbox : me.org.name}</span>
        <Badge tone="accent">{roleLabel}</Badge>
        <ChevronDown className="h-3.5 w-3.5 text-ink-3" aria-hidden />
      </summary>
      <div className="absolute end-0 z-50 mt-2 w-72 space-y-1 rounded-[var(--radius-card)] border border-line bg-surface p-2 text-sm shadow-card">
        <div className="px-2 py-1.5">
          <p className="text-xs text-ink-3">{a.signedInAs}</p>
          <p className="truncate font-medium" dir="auto">{me.org.is_sandbox ? a.sandbox : me.user.email}</p>
          {me.org.expires_at && (
            <p className="text-xs text-ink-3">{a.sandboxExpires} <bdi>{new Date(me.org.expires_at).toLocaleString(locale)}</bdi></p>
          )}
        </div>
        {me.orgs.length > 1 && (
          <div className="border-t border-line pt-1">
            <p className="px-2 py-1 text-xs text-ink-3">{a.switchOrg}</p>
            {me.orgs.map((o) => (
              <button key={o.id} type="button" disabled={o.id === me.org.id}
                onClick={() => api.switchOrg(o.id).then(adopt).catch(() => undefined)}
                className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-start hover:bg-muted disabled:opacity-60">
                <span className="truncate" dir="auto">{o.name}</span><span className="text-xs text-ink-3">{o.role}</span>
              </button>
            ))}
          </div>
        )}
        <div className="border-t border-line pt-1">
          <Link href={`/${locale}/team`} className="block rounded-lg px-2 py-1.5 hover:bg-muted">{a.team}</Link>
          <button type="button" onClick={signOut} className="block w-full rounded-lg px-2 py-1.5 text-start hover:bg-muted">
            {a.signOut}
          </button>
          {!me.org.is_sandbox && (
            <button type="button" className="block w-full rounded-lg px-2 py-1.5 text-start text-ink-2 hover:bg-muted"
              onClick={() => api.logoutAll().finally(signOut)}>
              {a.signOutAll}
            </button>
          )}
        </div>
      </div>
    </details>
  );
}
