/**
 * config.ts — Supported languages and their text direction.
 *
 * Why: the language lives in the URL (/en/..., /ar/...). Each language page is rendered
 * with the right `lang` and `dir` on <html>, so Arabic is right-to-left from the very
 * first byte — no flash, no hydration mismatch.
 */

export const LOCALES = ["en", "ar"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

/** True when a string is one of our supported locales. */
export function isLocale(value: string): value is Locale {
  return (LOCALES as readonly string[]).includes(value);
}

/** Text direction for a locale. */
export function dirFor(locale: Locale): "ltr" | "rtl" {
  return locale === "ar" ? "rtl" : "ltr";
}
