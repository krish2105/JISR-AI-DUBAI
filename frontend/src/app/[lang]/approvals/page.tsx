/**
 * /[lang]/approvals — the approval inbox (hero screen of the governance story).
 */

import type { Metadata } from "next";
import { ApprovalsInbox } from "@/components/approvals/ApprovalsInbox";

export const metadata: Metadata = { title: "Approvals" };

export default function ApprovalsPage() {
  return <ApprovalsInbox />;
}
