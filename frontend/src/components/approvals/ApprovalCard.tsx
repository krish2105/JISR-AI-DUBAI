"use client";

/**
 * ApprovalCard.tsx — One held action: what, why, evidence, risk, the draft, and the decision.
 *
 * Why: the approval inbox is the hero screen of the trust story. The human sees exactly what
 * would be sent, can edit it, and approves or rejects in one click. Used both on /approvals
 * and inline on /demo.
 */

import { useState } from "react";
import Link from "next/link";
import { Check, Pencil, X } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { ApiError, api, type Approval } from "@/lib/api";
import { Badge, Button, Card, RiskBadge } from "@/components/ui/primitives";
import { useCan } from "@/components/auth/SessionProvider";

export function ApprovalCard({ approval, onDecided }: { approval: Approval; onDecided?: (a: Approval) => void }) {
  const { t, locale } = useI18n();
  const [text, setText] = useState(approval.payload.text ?? "");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState(approval);
  const [fourEyes, setFourEyes] = useState(false);                // the server asked for a written override
  const [override, setOverride] = useState("");
  const canEdit = useCan("drafts.edit");
  const canDecide = current.can_decide ?? true;                    // older API without the flag: let the server decide
  const draftDir = approval.payload.language === "ar" ? "rtl" : "ltr";

  async function decide(kind: "approve" | "reject") {
    setBusy(true);
    setError(null);
    try {
      const edited = text !== (approval.payload.text ?? "") ? text : undefined;
      const result = kind === "approve"
        ? await api.approve(current.id, { edited_text: edited, override_reason: fourEyes ? override : undefined })
        : await api.reject(current.id);
      setCurrent(result);
      setFourEyes(false);
      onDecided?.(result);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403 && e.message.includes("Four-eyes")) setFourEyes(true);
      else setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
        <h3 dir="auto" className="me-auto font-semibold text-ink">{current.title}</h3>
        <RiskBadge risk={current.risk} label={t.risk[current.risk]} />
        <Badge tone="neutral" title={t.approvals.rule}>
          <bdi>{current.rule_id}</bdi>
        </Badge>
        <Link href={`/${locale}/run?id=${encodeURIComponent(current.run_id)}`} className="text-xs text-accent hover:underline">
          {t.runDetail.open}
        </Link>
      </div>

      <div className="space-y-3 px-4 py-3 text-sm">
        <p className="text-ink-2">
          <span className="font-medium text-ink">{t.approvals.reason}: </span>
          <span dir="auto">{current.reason}</span>
        </p>
        {current.evidence.length > 0 && (
          <p className="text-ink-2">
            <span className="font-medium text-ink">{t.approvals.evidence}: </span>
            <bdi>{current.evidence.join(" · ")}</bdi>
          </p>
        )}

        {current.payload.text !== undefined && (
          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wide text-ink-3">{t.demo.result.draft}</span>
              {current.status === "pending" && canEdit && canDecide && (
                <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => setEditing((v) => !v)}>
                  <Pencil className="h-3.5 w-3.5" aria-hidden /> {t.demo.result.edit}
                </Button>
              )}
            </div>
            {editing && current.status === "pending" ? (
              <textarea
                dir={draftDir}
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={8}
                className="w-full rounded-lg border border-line bg-muted p-3 font-sans text-sm text-ink"
              />
            ) : (
              <pre dir={draftDir} className="whitespace-pre-wrap rounded-lg bg-muted p-3 font-sans text-sm text-ink">
                {current.status === "pending" ? text : current.payload.text}
              </pre>
            )}
          </div>
        )}

        {fourEyes && current.status === "pending" && (
          <div className="space-y-2 rounded-lg border border-warn/40 bg-warn-soft p-3">
            <p className="font-medium text-warn">{t.auth.fourEyesTitle}</p>
            <p className="text-ink-2">{t.auth.fourEyesBody}</p>
            <textarea value={override} onChange={(e) => setOverride(e.target.value)} rows={2} dir="auto"
              aria-label={t.auth.fourEyesReason} placeholder={t.auth.fourEyesReason}
              className="w-full rounded-lg border border-line bg-surface p-2 text-sm text-ink" />
            <Button disabled={busy || override.trim().length < 10} onClick={() => decide("approve")}>
              {t.auth.fourEyesConfirm}
            </Button>
          </div>
        )}
        {error && <p className="text-risk" dir="auto">{error}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-line bg-muted/50 px-4 py-3">
        {current.status === "pending" ? (
          <>
            <Button onClick={() => decide("approve")} disabled={busy || !canDecide || fourEyes}>
              <Check className="h-4 w-4" aria-hidden /> {t.demo.result.approve}
            </Button>
            <Button variant="secondary" onClick={() => decide("reject")} disabled={busy || !canDecide}>
              <X className="h-4 w-4" aria-hidden /> {t.demo.result.reject}
            </Button>
            {!canDecide && (
              <span className="text-xs text-ink-3">
                {current.approver_role === "owner" ? t.auth.ownerOnly : t.auth.approverOnly}
              </span>
            )}
          </>
        ) : (
          <Badge tone={current.status === "approved" ? "ok" : "neutral"} className="px-3 py-1 text-sm">
            {current.status === "approved" ? t.demo.result.approved : t.demo.result.rejected}
          </Badge>
        )}
      </div>
    </Card>
  );
}
