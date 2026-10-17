"use client";

/**
 * DemoTour.tsx — A five-step guide for judges and first-time visitors in a demo sandbox (Phase 16).
 * Skippable; progress is remembered in this browser only (a convenience, never needed for anything to work).
 */

import { useSyncExternalStore } from "react";
import { Compass, X } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { Button, Card } from "@/components/ui/primitives";

const KEY = "jisr.tour.v1";
const EVENT = "jisr:tour";

function read(): string {
  try {
    return window.localStorage.getItem(KEY) ?? "0";
  } catch {
    return "0";
  }
}
function write(value: string) {
  try {
    window.localStorage.setItem(KEY, value);
  } catch {
    /* storage unavailable: the guide simply restarts next time */
  }
  window.dispatchEvent(new Event(EVENT));
}
function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  return () => window.removeEventListener(EVENT, cb);
}

export function DemoTour() {
  const { t } = useI18n();
  const tour = t.tour;
  const state = useSyncExternalStore(subscribe, read, () => "hidden");
  if (state === "hidden") return null;
  const step = Math.min(Number(state) || 0, tour.steps.length - 1);
  const current = tour.steps[step];

  return (
    <Card className="flex flex-wrap items-start gap-3 border-accent/40 bg-accent-soft/40 p-4" role="region" aria-label={tour.title}>
      <Compass className="mt-0.5 h-5 w-5 shrink-0 text-accent" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium uppercase tracking-wide text-accent">{tour.title} · {tour.step} <bdi>{step + 1}/{tour.steps.length}</bdi></p>
        <p className="mt-1 font-semibold">{current.h}</p>
        <p className="text-sm text-ink-2">{current.b}</p>
      </div>
      <div className="flex items-center gap-2">
        {step > 0 && <Button variant="ghost" onClick={() => write(String(step - 1))}>{tour.back}</Button>}
        {step < tour.steps.length - 1
          ? <Button onClick={() => write(String(step + 1))}>{tour.next}</Button>
          : <Button onClick={() => write("hidden")}>{tour.done}</Button>}
        <button type="button" aria-label={tour.skip} title={tour.skip} onClick={() => write("hidden")}
          className="rounded-full p-1.5 text-ink-3 hover:bg-muted hover:text-ink"><X className="h-4 w-4" aria-hidden /></button>
      </div>
    </Card>
  );
}
