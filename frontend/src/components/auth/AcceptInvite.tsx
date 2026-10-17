"use client";

/**
 * AcceptInvite.tsx — Join an organisation from an invitation link. New people choose a password; people who
 * already have an account confirm with theirs. The token comes from the URL fragment (#token), which is never sent
 * to any server by the browser, and is never stored by the dashboard.
 */

import { useEffect, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { useI18n } from "@/i18n/I18nProvider";
import { api } from "@/lib/api";
import { Button, Card } from "@/components/ui/primitives";
import { useSession } from "./SessionProvider";

type Info = { org_name: string; email: string; role: string; has_account: boolean };

function subscribeHash(callback: () => void) {
  window.addEventListener("hashchange", callback);
  return () => window.removeEventListener("hashchange", callback);
}

export function AcceptInvite() {
  const { t, locale } = useI18n();
  const a = t.auth;
  const token = useSyncExternalStore(subscribeHash, () => window.location.hash.slice(1), () => "");
  const router = useRouter();
  const { adopt } = useSession();
  const [info, setInfo] = useState<Info | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    api.invitation(token).then(setInfo).catch(() => setInvalid(true));
  }, [token]);

  if (invalid) return <p className="py-16 text-center text-sm text-risk">{a.inviteInvalid}</p>;
  if (!info) return <p className="py-16 text-center text-sm text-ink-3">{t.common.loading}</p>;

  return (
    <Card className="mx-auto max-w-md space-y-4 p-6">
      <h1 className="text-xl font-semibold" dir="auto">{a.inviteTitle.replace("{org}", info.org_name)}</h1>
      <p className="text-sm text-ink-2">
        {a.inviteBody.replace("{role}", info.role)} <bdi className="font-medium">{info.email}</bdi>
      </p>
      <form className="space-y-3" onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
          adopt(await api.acceptInvitation({ token, password, name }));
          router.replace(`/${locale}/demo`);
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setBusy(false);
        }
      }}>
        <p className="text-xs text-ink-3">{info.has_account ? a.inviteExisting : a.inviteNew}</p>
        {!info.has_account && (
          <label className="block text-xs font-medium text-ink-2">{a.name}
            <input className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm" value={name}
              onChange={(e) => setName(e.target.value)} autoComplete="name" />
          </label>
        )}
        <label className="block text-xs font-medium text-ink-2">{a.password}
          <input className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm" type="password" dir="ltr"
            required minLength={info.has_account ? 1 : 10} value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete={info.has_account ? "current-password" : "new-password"} />
        </label>
        {error && <p role="alert" className="text-sm text-risk">{error}</p>}
        <Button type="submit" disabled={busy} className="w-full">{a.inviteAccept}</Button>
      </form>
    </Card>
  );
}
