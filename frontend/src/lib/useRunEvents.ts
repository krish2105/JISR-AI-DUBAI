"use client";

/**
 * useRunEvents.ts — Subscribe to a run's live event stream (Server-Sent Events).
 *
 * Why: the timeline, the agent graph (and later the 3D graph) all render from the same
 * ordered list of events. This hook opens an EventSource, appends events in sequence order
 * (ignoring duplicates after a reconnect), and closes when the run is `done`.
 */

import { useEffect, useState } from "react";
import { api, type RunEvent } from "./api";

export type RunStream = { events: RunEvent[]; done: boolean; connected: boolean };

const EMPTY: RunStream = { events: [], done: false, connected: false };

export function useRunEvents(runId: string | null): RunStream {
  // State is keyed by run id, so switching runs never shows the previous run's events.
  const [stream, setStream] = useState<{ runId: string | null } & RunStream>({ runId: null, ...EMPTY });

  useEffect(() => {
    if (!runId) return;
    const source = new EventSource(api.eventsUrl(runId));

    source.onopen = () => setStream((s) => (s.runId === runId ? { ...s, connected: true } : s));
    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as RunEvent;
      setStream((s) => {
        const base = s.runId === runId ? s : { runId, ...EMPTY };
        if (base.events.some((e) => e.seq === event.seq)) return base;          // duplicate after reconnect
        const events = [...base.events, event].sort((a, b) => a.seq - b.seq);
        const done = event.kind === "done";
        if (done) source.close();                                               // nothing more will come
        return { ...base, runId, events, done, connected: !done };
      });
    };
    // EventSource retries on its own (sending Last-Event-ID); we only mark the connection state.
    source.onerror = () => setStream((s) => (s.runId === runId ? { ...s, connected: false } : s));

    return () => source.close();
  }, [runId]);

  return stream.runId === runId ? stream : EMPTY;
}
