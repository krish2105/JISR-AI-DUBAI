/**
 * proxy.ts — Send visitors without a language in the URL to /en or /ar.
 *
 * Why: every page lives under /[lang]. A visitor to "/" or "/demo" is redirected to the
 * same path with a language prefix: Arabic if their browser prefers Arabic, else English.
 * (Next.js 16 renamed "middleware" to "proxy".)
 */

import { NextResponse, type NextRequest } from "next/server";
import { DEFAULT_LOCALE, LOCALES } from "@/i18n/config";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasLocale = LOCALES.some((l) => pathname === `/${l}` || pathname.startsWith(`/${l}/`));
  if (hasLocale) return;

  const prefersArabic = (request.headers.get("accept-language") ?? "").toLowerCase().startsWith("ar");
  request.nextUrl.pathname = `/${prefersArabic ? "ar" : DEFAULT_LOCALE}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(request.nextUrl);
}

export const config = {
  // Skip Next.js internals and files with an extension (icons, images).
  matcher: ["/((?!_next|.*\\..*).*)"],
};
