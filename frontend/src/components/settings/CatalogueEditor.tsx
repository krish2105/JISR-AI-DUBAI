"use client";

/**
 * CatalogueEditor.tsx — The products Jisr can price: add, edit, remove, CSV import/export, HS hint suggestion.
 *
 * The HS suggestion uses the same tariff index as the duty agent (/kb/locate) and is only a hint: the duty agent
 * still decides with citations, and the document check flags any disagreement.
 */

import { useRef, useState } from "react";
import { Download, Pencil, Plus, Sparkles, Trash2, Upload } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type CatalogueItem, type ProfileView } from "@/lib/api";
import { Badge, Button } from "@/components/ui/primitives";
import { NumberField, TextField } from "./fields";

const EMPTY: CatalogueItem = { name: "", keywords: [], materials: [], unit_cost_inr: 0, kg: 0.5, cbm: 0.002, hs_hint: null };
const words = (v: string) => v.split(/[,،|]/).map((w) => w.trim()).filter(Boolean);

export function CatalogueEditor({ items, disabled, onChanged }: {
  items: CatalogueItem[]; disabled?: boolean; onChanged: (view: ProfileView) => void;
}) {
  const { t } = useI18n();
  const s = t.settings;
  const [editing, setEditing] = useState<{ original: string | null; item: CatalogueItem } | null>(null);
  const [kw, setKw] = useState("");
  const [mat, setMat] = useState("");
  const [hsNote, setHsNote] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"merge" | "replace">("merge");
  const file = useRef<HTMLInputElement>(null);

  const open = (original: string | null, item: CatalogueItem) => {
    setEditing({ original, item });
    setKw(item.keywords.join(", "));
    setMat(item.materials.join(", "));
    setHsNote(null);
    setError(null);
  };
  const act = (p: Promise<ProfileView>, done?: string) =>
    p.then((v) => { onChanged(v); setEditing(null); setMessage(done ?? s.saved); setError(null); })
      .catch((e) => setError((e as Error).message));

  async function suggest() {
    if (!editing?.item.name) return;
    try {
      const r = await api.kbLocate(editing.item.name);
      const top = r.candidates[0];
      if (!top || r.needs_human_check) { setHsNote(s.suggestNone); if (!top) return; }
      setEditing({ ...editing, item: { ...editing.item, hs_hint: top.line.replace(/\D/g, "").slice(0, 8) || top.heading } });
      setHsNote(`${top.line} · ${top.desc}`);
    } catch {
      setHsNote(s.suggestNone);
    }
  }

  return (
    <div className="space-y-4">
      {!disabled && (
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => open(null, EMPTY)}><Plus className="h-4 w-4" aria-hidden />{s.add}</Button>
          <input ref={file} type="file" accept=".csv,text/csv" className="hidden" onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            try {
              const r = await api.importCatalogue(await f.text(), mode);
              onChanged(r);
              setMessage(s.imported.replace("{added}", String(r.import.added)).replace("{updated}", String(r.import.updated))
                + (r.import.errors.length ? ` · ${r.import.errors.join(" · ")}` : ""));
              setError(null);
            } catch (err) {
              setError((err as Error).message);
            } finally {
              e.target.value = "";
            }
          }} />
          <select aria-label={s.importCsv} value={mode} onChange={(e) => setMode(e.target.value as "merge" | "replace")}
            className="rounded-lg border border-line bg-surface px-2 py-2 text-sm">
            <option value="merge">{s.merge}</option><option value="replace">{s.replace}</option>
          </select>
          <Button variant="secondary" onClick={() => file.current?.click()}><Upload className="h-4 w-4" aria-hidden />{s.importCsv}</Button>
          <Button variant="ghost" onClick={() => api.exportCatalogue().then((csv) => {
            const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
            Object.assign(document.createElement("a"), { href: url, download: "jisr-catalogue.csv" }).click();
            URL.revokeObjectURL(url);
          }).catch((e) => setError((e as Error).message))}><Download className="h-4 w-4" aria-hidden />{s.exportCsv}</Button>
        </div>
      )}
      {!disabled && <p className="text-xs text-ink-3">{s.csvHelp}</p>}
      {message && <p className="text-sm text-ok" role="status" dir="auto">{message}</p>}
      {error && <p className="text-sm text-risk" role="alert" dir="auto">{error}</p>}

      {editing && (
        <form className="space-y-3 rounded-[var(--radius-card)] border border-accent/40 p-4" onSubmit={(e) => {
          e.preventDefault();
          const item = { ...editing.item, keywords: words(kw).length ? words(kw) : [editing.item.name.toLowerCase()], materials: words(mat) };
          act(editing.original ? api.replaceProduct(editing.original, item) : api.addProduct(item));
        }}>
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField label={s.product} value={editing.item.name} onChange={(v) => setEditing({ ...editing, item: { ...editing.item, name: v } })} />
            <TextField label={s.keywords} value={kw} onChange={setKw} />
            <TextField label={s.materials} value={mat} onChange={setMat} />
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <TextField label={s.hs} dir="ltr" value={editing.item.hs_hint ?? ""}
                  onChange={(v) => setEditing({ ...editing, item: { ...editing.item, hs_hint: v || null } })} />
              </div>
              <Button type="button" variant="secondary" onClick={suggest} disabled={!editing.item.name}>
                <Sparkles className="h-4 w-4" aria-hidden />{s.suggestHs}
              </Button>
            </div>
            <NumberField label={s.cost} value={editing.item.unit_cost_inr} onChange={(v) => setEditing({ ...editing, item: { ...editing.item, unit_cost_inr: v } })} />
            <div className="grid grid-cols-2 gap-2">
              <NumberField label={s.kg} value={editing.item.kg} onChange={(v) => setEditing({ ...editing, item: { ...editing.item, kg: v } })} />
              <NumberField label={s.cbm} value={editing.item.cbm} onChange={(v) => setEditing({ ...editing, item: { ...editing.item, cbm: v } })} />
            </div>
          </div>
          <p className="text-xs text-ink-3" dir="auto">{hsNote ?? s.hsNote}</p>
          <div className="flex gap-2">
            <Button type="submit">{s.save}</Button>
            <Button type="button" variant="ghost" onClick={() => setEditing(null)}>{s.cancel}</Button>
          </div>
        </form>
      )}

      {items.length === 0 ? (
        <p className="rounded-[var(--radius-card)] border border-dashed border-line p-6 text-center text-sm text-ink-3">{s.empty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-xs text-ink-3">
              <tr className="border-b border-line text-start">
                <th className="px-2 py-2 text-start font-medium">{s.product}</th>
                <th className="px-2 py-2 text-start font-medium">{s.keywords}</th>
                <th className="px-2 py-2 text-end font-medium">{s.cost}</th>
                <th className="px-2 py-2 text-end font-medium">kg · CBM</th>
                <th className="px-2 py-2 text-start font-medium">HS</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.name} className="border-b border-line/60">
                  <td className="px-2 py-2 font-medium" dir="auto">{item.name}</td>
                  <td className="px-2 py-2 text-ink-2" dir="auto">{item.keywords.slice(0, 4).join(", ")}{item.keywords.length > 4 ? "…" : ""}</td>
                  <td className="px-2 py-2 text-end"><bdi>{item.unit_cost_inr.toLocaleString()}</bdi></td>
                  <td className="px-2 py-2 text-end text-ink-2"><bdi>{item.kg} · {item.cbm}</bdi></td>
                  <td className="px-2 py-2">{item.hs_hint ? <Badge><bdi>{item.hs_hint}</bdi></Badge> : "—"}</td>
                  <td className="px-2 py-2 text-end">
                    {!disabled && (
                      <span className="inline-flex gap-1">
                        <Button variant="ghost" className="px-2" aria-label={`${s.edit} ${item.name}`} onClick={() => open(item.name, item)}>
                          <Pencil className="h-4 w-4" aria-hidden />
                        </Button>
                        <Button variant="ghost" className="px-2" aria-label={`${s.remove} ${item.name}`}
                          onClick={() => act(api.removeProduct(item.name))}>
                          <Trash2 className="h-4 w-4" aria-hidden />
                        </Button>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
