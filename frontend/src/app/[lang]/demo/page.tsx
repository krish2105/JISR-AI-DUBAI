/**
 * /[lang]/demo — the one-click live demo (client console with SSE timeline and agent graph).
 */

import type { Metadata } from "next";
import { DemoConsole } from "@/components/demo/DemoConsole";

export const metadata: Metadata = { title: "Live demo" };
// Rendered only after sign-in (AppShell gate, Phase 13), so Next cannot pre-validate instant navigation here.
export const instant = false;

export default function DemoPage() {
  return <DemoConsole />;
}
