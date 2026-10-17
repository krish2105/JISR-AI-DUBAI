"use client";

/**
 * BuyersPanel.tsx — /buyers: buyer memory with masked contacts, and data rights (export, erase) (Phase 20).
 */

import { useCallback, useEffect, useState } from "react";
import { Download, Trash2 } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type Buyer } from "@/lib/api";
import { Badge, Button, Card } from "@/components/ui/primitives";
import { useCan } from "@/components/auth/SessionProvider";

export function BuyersPanel() {
  const { t, locale } = useI18n();
  const b = t.buyers;
  const canErase = useCan("buyers.erase");
  const [items, setItems] = useState<Buyer[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    api.buyers().then(setItems).catch((e) => { setItems([]); setNotice((e as Error).message); });
  }, []);
  useEffect(load, [load]);

  const download = (buyer: Buyer) => api.exportBuyer(buyer.contact_key).then((data) => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    Object.assign(document.createElement("a"), { href: url, download: `jisr-buyer-${buyer.contact_key.slice(0, 8)}.json` }).click();
    URL.revokeObjectURL(url);
  }).catch((e) => setNotice((e as Error).message));

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{b.title}</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-2">{b.subtitle}</p>
      </div>
      {notice && <p role="status" className="text-sm text-ink-2" dir="auto">{notice}</p>}
      {items === null ? <p className="text-sm text-ink-3">{t.common.loading}</p> : items.length === 0 ? (
        <p className="rounded-[var(--radius-card)] border border-dashed border-line p-8 text-center text-sm text-ink-3">{b.empty}</p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {items.map((buyer) => (
            <Card key={buyer.contact_key} className="space-y-2 p-4 text-sm">
              <div className="flex items-center justify-between gap-2">
                <p className="font-medium" dir="auto">{buyer.name ?? buyer.contact}</p>
                <Badge>{buyer.channel ?? "—"}</Badge>
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-ink-2">
                <dt>{b.contact}</dt><dd dir="ltr" className="text-end font-mono">{buyer.contact}</dd>
                <dt>{b.seen}</dt><dd className="text-end"><bdi>{new Date(buyer.last_seen).toLocaleDateString(locale)}</bdi></dd>
                <dt>{b.enquiries}</dt><dd className="text-end"><bdi>{buyer.runs}</bdi></dd>
                <dt>{b.sent}</dt><dd className="text-end"><bdi>{buyer.quotes_sent}</bdi></dd>
                <dt>{b.languages}</dt><dd className="text-end">{buyer.languages.join(", ") || "—"}</dd>
              </dl>
              {buyer.risk_signals.length > 0 && (
                <p className="text-xs text-risk">{b.signals}: {buyer.risk_signals.join(", ")}</p>
              )}
              <div className="flex gap-2 pt-1">
                <Button variant="secondary" className="px-3 py-1.5 text-xs" onClick={() => download(buyer)}>
                  <Download className="h-3.5 w-3.5" aria-hidden />{b.export}
                </Button>
                {canErase && (
                  <Button variant="danger" className="px-3 py-1.5 text-xs" onClick={() => {
                    if (!window.confirm(b.confirm)) return;
                    api.eraseBuyer(buyer.contact_key)
                      .then((r) => { setNotice(b.erased.replace("{n}", String(r.runs_scrubbed))); load(); })
                      .catch((e) => setNotice((e as Error).message));
                  }}>
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />{b.erase}
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
