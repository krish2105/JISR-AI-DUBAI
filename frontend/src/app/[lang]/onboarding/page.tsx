/**
 * /[lang]/onboarding — set up a new exporter's business in about five minutes (Phase 15).
 */

import type { Metadata } from "next";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";

export const metadata: Metadata = { title: "Set up" };
// Rendered only after sign-in (AppShell gate, Phase 13), so Next cannot pre-validate instant navigation here.
export const instant = false;

export default function Page() {
  return <OnboardingWizard />;
}
