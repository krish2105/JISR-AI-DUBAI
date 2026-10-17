"use client";

/**
 * GovernancePanel.tsx — The /governance page: the switches and rules that decide what Jisr may do.
 *
 * Why: "who is in control?" must be answerable on one screen. Everything here is read from the API, which reads the
 * same YAML files the engine enforces, so the page can never drift from the behaviour. Metrics on each passport come
 * from the latest eval result files (with their timestamp and commit).
 */

import { useCallback, useEffect, useState } from "react";
import { BadgeCheck, Bot, Power, ShieldAlert } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { useCan, useSession } from "@/components/auth/SessionProvider";
import { api, type AutonomousLog, type Governance, type Passport } from "@/lib/api";
import { Badge, Button, Card, CardHeader, RiskBadge } from "@/components/ui/primitives";

const EFFECT_TONE = { allow: "ok", require_approval: "warn", block: "risk" } as const;
const LEVEL_TONE: Record<string, "risk" | "warn" | "ok" | "neutral"> = { NEVER: "risk", L0: "risk", L1: "warn", L2: "ok", L3: "ok" };

export function GovernancePanel() {
  const { t, locale } = useI18n();
  const g = t.governance;
  const [gov, setGov] = useState<Governance | null>(null);
  const [auto, setAuto] = useState<AutonomousLog | null>(null);
  const [passports, setPassports] = useState<Passport[]>([]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([api.governance(), api.autonomous(24), api.passports()])
      .then(([a, b, c]) => { setGov(a); setAuto(b); setPassports(c); })
      .catch(() => setError(t.common.error));
  }, [t.common.error]);
  useEffect(load, [load]);

  const { me } = useSession();
  const canEngage = useCan("governance.kill_switch.engage");
  const canRelease = useCan("governance.kill_switch.release");
  const toggle = (engaged: boolean) => {
    api.killSwitch(engaged, engaged ? reason || "manual stop" : undefined)
      .then((next) => { setGov(next); setReason(""); load(); })
      .catch((e) => setError((e as Error).message || t.common.error));
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{g.title}</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-2">{g.subtitle}</p>
      </div>
      {error && <p className="text-sm text-risk">{error}</p>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className={gov?.kill_switch ? "border-risk/50 bg-risk-soft" : undefined}>
          <CardHeader title={<span className="inline-flex items-center gap-2"><Power className="h-4 w-4" aria-hidden />{g.killTitle}</span>}
            aside={gov && <Badge tone={gov.kill_switch ? "risk" : "ok"}>{gov.kill_switch ? g.killOn : g.killOff}</Badge>} />
          <div className="space-y-3 p-4 text-sm">
            {gov?.kill_switch ? (
              <>
                <p className="text-ink-2" dir="auto">{gov.kill_reason} · <bdi>{gov.updated_by}</bdi></p>
                {canRelease ? <Button onClick={() => toggle(false)}>{g.release}</Button>
                  : <p className="text-xs text-ink-3">{t.auth.releaseOnly}</p>}
              </>
            ) : canEngage ? (
              <div className="flex flex-wrap gap-2">
                <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={g.reason} aria-label={g.reason}
                  className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-sm" />
                <Button variant="danger" onClick={() => toggle(true)}><ShieldAlert className="h-4 w-4" aria-hidden />{g.engage}</Button>
              </div>
            ) : (
              <p className="text-xs text-ink-3">
                {t.auth.noPermission.replace("{role}", (locale === "ar" ? me?.role_label_ar : me?.role_label) ?? "")}
              </p>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title={<span className="inline-flex items-center gap-2"><Bot className="h-4 w-4" aria-hidden />{g.alone}</span>}
            aside={auto && <span className="text-sm"><bdi className="text-2xl font-semibold text-ok">{auto.done_alone}</bdi>
              <span className="text-ink-3"> · <bdi>{auto.blocked}</bdi> {g.blockedCount}</span></span>} />
          <div className="p-4 text-xs text-ink-2">
            <p>{g.aloneNote}</p>
            <ul className="mt-2 max-h-32 space-y-1 overflow-auto">
              {auto?.items.slice(0, 8).map((i) => (
                <li key={i.id} className="flex gap-2">
                  <bdi className="text-ink-3">{new Date(i.ts).toLocaleTimeString()}</bdi>
                  <bdi className={i.action === "action.autonomous_sent" ? "text-ok" : "text-risk"}>{i.action}</bdi>
                  <bdi className="text-ink-3">{i.run_id}</bdi>
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title={g.autonomy} aside={<span className="text-xs text-ink-3">{g.levels}</span>} />
        <table className="w-full text-sm">
          <tbody>
            {gov?.autonomy.map((a) => (
              <tr key={a.action_type} className="border-b border-line last:border-0">
                <td className="px-4 py-2 font-mono text-xs"><bdi>{a.action_type}</bdi></td>
                <td className="px-4 py-2"><Badge tone={LEVEL_TONE[a.level] ?? "neutral"}>{a.level}</Badge></td>
                <td className="px-4 py-2 text-ink-2">{a.why}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card>
        <CardHeader title={g.policies} aside={<span className="text-xs text-ink-3">policies.yaml</span>} />
        <table className="w-full text-sm">
          <tbody>
            {gov?.policies.map((p) => (
              <tr key={p.id} className="border-b border-line last:border-0 align-top">
                <td className="px-4 py-2 font-mono text-xs"><bdi>{p.id}</bdi></td>
                <td className="px-4 py-2"><Badge tone={EFFECT_TONE[p.effect]}>{p.effect}</Badge></td>
                <td className="px-4 py-2"><RiskBadge risk={p.risk} label={t.risk[p.risk]} /></td>
                <td className="px-4 py-2 text-ink-2">{p.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <section>
        <h2 className="mb-3 text-lg font-semibold">{g.passports}</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {passports.map((p) => (
            <Card key={p.id}>
              <CardHeader title={<span className="inline-flex items-center gap-2"><BadgeCheck className="h-4 w-4 text-accent" aria-hidden />{p.name}</span>}
                aside={Object.entries(p.autonomy).map(([a, l]) => <Badge key={a} tone={LEVEL_TONE[l] ?? "neutral"} title={a}>{l}</Badge>)} />
              <dl className="space-y-2 p-4 text-xs">
                <p className="text-sm text-ink-2">{p.purpose}</p>
                <div><dt className="text-ink-3">{g.tools}</dt>
                  <dd className="flex flex-wrap gap-1">{p.tools.length ? p.tools.map((tool) => <code key={tool} className="rounded bg-muted px-1.5 py-0.5"><bdi>{tool}</bdi></code>) : g.none}</dd></div>
                <div><dt className="text-ink-3">{g.data}</dt><dd className="text-ink-2">{p.data.join(" · ")}</dd></div>
                <div><dt className="text-ink-3">{g.measured}</dt>
                  <dd>{p.metrics.map((m) => (
                    <span key={m.metric} className="me-3 inline-block" title={m.result_file ?? ""}>
                      <bdi className="text-ink-2">{m.metric}</bdi> <bdi className="font-semibold tabular-nums">{m.value == null ? "—" : m.value.toFixed(3)}</bdi>
                    </span>))}</dd></div>
                <div><dt className="text-ink-3">{g.activity}</dt>
                  <dd className="text-ink-2"><bdi>{Object.entries(p.activity_24h).map(([k, v]) => `${k} ${v}`).join(" · ") || g.none}</bdi></dd></div>
              </dl>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
