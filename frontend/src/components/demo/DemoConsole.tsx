"use client";

/**
 * DemoConsole.tsx — The /demo page: pick an enquiry, watch the agents, approve the result.
 *
 * Layout: samples on the side; counters, live agent graph, timeline and results in the
 * main area. The current run id is kept in the URL (?run=...) so a refresh or a shared
 * link shows the same run (its events are replayed from the API).
 */

import { useEffect, useMemo, useState } from "react";
import { Loader2, Mic, Play, ShieldAlert } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { API_URL, api, type Sample, type VoiceSample } from "@/lib/api";
import { deriveRunView } from "@/lib/runView";
import { useRunEvents } from "@/lib/useRunEvents";
import { setUrlParam, useUrlParam } from "@/lib/useUrlParam";
import { Badge, Button, Card, CardHeader, cx } from "@/components/ui/primitives";
import dynamic from "next/dynamic";
import { use3D } from "@/components/three/use3D";
import { useSession } from "@/components/auth/SessionProvider";
import { ViewToggle } from "@/components/three/ViewToggle";
import { AgentGraph2D } from "./AgentGraph2D";

// 3D is loaded only when switched on (no server rendering; the 2D graph is the fallback).
const AgentGraph3D = dynamic(() => import("@/components/three/AgentGraph3D"), { ssr: false });
import { Counters } from "./Counters";
import { ResultPanel } from "./ResultPanel";
import { Timeline } from "./Timeline";
import { DemoTour } from "./DemoTour";

/** The duty agent reports its "up to" saving in its finished event (no extra fetch needed). */
function savingFromEvents(events: { agent: string; kind: string; payload: Record<string, unknown> }[]): number | null {
  const e = events.find((ev) => ev.agent === "duty" && ev.kind === "agent_finished");
  const v = e?.payload.saving_upto_aed;
  return typeof v === "number" ? v : null;
}

export function DemoConsole() {
  const { t, locale } = useI18n();
  const [samples, setSamples] = useState<Sample[]>([]);
  const [voices, setVoices] = useState<VoiceSample[]>([]);
  const three = use3D();
  const runId = useUrlParam("run");                       // the URL is the source of truth
  const [custom, setCustom] = useState("");
  const [starting, setStarting] = useState(false);
  const { can, me } = useSession();
  const canRun = can("runs.create");
  const [error, setError] = useState<string | null>(null);
  const stream = useRunEvents(runId);
  const view = useMemo(() => deriveRunView(stream.events), [stream.events]);
  const running = runId !== null && !view.governanceFinished && !stream.done;

  // Load the sample enquiries once.
  useEffect(() => {
    api.samples().then(setSamples).catch(() => setError(t.common.error));
    api.voiceSamples().then(setVoices).catch(() => setVoices([]));
  }, [t.common.error]);

  async function sendVoice(name: string) {
    setStarting(true);
    setError(null);
    try {
      const r = await api.simulateWhatsApp({ voice_sample: name });
      if (r.run_id) setUrlParam("run", r.run_id);
      else setError(r.reason ?? t.common.error);
    } catch {
      setError(t.common.error);
    } finally {
      setStarting(false);
    }
  }

  async function start(body: { sample_id?: string; message?: string }) {
    setStarting(true);
    setError(null);
    try {
      const { run_id } = await api.startRun({ ...body, channel: "whatsapp" });
      setUrlParam("run", run_id);
    } catch {
      setError(t.common.error);
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
      {me?.org.is_sandbox && <div className="lg:col-span-full"><DemoTour /></div>}
      {/* ---------- Side: inputs ---------- */}
      <aside className="space-y-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t.demo.title}</h1>
          <p className="mt-1 text-sm text-ink-2">{t.demo.subtitle}</p>
        </div>

        <Card>
          <CardHeader title={t.demo.samples} />
          {!canRun && me && (
            <p className="px-3 pt-3 text-xs text-ink-3">
              {t.auth.noPermission.replace("{role}", locale === "ar" ? me.role_label_ar : me.role_label)}
            </p>
          )}
          <div className="space-y-2 p-3">
            {samples.map((s) => (
              <button
                key={s.id}
                type="button"
                disabled={!canRun || starting || running}
                onClick={() => start({ sample_id: s.id })}
                className={cx(
                  "w-full rounded-xl border px-3 py-2.5 text-start text-sm transition disabled:opacity-50",
                  s.hostile ? "border-risk/30 bg-risk-soft hover:border-risk" : "border-line bg-surface hover:border-accent hover:bg-accent-soft",
                )}
              >
                <span className="flex items-center gap-2 font-medium text-ink">
                  {s.hostile ? <ShieldAlert className="h-4 w-4 text-risk" aria-hidden /> : <Play className="h-4 w-4 text-accent" aria-hidden />}
                  {locale === "ar" ? s.label_ar : s.label}
                </span>
                <span dir="auto" className="mt-1 line-clamp-2 block text-xs text-ink-3">
                  {s.hostile ? t.demo.hostileHint : s.message}
                </span>
              </button>
            ))}
          </div>
        </Card>

        {voices.length > 0 && (
          <Card>
            <CardHeader title={<span className="inline-flex items-center gap-2"><Mic className="h-4 w-4 text-accent" aria-hidden />{t.demo.voiceTitle}</span>} />
            <div className="space-y-3 p-3">
              {voices.map((v) => (
                <div key={v.name} className="space-y-1.5 rounded-xl border border-line p-2.5">
                  <p className="text-sm font-medium text-ink">{v.language === "ar" ? t.demo.voiceArabic : t.demo.voiceEnglish}</p>
                  <audio controls preload="none" src={`${API_URL}${v.audio_url}`} className="h-8 w-full" />
                  <Button variant="secondary" className="w-full" disabled={!canRun || starting || running} onClick={() => sendVoice(v.name)}>
                    <Mic className="h-4 w-4" aria-hidden /> {t.demo.sendVoice}
                  </Button>
                </div>
              ))}
              <p className="text-[11px] text-ink-3">{t.demo.voiceNote}</p>
            </div>
          </Card>
        )}

        <Card>
          <CardHeader title={t.demo.custom} />
          <div className="space-y-2 p-3">
            <textarea
              dir="auto"
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
              placeholder={t.demo.customPlaceholder}
              rows={4}
              className="w-full rounded-lg border border-line bg-muted p-2.5 text-sm text-ink placeholder:text-ink-3"
            />
            <Button className="w-full" disabled={!canRun || !custom.trim() || starting || running} onClick={() => start({ message: custom })}>
              <Play className="h-4 w-4" aria-hidden /> {t.demo.runCustom}
            </Button>
          </div>
        </Card>
        {error && <p className="text-sm text-risk">{error}</p>}
      </aside>

      {/* ---------- Main: the run ---------- */}
      <section className="min-w-0 space-y-4">
        <Counters view={runId ? view : null} savingUpTo={runId ? savingFromEvents(stream.events) : null} />

        <Card>
          <CardHeader
            title={t.demo.graph}
            aside={
                <div className="flex items-center gap-2 text-xs">
                  <ViewToggle enabled={three.enabled} allowed={three.allowed} onChange={three.setEnabled} label={t.demo.graphView} />
                  {runId && (<>
                  {running && (
                    <span className="inline-flex items-center gap-1 text-accent">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> {t.demo.running}
                    </span>
                  )}
                  {view.finalStatus && <Badge tone={view.finalStatus === "blocked" ? "risk" : "ok"}>{t.status[view.finalStatus] ?? view.finalStatus}</Badge>}
                  <code className="text-ink-3"><bdi>{runId}</bdi></code>
                  </>)}
                </div>
            }
          />
          <div className="px-2 py-4 sm:px-6">
            {three.enabled ? <AgentGraph3D view={view} labels={t.agents} /> : <AgentGraph2D view={view} />}
          </div>
        </Card>

        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="min-w-0">
            <CardHeader title={t.demo.timeline} />
            <Timeline events={stream.events} />
          </Card>
          <div className="min-w-0">{runId && <ResultPanel runId={runId} view={view} />}</div>
        </div>
      </section>
    </div>
  );
}
