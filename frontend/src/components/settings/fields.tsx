/**
 * fields.tsx — Small labelled inputs for the settings and onboarding forms (token-styled, RTL-safe).
 */

const INPUT = "mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink disabled:opacity-60";

export function TextField({ label, value, onChange, disabled, dir }: {
  label: string; value: string; onChange: (v: string) => void; disabled?: boolean; dir?: "ltr" | "rtl" | "auto";
}) {
  return (
    <label className="block text-xs font-medium text-ink-2">{label}
      <input className={INPUT} value={value} disabled={disabled} dir={dir ?? "auto"} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

export function NumberField({ label, value, onChange, disabled, step = "any", min = 0 }: {
  label: string; value: number; onChange: (v: number) => void; disabled?: boolean; step?: string; min?: number;
}) {
  return (
    <label className="block text-xs font-medium text-ink-2">{label}
      <input className={INPUT} type="number" inputMode="decimal" dir="ltr" step={step} min={min} disabled={disabled}
        value={Number.isFinite(value) ? value : ""} onChange={(e) => onChange(e.target.valueAsNumber)} />
    </label>
  );
}

export const INPUT_CLASS = INPUT;
