/**
 * /[lang]/governance — kill switch, autonomy levels, policy rules and Agent Passports (no 3D on this page).
 */

import type { Metadata } from "next";
import { GovernancePanel } from "@/components/governance/GovernancePanel";

export const metadata: Metadata = { title: "Governance" };

export default function GovernancePage() {
  return <GovernancePanel />;
}
