/**
 * /[lang]/demo — the one-click live demo (client console with SSE timeline and agent graph).
 */

import type { Metadata } from "next";
import { DemoConsole } from "@/components/demo/DemoConsole";

export const metadata: Metadata = { title: "Live demo" };

export default function DemoPage() {
  return <DemoConsole />;
}
