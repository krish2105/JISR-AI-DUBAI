"use client";

/**
 * SettingsPanel.tsx — /settings: business & pricing, products, shipping, autonomy (Phase 15).
 * Controls are disabled for roles without the permission; the server checks every change and audits it.
 */

import { useCallback, useEffect, useState } from "react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type AutonomyItem, type ProfileView } from "@/lib/api";
import { Card, cx } from "@/components/ui/primitives";
import { useCan } from "@/components/auth/SessionProvider";
import { AutonomyTable } from "./AutonomyTable";
import { BillingTab } from "./BillingTab";
import { BusinessForm } from "./BusinessForm";
import { CatalogueEditor } from "./CatalogueEditor";
import { LogisticsForm } from "./LogisticsForm";

const TABS = ["business", "catalogue", "logistics", "autonomy", "billing"] as const;

export function SettingsPanel() {
  const { t } = useI18n();
  const s = t.settings;
  const canEdit = useCan("settings.business");
  const canPolicy = useCan("governance.policies.edit");
  const [tab, setTab] = useState<(typeof TABS)[number]>("business");
  const [view, setView] = useState<ProfileView | null>(null);
  const [autonomy, setAutonomy] = useState<AutonomyItem[]>([]);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    api.profile().then(setView).catch((e) => setNotice({ ok: false, text: (e as Error).message }));
    api.autonomy().then(setAutonomy).catch(() => undefined);
  }, []);
  useEffect(load, [load]);

  const save = async (p: Promise<ProfileView>) => {
    try {
      setView(await p);
      setNotice({ ok: true, text: s.saved });
    } catch (e) {
      setNotice({ ok: false, text: (e as Error).message });
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{s.title}</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-2">{s.subtitle}</p>
      </div>
      {view?.source === "demo" && <p className="rounded-lg bg-accent-soft px-3 py-2 text-sm text-accent">{s.demoNote}</p>}
      {!canEdit && <p className="text-sm text-ink-3">{s.readOnly}</p>}
      {notice && <p role={notice.ok ? "status" : "alert"} dir="auto" className={cx("text-sm", notice.ok ? "text-ok" : "text-risk")}>{notice.text}</p>}

      <div role="tablist" className="flex flex-wrap gap-1 border-b border-line">
        {TABS.map((key) => (
          <button key={key} role="tab" type="button" aria-selected={tab === key} onClick={() => { setTab(key); setNotice(null); }}
            className={cx("rounded-t-lg px-4 py-2 text-sm", tab === key ? "border-b-2 border-accent font-medium text-accent" : "text-ink-2 hover:text-ink")}>
            {s.tabs[key]}
          </button>
        ))}
      </div>

      {view && (
        <Card className="p-5">
          {tab === "business" && (
            <BusinessForm key={JSON.stringify(view.profile.seller_name)} profile={view.profile} disabled={!canEdit}
              onSave={(sections) => save(api.patchProfile(sections))} />
          )}
          {tab === "catalogue" && (
            <CatalogueEditor items={view.profile.catalogue} disabled={!canEdit} onChanged={setView} />
          )}
          {tab === "logistics" && (
            <LogisticsForm logistics={view.profile.logistics} disabled={!canEdit}
              onSave={(logistics) => save(api.patchProfile({ logistics: logistics as ProfileView["profile"]["logistics"] }))} />
          )}
          {tab === "billing" && <BillingTab />}
          {tab === "autonomy" && (
            <AutonomyTable items={autonomy} disabled={!canPolicy} onChanged={(items) => { setAutonomy(items); setNotice({ ok: true, text: s.saved }); }}
              onError={(text) => setNotice({ ok: false, text })} />
          )}
        </Card>
      )}
    </div>
  );
}
