/**
 * /[lang]/signin — demo sandbox, sign in, or create an organisation (Phase 13).
 */

import type { Metadata } from "next";
import { SignInPage } from "@/components/auth/SignInPage";

export const metadata: Metadata = { title: "Sign in" };

export default function Page() {
  return <SignInPage />;
}
