"use client";

/**
 * AutonomyTable.tsx — How much Jisr may do alone, per action. Only stricter than the shipped defaults (server-checked).
 */

import { Lock } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type AutonomyItem } from "@/lib/api";
import { Badge } from "@/components/ui/primitives";

export function AutonomyTable({ items, disabled, onChanged, onError }: {
  items: AutonomyItem[]; disabled?: boolean; onChanged: (items: AutonomyItem[]) => void; onError: (m: string) => void;
}) {
  const { t } = useI18n();
  const s = t.settings;
  return (
    <div className="space-y-3">
      <p className="text-sm text-ink-2">{s.autonomyHelp}</p>
      <ul className="divide-y divide-line">
        {items.map((a) => (
          <li key={a.action_type} className="flex flex-wrap items-center gap-3 py-3">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{s.actions[a.action_type] ?? a.action_type}</p>
              <p className="text-xs text-ink-3" dir="auto">{a.why}</p>
            </div>
            {a.locked ? (
              <Badge tone="risk"><Lock className="h-3 w-3" aria-hidden />{s.levels.NEVER} · {s.locked}</Badge>
            ) : (
              <select aria-label={`${s.level}: ${s.actions[a.action_type] ?? a.action_type}`} value={a.level} disabled={disabled}
                onChange={(e) => api.setAutonomy(a.action_type, e.target.value).then(onChanged).catch((err) => onError((err as Error).message))}
                className="rounded-lg border border-line bg-surface px-2 py-2 text-sm disabled:opacity-60">
                {a.allowed.map((lvl) => (
                  <option key={lvl} value={lvl}>{s.levels[lvl] ?? lvl}{lvl === a.default ? ` (${s.defaultLevel})` : ""}</option>
                ))}
              </select>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
