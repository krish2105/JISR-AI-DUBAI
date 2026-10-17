/**
 * /[lang]/invite#<token> — accept an invitation to join an organisation (Phase 13).
 *
 * The token travels in the URL fragment, which browsers never send to servers, logs or other sites.
 */

import type { Metadata } from "next";
import { AcceptInvite } from "@/components/auth/AcceptInvite";

export const metadata: Metadata = { title: "Join the team", robots: { index: false } };

export default function Page() {
  return <AcceptInvite />;
}
