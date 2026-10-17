"use client";

/**
 * SessionProvider.tsx — Who is signed in, in which organisation, with which role (Phase 13).
 *
 * The token lives in localStorage (lib/session.ts); the user, organisation, role and permissions come from
 * GET /auth/me. `can(permission)` only hides or disables controls; the server checks every request anyway.
 */

import { createContext, useCallback, useContext, useEffect, useState, useSyncExternalStore } from "react";
import { api, type Me, type Session } from "@/lib/api";
import { SESSION_EVENT, getToken, setToken } from "@/lib/session";

type Status = "loading" | "signed-in" | "signed-out";
type SessionState = {
  status: Status;
  me: Me | null;
  can: (permission: string) => boolean;
  adopt: (session: Session) => void;
  signOut: () => void;
  refresh: () => void;
};

const SessionContext = createContext<SessionState | null>(null);

function subscribe(callback: () => void) {
  window.addEventListener(SESSION_EVENT, callback);
  window.addEventListener("storage", callback);                 // another tab signed in or out
  return () => {
    window.removeEventListener(SESSION_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}
const noopSubscribe = () => () => {};

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const token = useSyncExternalStore(subscribe, getToken, () => null);
  const hydrated = useSyncExternalStore(noopSubscribe, () => true, () => false);
  const [loaded, setLoaded] = useState<{ token: string; me: Me | null } | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!token) return;
    let live = true;
    api.me()
      .then((me) => { if (live) setLoaded({ token, me }); })
      .catch(() => { if (live) setLoaded({ token, me: null }); });
    return () => { live = false; };
  }, [token, nonce]);

  const me = token && loaded?.token === token ? loaded.me : null;
  const status: Status = !hydrated ? "loading" : !token ? "signed-out"
    : loaded?.token !== token ? "loading" : me ? "signed-in" : "signed-out";

  const adopt = useCallback((session: Session) => {
    setLoaded({ token: session.token, me: session.me });
    setToken(session.token);
  }, []);
  const signOut = useCallback(() => setToken(null), []);
  const refresh = useCallback(() => setNonce((n) => n + 1), []);
  const can = useCallback((permission: string) => !!me?.permissions.includes(permission), [me]);

  return (
    <SessionContext.Provider value={{ status, me, can, adopt, signOut, refresh }}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}

/** Does the signed-in role allow this? (UI hint only: the server is the source of truth.) */
export function useCan(permission: string): boolean {
  return useSession().can(permission);
}
