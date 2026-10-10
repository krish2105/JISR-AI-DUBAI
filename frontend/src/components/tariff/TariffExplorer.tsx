"use client";

/**
 * TariffExplorer.tsx — Chapter tree (3D or list), product search showing the agent's path, and the cited detail of
 * the selected node (official text EN/AR, duty, CEPA Annex 3B rule with page label).
 */

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useI18n } from "@/i18n/I18nProvider";
import { api, type KbChapter, type KbLocate, type KbNode } from "@/lib/api";
import { use3D } from "@/components/three/use3D";
import { ViewToggle } from "@/components/three/ViewToggle";
import { Badge, Button, Card, CardHeader } from "@/components/ui/primitives";

const TariffTree3D = dynamic(() => import("@/components/three/TariffTree3D"), { ssr: false });

function findNode(root: KbNode | null, code: string | null): KbNode | null {
  if (!root || !code) return null;
  if (root.code === code) return root;
  for (const c of root.children) {
    const hit = findNode(c, code);
    if (hit) return hit;
  }
  return null;
}

export function TariffExplorer() {
  const { t, locale } = useI18n();
  const g = t.tariff;
  const three = use3D();
  const [chapters, setChapters] = useState<KbChapter[]>([]);
  const [chapter, setChapter] = useState("94");
  const [root, setRoot] = useState<KbNode | null>(null);
  const [query, setQuery] = useState("brass diya lamps");
  const [found, setFound] = useState<KbLocate | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.kbChapters().then(setChapters).catch(() => setError(g.unavailable)); }, [g.unavailable]);
  useEffect(() => { api.kbTree(chapter).then(setRoot).catch(() => setError(g.unavailable)); }, [chapter, g.unavailable]);

  const path = useMemo(() => {
    const top = found?.candidates[0];
    return top && top.path[0] === chapter ? top.path.filter((c) => c.length <= 8 || findNode(root, c)) : [];
  }, [found, chapter, root]);
  const node = findNode(root, selected) ?? (path.length ? findNode(root, path[path.length - 1]) : null);

  const locate = () => {
    api.kbLocate(query).then((r) => {
      setFound(r);
      const top = r.candidates[0];
      if (top) { setChapter(top.path[0]); setSelected(top.path[Math.min(top.path.length - 1, 3)]); }
    }).catch(() => setError(g.unavailable));
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{g.title}</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-2">{g.subtitle}</p>
      </div>
      {error && <p className="text-sm text-risk">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <input dir="auto" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && locate()}
          aria-label={g.search} placeholder={g.search} className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-sm" />
        <Button onClick={locate}><Search className="h-4 w-4" aria-hidden />{g.locate}</Button>
        <select value={chapter} onChange={(e) => { setChapter(e.target.value); setSelected(null); }} aria-label={g.chapter}
          className="max-w-xs rounded-lg border border-line bg-surface px-2 py-2 text-sm">
          {chapters.map((c) => (
            <option key={c.code} value={c.code}>{c.code} · {(locale === "ar" ? c.title_ar : c.title).replace(/^Chapter \d+:\s*/, "").slice(0, 50)}</option>
          ))}
        </select>
      </div>

      {found && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-ink-3">{g.candidates}:</span>
          {found.candidates.map((c, i) => (
            <button key={c.line} type="button" onClick={() => { setChapter(c.path[0]); setSelected(c.path[Math.min(c.path.length - 1, 3)]); }}
              className="rounded-full border border-line px-2.5 py-1 hover:border-accent">
              <bdi>{c.heading}</bdi> · <bdi>{Math.round(c.confidence * 100)}%</bdi>{i === 0 ? ` · ${g.top}` : ""}
            </button>
          ))}
          <Badge tone="warn">{t.demo.needsHumanCheck}</Badge>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader title={g.tree} aside={<ViewToggle enabled={three.enabled} allowed={three.allowed}
            onChange={three.setEnabled} label={t.demo.graphView} />} />
          {root && (three.enabled ? (
            <TariffTree3D root={root} path={path} selected={selected} onSelect={(n) => setSelected(n.code)} lang={locale} />
          ) : (
            <ul className="max-h-[520px] space-y-1 overflow-auto p-4 text-sm">
              {root.children.map((h) => (
                <li key={h.code}>
                  <button type="button" onClick={() => setSelected(h.code)} className={`text-start ${path.includes(h.code) ? "font-semibold text-accent" : "text-ink"}`}>
                    <bdi>{h.code}</bdi> {(locale === "ar" ? h.desc_ar : h.desc_en).slice(0, 90)}
                  </button>
                </li>
              ))}
            </ul>
          ))}
        </Card>
        <Card>
          <CardHeader title={g.detail} />
          <div className="space-y-2 p-4 text-sm">
            {node ? (
              <>
                <p className="text-lg font-semibold"><bdi>{node.code}</bdi> <Badge tone="neutral">{node.level}</Badge></p>
                <p className="text-ink">{node.desc_en}</p>
                <p className="text-ink-2" dir="rtl" lang="ar">{node.desc_ar}</p>
                {node.duty_pct != null && <p><span className="text-ink-3">{g.duty}:</span> <bdi>{node.duty_pct}%</bdi></p>}
                {(node.rule ?? findNode(root, node.code.slice(0, 4))?.rule) && (() => {
                  const r = node.rule ?? findNode(root, node.code.slice(0, 4))!.rule!;
                  return <p><span className="text-ink-3">{g.rule}:</span> <bdi>{r.text}</bdi> · {r.scope} · <bdi>{r.page_label}</bdi>{r.is_ex && <Badge tone="warn">Ex</Badge>}</p>;
                })()}
                <p className="pt-2 text-xs text-ink-3">{root?.source?.tariff} · {root?.source?.rules}</p>
              </>
            ) : <p className="text-ink-3">{g.pick}</p>}
          </div>
        </Card>
      </div>
    </div>
  );
}
