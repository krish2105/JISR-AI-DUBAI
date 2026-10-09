"use client";

/**
 * useUrlParam.ts — Read a query-string parameter as React state, with the URL as the
 * single source of truth.
 *
 * Why: the demo keeps `?run=<id>` in the address bar so refresh and shared links work.
 * useSyncExternalStore renders `null` on the server and during hydration (no mismatch),
 * then the real value on the client. setUrlParam() updates the URL and notifies readers.
 */

import { useSyncExternalStore } from "react";

const EVENT = "jisr:url";

function subscribe(onChange: () => void): () => void {
  window.addEventListener("popstate", onChange);
  window.addEventListener(EVENT, onChange);
  return () => {
    window.removeEventListener("popstate", onChange);
    window.removeEventListener(EVENT, onChange);
  };
}

/** Current value of ?name=... (null on the server and when absent). */
export function useUrlParam(name: string): string | null {
  return useSyncExternalStore(
    subscribe,
    () => new URLSearchParams(window.location.search).get(name),
    () => null,
  );
}

/** Set ?name=value without a page reload, and tell every useUrlParam reader. */
export function setUrlParam(name: string, value: string): void {
  const url = new URL(window.location.href);
  url.searchParams.set(name, value);
  window.history.replaceState(null, "", url);
  window.dispatchEvent(new Event(EVENT));
}
