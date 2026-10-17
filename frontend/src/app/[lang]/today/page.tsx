/**
 * /[lang]/today — the owner's home: what needs them now and the last 24 hours (Phase 16).
 */

import type { Metadata } from "next";
import { OwnerDashboard } from "@/components/home/OwnerDashboard";

export const metadata: Metadata = { title: "Today" };
// Rendered only after sign-in (AppShell gate, Phase 13), so Next cannot pre-validate instant navigation here.
export const instant = false;

export default function Page() {
  return <OwnerDashboard />;
}
