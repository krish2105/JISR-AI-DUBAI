/**
 * JisrMark.tsx — The Jisr logo mark: an arch bridge over water, in theme colours.
 *
 * Why an inline SVG: it inherits the theme tokens (teal arch, saffron keystone) and
 * scales crisply on a projector.
 */

export function JisrMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="9" fill="var(--accent)" />
      {/* bridge deck */}
      <path d="M5 20h22" stroke="var(--accent-ink)" strokeWidth="2" strokeLinecap="round" />
      {/* arch */}
      <path d="M7 20c2.5-7 15.5-7 18 0" fill="none" stroke="var(--accent-ink)" strokeWidth="2" strokeLinecap="round" />
      {/* keystone: the governed crossing */}
      <circle cx="16" cy="14.6" r="2" fill="var(--sand)" />
      {/* water */}
      <path d="M8 24.5h4M14 24.5h4M20 24.5h4" stroke="var(--accent-ink)" strokeOpacity=".55" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
