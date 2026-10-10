"use client";

/**
 * useThemeTokens.ts — The colour tokens of the current theme, for 3D materials.
 *
 * Why: 3D scenes cannot read CSS variables directly. This hook reads them once and again whenever the theme toggle
 * fires `jisr:theme`, so a scene re-colours live (pearl ↔ midnight) without reloading.
 */

import { useEffect, useState } from "react";
import { themeToken } from "@/components/shell/theme";

const NAMES = ["--bg", "--surface", "--muted", "--ink", "--ink-2", "--ink-3", "--line", "--accent", "--accent-soft",
  "--sand", "--ok", "--warn", "--risk"] as const;
export type Tokens = Record<(typeof NAMES)[number], string>;

function read(): Tokens {
  return Object.fromEntries(NAMES.map((n) => [n, themeToken(n) || "#888888"])) as Tokens;
}

export function useThemeTokens(): Tokens | null {
  const [tokens, setTokens] = useState<Tokens | null>(null);
  useEffect(() => {
    const update = () => setTokens(read());
    const id = requestAnimationFrame(update);                 // after the boot script applied the theme
    window.addEventListener("jisr:theme", update);
    return () => {
      cancelAnimationFrame(id);
      window.removeEventListener("jisr:theme", update);
    };
  }, []);
  return tokens;
}
