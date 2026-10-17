/**
 * /[lang]/impact — the Impact Ledger: measured outcomes per run, and a clearly labelled time-saved estimate.
 */

import type { Metadata } from "next";
import { ImpactPanel } from "@/components/impact/ImpactPanel";

export const metadata: Metadata = { title: "Impact" };
// Rendered only after sign-in (AppShell gate, Phase 13), so Next cannot pre-validate instant navigation here.
export const instant = false;

export default function ImpactPage() {
  return <ImpactPanel />;
}
