/**
 * /[lang]/governance — kill switch, autonomy levels, policy rules and Agent Passports (no 3D on this page).
 */

import type { Metadata } from "next";
import { GovernancePanel } from "@/components/governance/GovernancePanel";

export const metadata: Metadata = { title: "Governance" };
// Rendered only after sign-in (AppShell gate, Phase 13), so Next cannot pre-validate instant navigation here.
export const instant = false;

export default function GovernancePage() {
  return <GovernancePanel />;
}
