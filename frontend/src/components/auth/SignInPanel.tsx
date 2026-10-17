"use client";

/**
 * SignInPanel.tsx — The way into Jisr: a private demo sandbox (one click), sign in, or create an organisation.
 *
 * Shown in place of any protected page when nobody is signed in, and on /signin. The demo comes first because
 * judges and first-time visitors should be inside a working sandbox in one click.
 */

import { useEffect, useState } from "react";
import { FlaskConical, LogIn, UserPlus } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type AuthConfig } from "@/lib/api";
import { Button, Card } from "@/components/ui/primitives";
import { useSession } from "./SessionProvider";

const INPUT = "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink";

export function SignInPanel({ title }: { title?: string }) {
  const { t } = useI18n();
  const a = t.auth;
  const { adopt } = useSession();
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [form, setForm] = useState({ email: "", password: "", name: "", org_name: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.authConfig().then(setConfig).catch(() => setError(t.common.error));
  }, [t.common.error]);

  async function run(action: () => Promise<Parameters<typeof adopt>[0]>) {
    setBusy(true);
    setError(null);
    try {
      adopt(await action());
    } catch (e) {
      setError((e as Error).message || t.common.error);
    } finally {
      setBusy(false);
    }
  }

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <div className="mx-auto max-w-4xl space-y-6 py-4">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight">{title ?? a.title}</h1>
        <p className="mx-auto mt-2 max-w-2xl text-sm text-ink-2">{a.subtitle}</p>
      </div>
      {error && <p role="alert" className="text-center text-sm text-risk">{error}</p>}

      <div className="grid gap-4 md:grid-cols-2">
        {(config?.demo_mode ?? true) && (
          <Card className="flex flex-col gap-3 border-accent/40 p-5">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <FlaskConical className="h-4 w-4 text-accent" aria-hidden /> {a.demoTitle}
            </h2>
            <p className="flex-1 text-sm text-ink-2">
              {a.demoBody.replace("{hours}", String(config?.sandbox_hours ?? 24))}
            </p>
            <Button disabled={busy} onClick={() => run(() => api.demoSandbox())} className="w-full">
              {a.demoButton}
            </Button>
          </Card>
        )}

        <Card className="p-5">
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              run(() => (mode === "signin"
                ? api.login({ email: form.email, password: form.password })
                : api.signup(form)));
            }}
          >
            <h2 className="flex items-center gap-2 text-base font-semibold">
              {mode === "signin" ? <LogIn className="h-4 w-4" aria-hidden /> : <UserPlus className="h-4 w-4" aria-hidden />}
              {mode === "signin" ? a.signIn : a.signUp}
            </h2>
            {mode === "signup" && (
              <>
                <label className="block text-xs font-medium text-ink-2">{a.name}
                  <input className={`${INPUT} mt-1`} value={form.name} onChange={set("name")} autoComplete="name" />
                </label>
                <label className="block text-xs font-medium text-ink-2">{a.orgName}
                  <input className={`${INPUT} mt-1`} value={form.org_name} onChange={set("org_name")} autoComplete="organization" />
                </label>
              </>
            )}
            <label className="block text-xs font-medium text-ink-2">{a.email}
              <input className={`${INPUT} mt-1`} type="email" required value={form.email} onChange={set("email")}
                autoComplete="email" dir="ltr" />
            </label>
            <label className="block text-xs font-medium text-ink-2">{a.password}
              <input className={`${INPUT} mt-1`} type="password" required minLength={mode === "signup" ? 10 : 1}
                value={form.password} onChange={set("password")} dir="ltr"
                autoComplete={mode === "signin" ? "current-password" : "new-password"} />
              {mode === "signup" && <span className="mt-1 block text-ink-3">{a.passwordHint}</span>}
            </label>
            <Button type="submit" variant="secondary" disabled={busy} className="w-full">
              {mode === "signin" ? a.signIn : a.signUp}
            </Button>
            {(config?.allow_signup ?? true) && (
              <button type="button" className="w-full text-center text-xs text-accent hover:underline"
                onClick={() => setMode(mode === "signin" ? "signup" : "signin")}>
                {mode === "signin" ? a.noAccount : a.haveAccount}
              </button>
            )}
          </form>
        </Card>
      </div>
    </div>
  );
}
