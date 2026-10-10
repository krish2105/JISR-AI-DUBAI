"use client";

/**
 * DocPack3D.tsx — The draft export documents as three floating cards; conflicting fields joined by red beams.
 *
 * Why: "the certificate says 6305 but the invoice says 4202" is easier to grasp when you SEE the two fields linked.
 * Rows are DOM text projected onto the cards (Arabic shapes correctly, screen readers use the 2D checks card, which
 * is always shown next to this view). Calm when consistent: a soft green ring instead of beams.
 */

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Line, OrbitControls, RoundedBox } from "@react-three/drei";
import type { Group } from "three";
import { Vector3 } from "three";
import type { DocIssue } from "@/lib/api";
import { useThemeTokens } from "./useThemeTokens";

export type DraftDocs = {
  invoice: { lines: { description: string; hs_code: string }[] };
  packing_list: { lines: { description: string; hs_code: string }[] };
  certificate_of_origin: { hs_codes: string[] };
};
type Row = { id: string; text: string; anchor: Vector3; bad: boolean; edge?: Vector3 };
const CARD_X = { invoice: -3.3, packing: 0, coo: 3.3 } as const;
const HALF = 1.3;                                    // half a card's width: beams leave from the card's edge
const digits = (s: string) => s.replace(/\D/g, "");

function rows(draft: DraftDocs, issues: DocIssue[]) {
  const badCoo = new Set<number>(), badPack = new Set<number>(), badInv = new Set<number>();
  const beams: [string, string][] = [];
  issues.filter((f) => f.type === "hs_mismatch").forEach((f) => {
    const m = /^(certificate_of_origin|packing_list)\.line\[(\d+)\]/.exec(f.field);
    if (!m) return;
    const k = Number(m[2]);
    const inv = draft.invoice.lines.findIndex((l) => digits(l.hs_code) === String(f.expected ?? ""));
    if (m[1] === "certificate_of_origin") badCoo.add(k); else badPack.add(k);
    if (inv >= 0) {
      badInv.add(inv);
      beams.push([`inv-${inv}`, `${m[1] === "certificate_of_origin" ? "coo" : "pack"}-${k}`]);
    }
  });
  const y = (i: number) => 0.55 - i * 0.55;
  const out: Row[] = [
    ...draft.invoice.lines.map((l, i) => ({ id: `inv-${i}`, text: `${l.description.slice(0, 18)} · ${l.hs_code}`,
      anchor: new Vector3(CARD_X.invoice, y(i), 0.12), edge: new Vector3(CARD_X.invoice + HALF, y(i), 0.12),
      bad: badInv.has(i) })),
    ...draft.packing_list.lines.map((l, i) => ({ id: `pack-${i}`, text: `${l.description.slice(0, 18)} · ${l.hs_code}`,
      anchor: new Vector3(CARD_X.packing, y(i), 0.12), edge: new Vector3(CARD_X.packing - HALF, y(i), 0.12),
      bad: badPack.has(i) })),
    ...draft.certificate_of_origin.hs_codes.map((c, i) => ({ id: `coo-${i}`, text: `HS ${c}`,
      anchor: new Vector3(CARD_X.coo, y(i), 0.12), edge: new Vector3(CARD_X.coo - HALF, y(i), 0.12),
      bad: badCoo.has(i) })),
  ];
  return { rows: out, beams };
}

function Projector({ items, refs }: { items: Row[]; refs: React.RefObject<Record<string, HTMLSpanElement | null>> }) {
  const v = useMemo(() => new Vector3(), []);
  useFrame(({ camera, size }) => {
    items.forEach((r) => {
      const el = refs.current?.[r.id];
      if (!el) return;
      v.copy(r.anchor).project(camera);
      el.style.transform = `translate(${((v.x + 1) / 2) * size.width}px, ${((1 - v.y) / 2) * size.height}px) translate(-50%, -50%)`;
    });
  });
  return null;
}

function Beam({ a, b, colour }: { a: Vector3; b: Vector3; colour: string }) {
  const ref = useRef<Group>(null);
  useFrame(({ clock }) => {
    if (ref.current) ref.current.scale.setScalar(1 + Math.sin(clock.elapsedTime * 5) * 0.02);
  });
  const mid = a.clone().add(b).multiplyScalar(0.5).add(new Vector3(0, 0.6, 0.8));
  return <group ref={ref}><Line points={[a, mid, b]} color={colour} lineWidth={3} /></group>;
}

export default function DocPack3D({ draft, issues, titles }: {
  draft: DraftDocs; issues: DocIssue[]; titles: { invoice: string; packing: string; coo: string };
}) {
  const tokens = useThemeTokens();
  const { rows: items, beams } = useMemo(() => rows(draft, issues), [draft, issues]);
  const byId = useMemo(() => new Map(items.map((r) => [r.id, r])), [items]);
  const refs = useRef<Record<string, HTMLSpanElement | null>>({});
  const titleRows: Row[] = useMemo(() => [
    { id: "t-inv", text: titles.invoice, anchor: new Vector3(CARD_X.invoice, 1.35, 0.12), bad: false },
    { id: "t-pack", text: titles.packing, anchor: new Vector3(CARD_X.packing, 1.35, 0.12), bad: false },
    { id: "t-coo", text: titles.coo, anchor: new Vector3(CARD_X.coo, 1.35, 0.12), bad: false },
  ], [titles]);
  if (!tokens) return <div className="aspect-[16/7] w-full" />;
  const all = [...titleRows, ...items];
  return (
    <div className="relative aspect-[16/7] w-full overflow-hidden" aria-hidden>
      <div className="pointer-events-none absolute inset-0 z-10" style={{ direction: "ltr" }}>
        {all.map((r) => (
          <span key={r.id} ref={(el) => { refs.current[r.id] = el; }} dir="auto"
            className={`absolute start-0 top-0 whitespace-nowrap rounded px-1 text-[10px] ${r.id.startsWith("t-") ? "text-xs font-semibold text-ink" : r.bad ? "bg-risk text-white" : "text-ink-2"}`}>
            {r.text}
          </span>
        ))}
      </div>
      <Canvas dpr={[1, 2]} camera={{ position: [0, 0.4, 8.2], fov: 42 }} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={0.85} />
        <directionalLight position={[2, 5, 6]} intensity={1} />
        {([CARD_X.invoice, CARD_X.packing, CARD_X.coo] as number[]).map((x, i) => (
          <RoundedBox key={x} args={[HALF * 2, 3.2, 0.12]} radius={0.08} position={[x, 0, 0]} rotation={[0, (1 - i) * 0.12, 0]}>
            <meshPhysicalMaterial color={tokens["--surface"]} roughness={0.35} transmission={0.25} thickness={0.4} />
          </RoundedBox>
        ))}
        {beams.map(([a, b]) => byId.get(a) && byId.get(b) && (
          <Beam key={`${a}-${b}`} a={byId.get(a)!.edge ?? byId.get(a)!.anchor} b={byId.get(b)!.edge ?? byId.get(b)!.anchor}
            colour={tokens["--risk"]} />
        ))}
        {!beams.length && (
          <mesh position={[0, -1.9, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.35, 0.05, 16, 48]} />
            <meshStandardMaterial color={tokens["--ok"]} emissive={tokens["--ok"]} emissiveIntensity={0.4} />
          </mesh>
        )}
        <Projector items={all} refs={refs} />
        <OrbitControls enablePan={false} enableZoom={false} autoRotate={false} minAzimuthAngle={-0.4} maxAzimuthAngle={0.4}
          minPolarAngle={Math.PI / 2.6} maxPolarAngle={Math.PI / 1.9} />
      </Canvas>
    </div>
  );
}
