/**
 * /[lang]/buyers — buyer memory and data rights (Phase 20).
 */

import type { Metadata } from "next";
import { BuyersPanel } from "@/components/buyers/BuyersPanel";

export const metadata: Metadata = { title: "Buyers" };
// Rendered only after sign-in (AppShell gate, Phase 13), so Next cannot pre-validate instant navigation here.
export const instant = false;

export default function Page() {
  return <BuyersPanel />;
}
