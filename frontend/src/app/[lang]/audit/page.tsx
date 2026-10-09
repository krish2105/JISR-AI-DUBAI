/**
 * /[lang]/audit — the hash-chained audit log with a live "chain verified" check.
 */

import type { Metadata } from "next";
import { AuditLog } from "@/components/audit/AuditLog";

export const metadata: Metadata = { title: "Audit log" };

export default function AuditPage() {
  return <AuditLog />;
}
