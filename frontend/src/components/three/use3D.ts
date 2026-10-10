"use client";

/**
 * use3D.ts — Should a 3D scene run here? (and the "3D off" switch)
 *
 * 3D is off when: the user prefers reduced motion, WebGL is unavailable, or the user switched it off (remembered in
 * this browser only). Every 3D view has a 2D fallback, so turning it off never hides information.
 */

import { useEffect, useState } from "react";

const KEY = "jisr_3d";

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

export function use3D(): { enabled: boolean; allowed: boolean; setEnabled: (on: boolean) => void } {
  const [state, setState] = useState({ enabled: false, allowed: false });
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let saved: string | null = null;
    try {
      saved = window.localStorage.getItem(KEY);
    } catch {
      saved = null;
    }
    const allowed = !reduced && webglAvailable();
    const id = requestAnimationFrame(() => setState({ allowed, enabled: allowed && saved !== "off" }));
    return () => cancelAnimationFrame(id);
  }, []);
  const setEnabled = (on: boolean) => {
    try {
      window.localStorage.setItem(KEY, on ? "on" : "off");
    } catch {
      /* private mode: the choice lasts for this page only */
    }
    setState((s) => ({ ...s, enabled: on && s.allowed }));
  };
  return { ...state, setEnabled };
}
