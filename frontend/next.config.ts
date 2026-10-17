import type { NextConfig } from "next";

/**
 * Security headers (Phase 20, DECISIONS H2). The Content-Security-Policy is applied to production builds only:
 * the dev server needs eval for hot reload. 'unsafe-inline' scripts remain because Next's static pages bootstrap with
 * inline scripts and the theme boot script must run before paint; everything else is locked to this site and the API.
 */
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${API}`,
  `media-src 'self' ${API} blob:`,
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    const common = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
    ];
    const production = process.env.NODE_ENV === "production";
    return [{ source: "/:path*", headers: production ? [...common, { key: "Content-Security-Policy", value: CSP }] : common }];
  },
};

export default nextConfig;
