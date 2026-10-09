"use client";

/**
 * I18nProvider.tsx — Makes the current locale and dictionary available to client components.
 *
 * Why: the root layout knows the locale from the URL. Client components (demo console,
 * inbox) call useI18n() instead of receiving the dictionary through many props.
 */

import { createContext, useContext } from "react";
import type { Locale } from "./config";
import { getDictionary, type Dictionary } from "./dictionaries";

type I18n = { locale: Locale; t: Dictionary; dir: "ltr" | "rtl" };

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  const value: I18n = { locale, t: getDictionary(locale), dir: locale === "ar" ? "rtl" : "ltr" };
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/** Read the locale, dictionary and direction (must be inside I18nProvider). */
export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}
