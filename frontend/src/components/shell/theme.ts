/**
 * theme.ts — Light/dark theme: the boot script, the toggle action and 3D token access.
 *
 * Why: the saved theme lives in a cookie (`jisr_theme`). The boot script runs in <head>
 * before anything paints and sets <html data-theme>. Toggling flips the attribute and
 * saves the cookie. No React state is involved, so there is nothing to mismatch.
 */

export type Theme = "light" | "dark";
export const THEME_COOKIE = "jisr_theme";

/** Inline script for <head>: apply the saved theme before first paint (light by default). */
export const THEME_BOOT_SCRIPT = `(function(){try{var m=document.cookie.match(/(?:^|; )${THEME_COOKIE}=(light|dark)/);if(m)document.documentElement.setAttribute("data-theme",m[1])}catch(e){}})()`;

/** Read the theme currently applied to the page. */
export function currentTheme(): Theme {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

/** Switch theme now and remember it for a year. */
export function setTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
  document.cookie = `${THEME_COOKIE}=${theme}; path=/; max-age=31536000; SameSite=Lax`;
  // Tell listeners (e.g. 3D scenes in later phases) to re-read the colour tokens.
  window.dispatchEvent(new CustomEvent("jisr:theme", { detail: theme }));
}

/** Read a CSS colour token, e.g. themeToken("--accent"); used by canvas/3D code. */
export function themeToken(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
