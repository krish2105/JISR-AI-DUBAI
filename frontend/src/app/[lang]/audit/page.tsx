/**
 * /[lang]/audit — the hash-chained audit log with a live "chain verified" check.
 */

import type { Metadata } from "next";
import { AuditLog } from "@/components/audit/AuditLog";

export const metadata: Metadata = { title: "Audit log" };
// Rendered only after sign-in (AppShell gate, Phase 13), so Next cannot pre-validate instant navigation here.
export const instant = false;

export default function AuditPage() {
  return <AuditLog />;
}
