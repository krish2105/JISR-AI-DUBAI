/**
 * primitives.tsx — Small, token-based building blocks: Card, Button, Badge, RiskBadge.
 *
 * Why: consistent look everywhere with no raw colours in pages. Kept tiny on purpose;
 * richer shadcn/ui components (dialogs, data tables) are added when a phase needs them.
 */

import type { ButtonHTMLAttributes, HTMLAttributes } from "react";

/** Join class names, skipping empty ones. */
export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx("rounded-[var(--radius-card)] border border-line bg-surface shadow-card", className)}
      {...props}
    />
  );
}

export function CardHeader({ title, aside, className }: { title: React.ReactNode; aside?: React.ReactNode; className?: string }) {
  return (
    <div className={cx("flex items-center justify-between gap-3 border-b border-line px-4 py-3", className)}>
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      {aside}
    </div>
  );
}

type Variant = "primary" | "secondary" | "danger" | "ghost";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-ink hover:opacity-90",
  secondary: "border border-line bg-surface text-ink hover:bg-muted",
  danger: "border border-risk/40 bg-risk-soft text-risk hover:border-risk",
  ghost: "text-ink-2 hover:bg-muted hover:text-ink",
};

export function Button({ variant = "primary", className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition",
        "disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}

type Tone = "neutral" | "accent" | "ok" | "warn" | "risk" | "sand";
const TONES: Record<Tone, string> = {
  neutral: "bg-muted text-ink-2",
  accent: "bg-accent-soft text-accent",
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  risk: "bg-risk-soft text-risk",
  sand: "bg-sand-soft text-sand",
};

export function Badge({ tone = "neutral", className, ...props }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", TONES[tone], className)}
      {...props}
    />
  );
}

const RISK_TONE: Record<string, Tone> = { low: "ok", medium: "warn", high: "risk" };

/** A risk chip; colour is never the only signal (the label says the level). */
export function RiskBadge({ risk, label }: { risk: string | null | undefined; label: string }) {
  if (!risk) return null;
  return <Badge tone={RISK_TONE[risk] ?? "neutral"}>{label}</Badge>;
}
