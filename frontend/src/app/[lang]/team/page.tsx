/**
 * /[lang]/team — members, roles, invitations and assistant (MCP) keys (Phase 13).
 */

import type { Metadata } from "next";
import { TeamPanel } from "@/components/team/TeamPanel";

export const metadata: Metadata = { title: "Team" };
// Rendered only after sign-in (AppShell gate, Phase 13), so Next cannot pre-validate instant navigation here.
export const instant = false;

export default function Page() {
  return <TeamPanel />;
}
