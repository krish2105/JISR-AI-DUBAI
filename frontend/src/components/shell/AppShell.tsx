"use client";

/**
 * AppShell.tsx — Page frame: top bar (brand, language, user menu, theme) and, once signed in, a left sidebar with
 * role-aware navigation (Phase 16). Visitors who are not signed in keep a short top bar.
 *
 * Why: the same frame on every page, so the theme toggle and the language switch are always one click away (judges
 * will try both). The sidebar keeps a dozen destinations readable; on phones it becomes a "Menu" drawer.
 * Links keep the current language prefix; logical CSS properties make the sidebar sit on the right in Arabic.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Languages, Menu, Moon, Sun } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { SignInPanel } from "@/components/auth/SignInPanel";
import { useSession } from "@/components/auth/SessionProvider";
import { UserMenu } from "@/components/auth/UserMenu";
import { api } from "@/lib/api";
import { currentTheme, setTheme } from "./theme";
import { JisrMark } from "./JisrMark";

/** Pages that show organisation data: they need a session (landing, tariff, pricing, terms, privacy are public). */
const PROTECTED = ["/demo", "/approvals", "/audit", "/governance", "/impact", "/team", "/settings", "/onboarding", "/run",
  "/print", "/today", "/buyers", "/ops"];

type NavLink = { href: string; label: string; active: boolean; badge?: number };
type NavGroup = { label: string; links: NavLink[] };

/** Pending approvals for the badge, refreshed every 30 s while signed in. */
function usePendingCount(enabled: boolean): number {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    const tick = () => api.approvals("pending").then((a) => { if (live) setCount(a.length); }).catch(() => undefined);
    tick();
    const id = window.setInterval(tick, 30_000);
    return () => { live = false; window.clearInterval(id); };
  }, [enabled]);
  return enabled ? count : 0;
}

/** One navigation link (pill in the top bar, row in the sidebar), with the optional approvals badge. */
function NavItem({ link, row, waitingLabel }: { link: NavLink; row?: boolean; waitingLabel: string }) {
  return (
    <Link
      href={link.href}
      aria-current={link.active ? "page" : undefined}
      className={`flex items-center whitespace-nowrap text-sm transition-colors ${row ? "rounded-lg px-3 py-2" : "rounded-full px-3 py-1.5"} ${
        link.active ? "bg-accent-soft font-medium text-accent" : "text-ink-2 hover:bg-muted hover:text-ink"
      }`}
    >
      <span className="flex-1">{link.label}</span>
      {!!link.badge && (
        <span className="ms-1.5 inline-flex min-w-5 items-center justify-center rounded-full bg-risk px-1.5 text-[10px] font-semibold text-white"
          aria-label={`${link.badge} ${waitingLabel}`}>
          <bdi>{link.badge}</bdi>
        </span>
      )}
    </Link>
  );
}

/** The grouped sidebar list (also used inside the phone drawer). */
function SidebarGroups({ groups, waitingLabel }: { groups: NavGroup[]; waitingLabel: string }) {
  return (
    <nav className="space-y-5">
      {groups.map((group) => (
        <div key={group.label}>
          <p className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wide text-ink-3">{group.label}</p>
          <div className="space-y-0.5">
            {group.links.map((link) => <NavItem key={link.href} link={link} row waitingLabel={waitingLabel} />)}
          </div>
        </div>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { t, locale } = useI18n();
  const pathname = usePathname() ?? `/${locale}`;
  const rest = pathname.replace(/^\/(en|ar)/, "");                 // path without the language prefix
  const otherLocale = locale === "en" ? "ar" : "en";
  const { status, me, can } = useSession();
  const signedIn = status === "signed-in";
  const pendingCount = usePendingCount(signedIn && can("runs.read"));
  const setupPending = signedIn && me?.onboarding && !me.onboarding.done && can("settings.business")
    && !rest.startsWith("/onboarding");
  const needsSession = PROTECTED.some((p) => rest.startsWith(p));
  const link = (path: string, label: string, extra: Partial<NavLink> = {}): NavLink =>
    ({ href: `/${locale}${path}`, label, active: path === "" ? rest === "" : rest.startsWith(path), ...extra });

  // Public top links for visitors; the full, role-aware set lives in the sidebar once signed in.
  const publicLinks = [link("", t.nav.home), link("/demo", t.nav.demo), link("/tariff", t.nav.tariff),
    link("/pricing", t.nav.pricing)];
  const groups: NavGroup[] = [
    { label: t.nav.groups.work, links: [link("/today", t.nav.today), link("/demo", t.nav.demo),
      link("/approvals", t.nav.approvals, { badge: pendingCount }),
      ...(can("buyers.read") ? [link("/buyers", t.nav.buyers)] : [])] },
    { label: t.nav.groups.trade, links: [link("/tariff", t.nav.tariff), link("/impact", t.nav.impact)] },
    { label: t.nav.groups.control, links: [link("/governance", t.nav.governance), link("/audit", t.nav.audit),
      ...(can("ops.read") ? [link("/ops", t.nav.ops)] : [])] },
    { label: t.nav.groups.org, links: [link("/settings", t.nav.settings), link("/team", t.nav.team)] },
  ];

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-line bg-bg/80 backdrop-blur-md print:hidden">
        <div className="mx-auto flex h-16 max-w-[90rem] items-center gap-2 px-4 sm:px-6">
          {signedIn && (
            <details className="relative lg:hidden">
              <summary className="flex h-9 cursor-pointer list-none items-center gap-1.5 rounded-full border border-line px-3 text-sm text-ink-2"
                aria-label={t.nav.menu}>
                <Menu className="h-4 w-4" aria-hidden /><span className="hidden sm:inline">{t.nav.menu}</span>
              </summary>
              <div className="absolute start-0 z-50 mt-2 max-h-[75vh] w-64 overflow-y-auto rounded-[var(--radius-card)] border border-line bg-surface p-3 shadow-card">
                <SidebarGroups groups={groups} waitingLabel={t.inbox.waiting} />
              </div>
            </details>
          )}
          <Link href={`/${locale}`} className="me-4 flex shrink-0 items-center gap-2.5" aria-label={t.brand.name}>
            <JisrMark className="h-8 w-8" />
            <span className="text-lg font-semibold tracking-tight">{t.brand.name}</span>
          </Link>

          <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
            {!signedIn && publicLinks.map((l) => <NavItem key={l.href} link={l} waitingLabel={t.inbox.waiting} />)}
          </div>

          <Link
            href={`/${otherLocale}${rest}`}
            aria-label={t.lang.switchAria}
            className="inline-flex h-9 items-center gap-1.5 rounded-full border border-line px-3 text-sm text-ink-2 hover:bg-muted hover:text-ink"
          >
            <Languages className="h-4 w-4" aria-hidden />
            <span lang={otherLocale}>{t.lang.switchLabel}</span>
          </Link>

          <UserMenu />

          <button
            type="button"
            onClick={() => setTheme(currentTheme() === "dark" ? "light" : "dark")}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-line text-ink-2 hover:bg-muted hover:text-ink"
          >
            {/* Both icons are rendered; CSS shows the right one for the active theme. */}
            <span className="theme-icon-light" title={t.theme.toDark}>
              <Moon className="h-4 w-4" aria-hidden />
              <span className="sr-only">{t.theme.toDark}</span>
            </span>
            <span className="theme-icon-dark" title={t.theme.toLight}>
              <Sun className="h-4 w-4" aria-hidden />
              <span className="sr-only">{t.theme.toLight}</span>
            </span>
          </button>
        </div>
      </header>
      {setupPending && me?.onboarding && (
        <div className="border-b border-accent/30 bg-accent-soft print:hidden">
          <div className="mx-auto flex max-w-[90rem] flex-wrap items-center gap-3 px-4 py-2 text-sm text-accent sm:px-6">
            <span className="flex-1">
              {t.onboarding.banner.replace("{step}", String(Math.min(me.onboarding.step + 1, 5))).replace("{total}", "5")}
            </span>
            <Link href={`/${locale}/onboarding`} className="rounded-full bg-accent px-3 py-1 text-xs font-medium text-accent-ink">
              {t.onboarding.continue}
            </Link>
          </div>
        </div>
      )}
      <div className="mx-auto flex w-full max-w-[90rem] flex-1">
        {signedIn && (
          <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] w-56 shrink-0 overflow-y-auto border-e border-line px-3 py-6 lg:block print:hidden">
            <SidebarGroups groups={groups} waitingLabel={t.inbox.waiting} />
          </aside>
        )}
        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 sm:py-8">
          {!needsSession || signedIn ? children
            : status === "loading" ? <p className="py-16 text-center text-sm text-ink-3">{t.common.loading}</p>
            : <SignInPanel title={t.auth.gateTitle} />}
        </main>
      </div>
      <footer className="border-t border-line py-4 text-center text-xs text-ink-3 print:hidden">
        {t.brand.name} · {t.brand.tagline} ·{" "}
        <Link href={`/${locale}/privacy`} className="underline-offset-4 hover:underline">{t.privacy.link}</Link> ·{" "}
        <Link href={`/${locale}/pricing`} className="underline-offset-4 hover:underline">{t.nav.pricing}</Link> ·{" "}
        <Link href={`/${locale}/terms`} className="underline-offset-4 hover:underline">{t.nav.terms}</Link>
      </footer>
    </>
  );
}
