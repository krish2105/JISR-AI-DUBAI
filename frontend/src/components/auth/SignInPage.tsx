"use client";

/**
 * SignInPage.tsx — /signin: once signed in, continue to the live demo.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useI18n } from "@/i18n/I18nProvider";
import { SignInPanel } from "./SignInPanel";
import { useSession } from "./SessionProvider";

export function SignInPage() {
  const { status } = useSession();
  const { locale, t } = useI18n();
  const router = useRouter();
  useEffect(() => {
    if (status === "signed-in") router.replace(`/${locale}/demo`);
  }, [status, locale, router]);
  if (status === "signed-in") return <p className="py-16 text-center text-sm text-ink-3">{t.common.loading}</p>;
  return <SignInPanel />;
}
