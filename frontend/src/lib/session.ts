/**
 * session.ts — Where the dashboard keeps the access token (Phase 13).
 *
 * Why localStorage and a bearer header (DECISIONS S9): the API and the dashboard live on different sites (fly.dev /
 * vercel.app), where cross-site cookies are blocked by several browsers. The token is short-lived (12 h; demo
 * sandboxes 24 h), carries no role (the server reads the role on every request) and "Sign out everywhere"
 * revokes it. Every access is wrapped in try/catch: private windows can refuse storage.
 */

const KEY = "jisr.session.v1";
export const SESSION_EVENT = "jisr:session-changed";

export function getToken(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) window.localStorage.setItem(KEY, token);
    else window.localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: the session lasts until the tab closes */
  }
  if (typeof window !== "undefined") window.dispatchEvent(new Event(SESSION_EVENT));
}
