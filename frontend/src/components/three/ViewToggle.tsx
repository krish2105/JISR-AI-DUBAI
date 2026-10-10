"use client";

/**
 * ViewToggle.tsx — The 2D / 3D switch shown on every 3D view (the choice is remembered in this browser).
 */

import { cx } from "@/components/ui/primitives";

export function ViewToggle({ enabled, allowed, onChange, label }: {
  enabled: boolean; allowed: boolean; onChange: (on: boolean) => void; label: string;
}) {
  if (!allowed) return null;
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-full border border-line p-0.5 text-xs">
      {(["2d", "3d"] as const).map((mode) => (
        <button key={mode} type="button" aria-pressed={(mode === "3d") === enabled} onClick={() => onChange(mode === "3d")}
          className={cx("rounded-full px-2 py-0.5 font-medium uppercase", (mode === "3d") === enabled ? "bg-accent text-white" : "text-ink-3")}>
          {mode}
        </button>
      ))}
    </div>
  );
}
