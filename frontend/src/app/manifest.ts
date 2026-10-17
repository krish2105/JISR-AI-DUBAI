/**
 * manifest.ts — Web app manifest (Phase 16): Jisr can be installed on a phone's home screen, so an owner can open
 * the approval inbox in one tap. Served by Next at /manifest.webmanifest.
 */

import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Jisr AI — governed India–UAE trade agent",
    short_name: "Jisr",
    description: "Quotes, CEPA duty checks and export documents, approved by you.",
    start_url: "/en/approvals",
    scope: "/",
    display: "standalone",
    background_color: "#faf8f5",
    theme_color: "#0f766e",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
