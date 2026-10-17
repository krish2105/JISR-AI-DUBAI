/**
 * /[lang]/approvals — the approval inbox (hero screen of the governance story).
 */

import type { Metadata } from "next";
import { ApprovalsInbox } from "@/components/approvals/ApprovalsInbox";

export const metadata: Metadata = { title: "Approvals" };
// Rendered only after sign-in (AppShell gate, Phase 13), so Next cannot pre-validate instant navigation here.
export const instant = false;

export default function ApprovalsPage() {
  return <ApprovalsInbox />;
}
