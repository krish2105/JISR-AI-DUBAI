"use client";

/**
 * InlineScript.tsx — A <script> that runs once during HTML parsing (before first paint).
 *
 * Why (from the Next.js "preventing flash before hydration" guide): on the server it is a
 * real script, so the saved theme applies before anything is drawn. On the client it is
 * marked text/plain, so React does not warn and the script is not re-run on navigation.
 * It must be a Client Component: only then does the browser-side render see `window`.
 */

export function InlineScript({ html }: { html: string }) {
  return (
    <script
      type={typeof window === "undefined" ? "text/javascript" : "text/plain"}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
