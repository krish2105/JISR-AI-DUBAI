"use client";

/**
 * BusinessForm.tsx — Business name and pricing policy (margins, discounts, validity, assumed cost).
 * `part` limits the fields for an onboarding step; Settings shows everything.
 */

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import type { BusinessProfile } from "@/lib/api";
import { Button } from "@/components/ui/primitives";
import { NumberField, TextField } from "./fields";

type Part = "all" | "business" | "pricing";
type Draft = Pick<BusinessProfile, "seller_name" | "quote_validity_days" | "default_margin_pct" | "min_margin_pct"
  | "max_discount_pct" | "volume_discounts" | "default_unit_cost_inr">;

export function BusinessForm({ profile, part = "all", disabled, onSave, saveLabel }: {
  profile: BusinessProfile; part?: Part; disabled?: boolean; saveLabel?: string;
  onSave: (sections: Partial<BusinessProfile>) => Promise<void>;
}) {
  const { t } = useI18n();
  const s = t.settings;
  const [draft, setDraft] = useState<Draft>({
    seller_name: profile.seller_name, quote_validity_days: profile.quote_validity_days,
    default_margin_pct: profile.default_margin_pct, min_margin_pct: profile.min_margin_pct,
    max_discount_pct: profile.max_discount_pct, volume_discounts: profile.volume_discounts,
    default_unit_cost_inr: profile.default_unit_cost_inr,
  });
  const set = <K extends keyof Draft>(key: K) => (value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }));
  const showBusiness = part !== "pricing";
  const showPricing = part !== "business";

  return (
    <form className="space-y-4" onSubmit={(e) => {
      e.preventDefault();
      const sections: Partial<BusinessProfile> = {};
      if (showBusiness) Object.assign(sections, { seller_name: draft.seller_name, quote_validity_days: draft.quote_validity_days });
      if (showPricing) Object.assign(sections, {
        default_margin_pct: draft.default_margin_pct, min_margin_pct: draft.min_margin_pct,
        max_discount_pct: draft.max_discount_pct, volume_discounts: draft.volume_discounts,
        default_unit_cost_inr: draft.default_unit_cost_inr,
      });
      void onSave(sections);
    }}>
      {showBusiness && (
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField label={s.sellerName} value={draft.seller_name} onChange={set("seller_name")} disabled={disabled} />
          <NumberField label={s.validity} value={draft.quote_validity_days} onChange={set("quote_validity_days")} step="1" min={1} disabled={disabled} />
        </div>
      )}
      {showPricing && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <NumberField label={s.margin} value={draft.default_margin_pct} onChange={set("default_margin_pct")} disabled={disabled} />
            <NumberField label={s.minMargin} value={draft.min_margin_pct} onChange={set("min_margin_pct")} disabled={disabled} />
            <NumberField label={s.maxDiscount} value={draft.max_discount_pct} onChange={set("max_discount_pct")} disabled={disabled} />
          </div>
          <NumberField label={s.defaultCost} value={draft.default_unit_cost_inr} onChange={set("default_unit_cost_inr")} disabled={disabled} />
          <fieldset className="space-y-2">
            <legend className="text-xs font-medium text-ink-2">{s.tiers}</legend>
            {draft.volume_discounts.map((tier, i) => (
              <div key={i} className="flex items-end gap-2">
                <NumberField label={s.tierQty} value={tier.min_qty} disabled={disabled} step="1"
                  onChange={(v) => set("volume_discounts")(draft.volume_discounts.map((x, j) => (j === i ? { ...x, min_qty: v } : x)))} />
                <NumberField label={s.tierPct} value={tier.pct} disabled={disabled}
                  onChange={(v) => set("volume_discounts")(draft.volume_discounts.map((x, j) => (j === i ? { ...x, pct: v } : x)))} />
                {!disabled && (
                  <Button type="button" variant="ghost" aria-label={s.remove}
                    onClick={() => set("volume_discounts")(draft.volume_discounts.filter((_, j) => j !== i))}>
                    <Trash2 className="h-4 w-4" aria-hidden />
                  </Button>
                )}
              </div>
            ))}
            {!disabled && (
              <Button type="button" variant="ghost" className="text-xs"
                onClick={() => set("volume_discounts")([...draft.volume_discounts, { min_qty: 1000, pct: 2 }])}>
                <Plus className="h-3.5 w-3.5" aria-hidden />{s.addTier}
              </Button>
            )}
          </fieldset>
        </>
      )}
      {!disabled && <Button type="submit">{saveLabel ?? s.save}</Button>}
    </form>
  );
}
