/**
 * /[lang]/impact — the Impact Ledger: measured outcomes per run, and a clearly labelled time-saved estimate.
 */

import type { Metadata } from "next";
import { ImpactPanel } from "@/components/impact/ImpactPanel";

export const metadata: Metadata = { title: "Impact" };

export default function ImpactPage() {
  return <ImpactPanel />;
}
