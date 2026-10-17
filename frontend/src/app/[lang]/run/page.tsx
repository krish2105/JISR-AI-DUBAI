/**
 * /[lang]/run?id=… — one enquiry: results, timeline, documents and audit trail (Phases 16–17).
 */

import { Suspense } from "react";
import type { Metadata } from "next";
import { RunDetail } from "@/components/runs/RunDetail";

export const metadata: Metadata = { title: "Enquiry", robots: { index: false } };
// Rendered only after sign-in (AppShell gate, Phase 13), so Next cannot pre-validate instant navigation here.
export const instant = false;

export default function Page() {
  return (
    <Suspense>
      <RunDetail />
    </Suspense>
  );
}
