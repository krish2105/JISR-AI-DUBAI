/**
 * layout.tsx — Root layout for every page, per language (/en/..., /ar/...).
 *
 * Why it looks like this:
 *  - `lang` and `dir` come from the URL, so Arabic pages are right-to-left from the first byte.
 *  - Both languages are pre-rendered (generateStaticParams), so pages are fast and static.
 *  - A tiny inline script in <head> applies the saved theme before the first paint
 *    (Next.js "preventing flash before hydration" guide), so light/dark never flickers.
 */

import type { Metadata } from "next";
import { Geist, Geist_Mono, IBM_Plex_Sans_Arabic } from "next/font/google";
import { notFound } from "next/navigation";
import { SessionProvider } from "@/components/auth/SessionProvider";
import { AppShell } from "@/components/shell/AppShell";
import { InlineScript } from "@/components/shell/InlineScript";
import { THEME_BOOT_SCRIPT } from "@/components/shell/theme";
import { LOCALES, dirFor, isLocale } from "@/i18n/config";
import { I18nProvider } from "@/i18n/I18nProvider";
import "../globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const plexArabic = IBM_Plex_Sans_Arabic({
  variable: "--font-plex-arabic",
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: { default: "Jisr AI — governed India–UAE trade agent", template: "%s · Jisr AI" },
  description:
    "Jisr turns India-to-UAE buyer enquiries into approved quotes, cited CEPA duty checks, export documents and bilingual replies, with human approval and a hash-chained audit trail.",
};

/** Pre-render every page in both languages. */
export async function generateStaticParams() {
  return LOCALES.map((lang) => ({ lang }));
}

export default async function RootLayout({ children, params }: LayoutProps<"/[lang]">) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();

  return (
    <html
      lang={lang}
      dir={dirFor(lang)}
      data-theme="light"
      suppressHydrationWarning /* the boot script may switch data-theme before React hydrates */
      className={`${geistSans.variable} ${geistMono.variable} ${plexArabic.variable} h-full antialiased`}
    >
      <head>
        <InlineScript html={THEME_BOOT_SCRIPT} />
      </head>
      <body className="min-h-full flex flex-col">
        <I18nProvider locale={lang}>
          <SessionProvider>
            <AppShell>{children}</AppShell>
          </SessionProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
