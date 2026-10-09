"use client";

/**
 * ApprovalCard.tsx — One held action: what, why, evidence, risk, the draft, and the decision.
 *
 * Why: the approval inbox is the hero screen of the trust story. The human sees exactly what
 * would be sent, can edit it, and approves or rejects in one click. Used both on /approvals
 * and inline on /demo.
 */

import { useState } from "react";
import { Check, Pencil, X } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type Approval } from "@/lib/api";
import { Badge, Button, Card, RiskBadge } from "@/components/ui/primitives";

export function ApprovalCard({ approval, onDecided }: { approval: Approval; onDecided?: (a: Approval) => void }) {
  const { t } = useI18n();
  const [text, setText] = useState(approval.payload.text ?? "");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState(approval);
  const draftDir = approval.payload.language === "ar" ? "rtl" : "ltr";

  async function decide(kind: "approve" | "reject") {
    setBusy(true);
    setError(null);
    try {
      const edited = text !== (approval.payload.text ?? "") ? text : undefined;
      const result = kind === "approve" ? await api.approve(current.id, { edited_text: edited }) : await api.reject(current.id);
      setCurrent(result);
      onDecided?.(result);
    } catch (e) {
      setError((e as Error).message);
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
              {current.status === "pending" && (
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

        {error && <p className="text-risk">{error}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-line bg-muted/50 px-4 py-3">
        {current.status === "pending" ? (
          <>
            <Button onClick={() => decide("approve")} disabled={busy}>
              <Check className="h-4 w-4" aria-hidden /> {t.demo.result.approve}
            </Button>
            <Button variant="secondary" onClick={() => decide("reject")} disabled={busy}>
              <X className="h-4 w-4" aria-hidden /> {t.demo.result.reject}
            </Button>
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
