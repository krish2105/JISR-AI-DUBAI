"use client";

/**
 * LogisticsForm.tsx — Shipping cost inputs used by the quote agent (port, freight, clearance, insurance).
 */

import { useState } from "react";
import { useI18n } from "@/i18n/I18nProvider";
import type { LogisticsSettings } from "@/lib/api";
import { Button } from "@/components/ui/primitives";
import { NumberField, TextField } from "./fields";

const MARKETS = ["AE", "SA", "QA", "OM", "KW", "BH", "unknown"];

export function LogisticsForm({ logistics, disabled, onSave, saveLabel }: {
  logistics: LogisticsSettings; disabled?: boolean; saveLabel?: string;
  onSave: (logistics: Partial<LogisticsSettings>) => Promise<void>;
}) {
  const { t } = useI18n();
  const s = t.settings;
  const [d, setD] = useState(logistics);
  const set = <K extends keyof LogisticsSettings>(key: K) => (value: LogisticsSettings[K]) => setD((x) => ({ ...x, [key]: value }));

  return (
    <form className="space-y-4" onSubmit={(e) => {
      e.preventDefault();
      // Import duty is not edited here: it comes from the official tariff (the duty agent cites it).
      void onSave({
        origin_port: d.origin_port, inland_freight_inr_per_kg: d.inland_freight_inr_per_kg,
        export_clearance_inr: d.export_clearance_inr, ocean_freight_aed_per_cbm: d.ocean_freight_aed_per_cbm,
        min_cbm: d.min_cbm, insurance_pct: d.insurance_pct, destination_delivery_aed: d.destination_delivery_aed,
        destination_clearance_aed: d.destination_clearance_aed,
      });
    }}>
      <div className="grid gap-3 sm:grid-cols-3">
        <TextField label={s.originPort} value={d.origin_port} onChange={set("origin_port")} disabled={disabled} />
        <NumberField label={s.inland} value={d.inland_freight_inr_per_kg} onChange={set("inland_freight_inr_per_kg")} disabled={disabled} />
        <NumberField label={s.clearance} value={d.export_clearance_inr} onChange={set("export_clearance_inr")} disabled={disabled} />
        <NumberField label={s.minCbm} value={d.min_cbm} onChange={set("min_cbm")} disabled={disabled} />
        <NumberField label={s.insurance} value={d.insurance_pct} onChange={set("insurance_pct")} disabled={disabled} />
        <NumberField label={s.delivery} value={d.destination_delivery_aed} onChange={set("destination_delivery_aed")} disabled={disabled} />
        <NumberField label={s.destClearance} value={d.destination_clearance_aed} onChange={set("destination_clearance_aed")} disabled={disabled} />
      </div>
      <fieldset>
        <legend className="text-xs font-medium text-ink-2">{s.ocean}</legend>
        <div className="mt-1 grid grid-cols-3 gap-2 sm:grid-cols-7">
          {MARKETS.map((m) => (
            <NumberField key={m} label={m} value={d.ocean_freight_aed_per_cbm[m] ?? 0} disabled={disabled}
              onChange={(v) => set("ocean_freight_aed_per_cbm")({ ...d.ocean_freight_aed_per_cbm, [m]: v })} />
          ))}
        </div>
      </fieldset>
      {!disabled && <Button type="submit">{saveLabel ?? s.save}</Button>}
    </form>
  );
}
