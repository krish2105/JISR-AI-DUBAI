/**
 * /[lang]/print?run=…&doc=… — printable trade document (Phase 17).
 */

import { Suspense } from "react";
import type { Metadata } from "next";
import { PrintableDocument } from "@/components/runs/PrintableDocument";

export const metadata: Metadata = { title: "Document", robots: { index: false } };
// Rendered only after sign-in (AppShell gate, Phase 13), so Next cannot pre-validate instant navigation here.
export const instant = false;

export default function Page() {
  return (
    <Suspense>
      <PrintableDocument />
    </Suspense>
  );
}
