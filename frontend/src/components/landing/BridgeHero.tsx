/**
 * BridgeHero.tsx — The India → UAE bridge illustration (2D, theme-aware SVG).
 *
 * Why: this is the static version of the landing hero. In Phase 7 the React Three Fiber
 * "bridge" scene loads on top of it lazily; this SVG stays as the fallback for slow devices,
 * reduced motion and screenshots. Shipment dots cross the arch with a CSS animation.
 */

export function BridgeHero({ fromLabel, toLabel, gateLabel }: { fromLabel: string; toLabel: string; gateLabel: string }) {
  return (
    <svg viewBox="0 0 600 300" className="h-auto w-full" role="img" aria-label={`${fromLabel} → ${gateLabel} → ${toLabel}`} style={{ direction: "ltr" }}>
      <defs>
        <linearGradient id="sea" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="var(--accent-soft)" />
          <stop offset="1" stopColor="var(--bg)" />
        </linearGradient>
        <path id="arch" d="M70 200 C 170 40, 430 40, 530 200" />
      </defs>
      <rect x="0" y="200" width="600" height="100" fill="url(#sea)" />
      {/* shore pillars */}
      <rect x="50" y="196" width="40" height="40" rx="6" fill="var(--sand)" opacity=".85" />
      <rect x="510" y="196" width="40" height="40" rx="6" fill="var(--accent)" opacity=".85" />
      {/* deck and arch */}
      <path d="M70 200 H530" stroke="var(--ink-3)" strokeWidth="3" />
      <use href="#arch" fill="none" stroke="var(--accent)" strokeWidth="5" strokeLinecap="round" />
      {[130, 190, 250, 300, 350, 410, 470].map((x) => (
        <line key={x} x1={x} x2={x} y1="200" y2={x < 300 ? 200 - (x - 70) * 0.62 : 200 - (530 - x) * 0.62} stroke="var(--accent)" strokeOpacity=".35" strokeWidth="2" />
      ))}
      {/* governance keystone */}
      <circle cx="300" cy="80" r="16" fill="var(--surface)" stroke="var(--sand)" strokeWidth="4" />
      <path d="M293 80l5 5 9-10" fill="none" stroke="var(--sand)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {/* shipments crossing (animation is skipped under reduced motion by globals.css) */}
      {[0, 1.3, 2.6].map((delay) => (
        <circle key={delay} r="6" fill="var(--sand)">
          <animateMotion dur="4s" begin={`${delay}s`} repeatCount="indefinite">
            <mpath href="#arch" />
          </animateMotion>
        </circle>
      ))}
      <text x="70" y="262" textAnchor="middle" fontSize="16" fontWeight="600" fill="var(--ink)">{fromLabel}</text>
      <text x="530" y="262" textAnchor="middle" fontSize="16" fontWeight="600" fill="var(--ink)">{toLabel}</text>
      <text x="300" y="50" textAnchor="middle" fontSize="13" fill="var(--ink-2)">{gateLabel}</text>
    </svg>
  );
}
