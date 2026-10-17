/**
 * /[lang]/ops — operations metrics for owners and admins (Phase 14).
 */

import type { Metadata } from "next";
import { OpsPanel } from "@/components/ops/OpsPanel";

export const metadata: Metadata = { title: "Operations" };
// Rendered only after sign-in (AppShell gate, Phase 13), so Next cannot pre-validate instant navigation here.
export const instant = false;

export default function Page() {
  return <OpsPanel />;
}
