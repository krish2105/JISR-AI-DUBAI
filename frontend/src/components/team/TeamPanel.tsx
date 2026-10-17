"use client";

/**
 * TeamPanel.tsx — Members and roles, invitations, and assistant (MCP) keys for one organisation (Phase 13).
 *
 * The server enforces every rule (admins cannot touch owners; the last owner stays; keys are shown once). This
 * screen hides what the role cannot do and shows the server's message when something is refused.
 */

import { useCallback, useEffect, useState } from "react";
import { KeyRound, UserPlus } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, ROLES, type ApiKey, type Member, type Role } from "@/lib/api";
import { Badge, Button, Card, CardHeader } from "@/components/ui/primitives";
import { useSession } from "@/components/auth/SessionProvider";

const INPUT = "rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink";

export function TeamPanel() {
  const { t, locale } = useI18n();
  const tm = t.team;
  const { me, can } = useSession();
  const manage = can("team.manage");
  const keysAllowed = can("api_keys.manage");
  const sandbox = !!me?.org.is_sandbox;
  const [members, setMembers] = useState<Member[] | null>(null);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("operator");
  const [link, setLink] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [keyName, setKeyName] = useState("Claude Desktop");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.members().then(setMembers).catch((e) => setError((e as Error).message));
    if (keysAllowed) api.apiKeys().then(setKeys).catch(() => undefined);
  }, [keysAllowed]);
  useEffect(load, [load]);

  const act = (p: Promise<unknown>) => p.then(load).catch((e) => setError((e as Error).message));
  const roleText = (r: string) => tm.roles[r] ?? r;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{tm.title}</h1>
        <p className="mt-1 text-sm text-ink-2">{tm.subtitle}</p>
      </div>
      {error && <p role="alert" className="text-sm text-risk" dir="auto">{error}</p>}
      {sandbox && <p className="rounded-lg bg-accent-soft px-3 py-2 text-sm text-accent">{tm.sandboxNote}</p>}

      <Card>
        <CardHeader title={tm.members} />
        <ul className="divide-y divide-line">
          {(members ?? []).map((m) => (
            <li key={m.pending ? m.invitation_id : m.user_id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium" dir="auto">
                  {m.pending ? m.email : (m.name || m.email)}{" "}
                  {!m.pending && m.you && <span className="text-xs text-ink-3">({tm.you})</span>}
                </p>
                {!m.pending && <p className="truncate text-xs text-ink-3">{m.email}</p>}
              </div>
              {m.pending ? (
                <>
                  <Badge tone="sand">{tm.pending} · {m.role}</Badge>
                  {manage && <Button variant="ghost" onClick={() => act(api.revokeInvitation(m.invitation_id))}>{tm.revoke}</Button>}
                </>
              ) : manage && !m.you ? (
                <>
                  <select aria-label={tm.changeRole} value={m.role} className={INPUT}
                    onChange={(e) => act(api.changeRole(m.user_id, e.target.value as Role))}>
                    {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                  <Button variant="ghost" onClick={() => act(api.removeMember(m.user_id))}>{tm.remove}</Button>
                </>
              ) : (
                <Badge tone="accent" title={roleText(m.role)}>{m.role}</Badge>
              )}
            </li>
          ))}
        </ul>
      </Card>

      {manage && !sandbox && (
        <Card className="space-y-3 p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold"><UserPlus className="h-4 w-4" aria-hidden />{tm.invite}</h2>
          <form className="flex flex-wrap gap-2" onSubmit={(e) => {
            e.preventDefault();
            api.invite(email, role).then((inv) => {
              setLink(`${window.location.origin}/${locale}/invite#${inv.token}`);
              setEmail("");
              load();
            }).catch((err) => setError((err as Error).message));
          }}>
            <input className={`${INPUT} min-w-0 flex-1`} type="email" required placeholder={tm.inviteEmail} dir="ltr"
              aria-label={tm.inviteEmail} value={email} onChange={(e) => setEmail(e.target.value)} />
            <select className={INPUT} aria-label={t.auth.role} value={role} onChange={(e) => setRole(e.target.value as Role)}>
              {ROLES.filter((r) => me?.role === "owner" || r !== "owner").map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <Button type="submit">{tm.sendInvite}</Button>
          </form>
          <p className="text-xs text-ink-3">{roleText(role)}</p>
          {link && (
            <div className="space-y-1 rounded-lg bg-muted p-3 text-xs">
              <p className="text-ink-2">{tm.inviteLink}</p>
              <code className="block break-all" dir="ltr">{link}</code>
              <Button variant="secondary" className="px-3 py-1 text-xs"
                onClick={() => navigator.clipboard?.writeText(link).catch(() => undefined)}>{tm.copy}</Button>
            </div>
          )}
        </Card>
      )}

      <Card className="space-y-2 p-4">
        <h2 className="text-sm font-semibold">{t.auth.role}</h2>
        <ul className="grid gap-1 text-xs text-ink-2 sm:grid-cols-2">
          {ROLES.map((r) => <li key={r}><span className="font-medium text-ink">{r}</span> — {roleText(r).split(": ")[1] ?? roleText(r)}</li>)}
        </ul>
      </Card>

      {keysAllowed && !sandbox && (
        <Card className="space-y-3 p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold"><KeyRound className="h-4 w-4" aria-hidden />{tm.keys}</h2>
          <p className="text-xs text-ink-2">{tm.keysBody}</p>
          <form className="flex flex-wrap gap-2" onSubmit={(e) => {
            e.preventDefault();
            api.createApiKey(keyName).then((k) => { setNewKey(k.key); load(); }).catch((err) => setError((err as Error).message));
          }}>
            <input className={`${INPUT} min-w-0 flex-1`} aria-label={tm.keyName} value={keyName} onChange={(e) => setKeyName(e.target.value)} />
            <Button type="submit" variant="secondary">{tm.createKey}</Button>
          </form>
          {newKey && (
            <div className="rounded-lg bg-warn-soft p-3 text-xs">
              <p className="text-warn">{tm.keyOnce}</p>
              <code className="mt-1 block break-all text-ink" dir="ltr">{newKey}</code>
            </div>
          )}
          <ul className="divide-y divide-line text-sm">
            {keys.map((k) => (
              <li key={k.id} className="flex items-center gap-3 py-2">
                <span className="flex-1 truncate" dir="auto">{k.name} <code className="text-xs text-ink-3" dir="ltr">{k.prefix}…</code></span>
                <span className="text-xs text-ink-3">{tm.lastUsed}: {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString(locale) : tm.never}</span>
                {k.revoked ? <Badge>{tm.revoked}</Badge>
                  : <Button variant="ghost" onClick={() => act(api.revokeApiKey(k.id))}>{tm.revoke}</Button>}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
