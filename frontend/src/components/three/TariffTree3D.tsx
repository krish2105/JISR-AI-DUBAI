"use client";

/**
 * TariffTree3D.tsx — The UAE tariff for one chapter as a radial 3D tree, with the duty agent's path lit up.
 *
 * Why: "how did the agent get from 'brass diya lamps' to 9405.50?" becomes visible: chapter in the centre, headings on
 * the inner ring, subheadings and lines further out; the searched path glows and a parcel travels along it. Clicking a
 * node selects it (the page shows its official text, duty and CEPA rule). DOM labels: Arabic shapes correctly.
 */

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Line, OrbitControls } from "@react-three/drei";
import type { Mesh } from "three";
import { CatmullRomCurve3, Vector3 } from "three";
import type { KbNode } from "@/lib/api";
import { useThemeTokens } from "./useThemeTokens";

type Placed = { node: KbNode; pos: Vector3; parent: Vector3 | null; depth: number };
const RADIUS = [0, 2.6, 4.6, 6.2, 7.4];

function layout(root: KbNode): Placed[] {
  const out: Placed[] = [];
  const walk = (node: KbNode, depth: number, a0: number, a1: number, parent: Vector3 | null) => {
    const mid = (a0 + a1) / 2;
    const r = RADIUS[Math.min(depth, RADIUS.length - 1)];
    const pos = new Vector3(Math.cos(mid) * r, (depth === 0 ? 0 : -depth * 0.25), Math.sin(mid) * r);
    out.push({ node, pos, parent, depth });
    const kids = node.children;
    kids.forEach((k, i) => walk(k, depth + 1, a0 + ((a1 - a0) * i) / kids.length, a0 + ((a1 - a0) * (i + 1)) / kids.length, pos));
  };
  walk(root, 0, 0, Math.PI * 2, null);
  return out;
}

function Traveller({ points, colour }: { points: Vector3[]; colour: string }) {
  const ref = useRef<Mesh>(null);
  const curve = useMemo(() => (points.length > 1 ? new CatmullRomCurve3(points) : null), [points]);
  useFrame(({ clock }) => {
    if (ref.current && curve) ref.current.position.copy(curve.getPoint((clock.elapsedTime * 0.35) % 1));
  });
  if (!curve) return null;
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.13, 16, 16]} />
      <meshStandardMaterial color={colour} emissive={colour} emissiveIntensity={0.9} />
    </mesh>
  );
}

const Y_AXIS = new Vector3(0, 1, 0);

function Labels({ placed, refs, spin }: { placed: Placed[]; refs: React.RefObject<Record<string, HTMLSpanElement | null>>;
  spin: number }) {
  const v = useMemo(() => new Vector3(), []);
  useFrame(({ camera, size }) => {
    placed.forEach((p) => {
      const el = refs.current?.[p.node.code];
      if (!el) return;
      v.copy(p.pos).applyAxisAngle(Y_AXIS, spin).add(new Vector3(0, 0.35, 0)).project(camera);
      el.style.transform = `translate(${((v.x + 1) / 2) * size.width}px, ${((1 - v.y) / 2) * size.height}px) translate(-50%, -100%)`;
    });
  });
  return null;
}

export default function TariffTree3D({ root, path, selected, onSelect, lang }: {
  root: KbNode; path: string[]; selected: string | null; onSelect: (n: KbNode) => void; lang: "en" | "ar";
}) {
  const tokens = useThemeTokens();
  const placed = useMemo(() => layout(root), [root]);
  const byCode = useMemo(() => new Map(placed.map((p) => [p.node.code, p])), [placed]);
  const onPath = useMemo(() => new Set(path), [path]);
  const labelRefs = useRef<Record<string, HTMLSpanElement | null>>({});
  const pathPoints = useMemo(() => path.map((c) => byCode.get(c)?.pos).filter(Boolean) as Vector3[], [path, byCode]);
  // Turn the tree so the searched heading faces the viewer (camera looks along -z).
  const spin = useMemo(() => {
    const heading = path[1] ? byCode.get(path[1])?.pos : undefined;
    return heading ? Math.atan2(heading.z, heading.x) - Math.PI / 2 : 0;   // rotation.y maps angle θ to θ - spin
  }, [path, byCode]);
  if (!tokens) return <div className="aspect-[4/3] w-full" />;
  const labelled = placed.filter((p) => p.depth === 1 || onPath.has(p.node.code) || p.node.code === selected);
  const levelColour = [tokens["--sand"], tokens["--accent"], tokens["--ink-3"], tokens["--ink-3"], tokens["--ink-3"]];
  return (
    <div className="relative aspect-[4/3] w-full overflow-hidden" aria-hidden>
      <div className="pointer-events-none absolute inset-0 z-10" style={{ direction: "ltr" }}>
        {labelled.map((p) => (
          <span key={p.node.code} ref={(el) => { labelRefs.current[p.node.code] = el; }} dir="auto"
            className={`absolute start-0 top-0 whitespace-nowrap rounded px-1 text-[10px] ${onPath.has(p.node.code) ? "bg-accent text-white" : "text-ink-2"}`}>
            {p.node.code}{p.depth === 1 ? ` · ${(lang === "ar" ? p.node.desc_ar : p.node.desc_en).replace(/^(Includes|يشمل):\s*/, "").slice(0, 26)}` : ""}
          </span>
        ))}
      </div>
      <Canvas dpr={[1, 2]} camera={{ position: [0, 12, 15.5], fov: 45 }} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={0.8} />
        <directionalLight position={[4, 10, 6]} intensity={1} />
        <group rotation={[0, spin, 0]}>
        {placed.filter((p) => p.parent).map((p) => {
          const lit = onPath.has(p.node.code) && onPath.has(p.node.code.slice(0, Math.max(2, p.node.code.length - 2)));
          return <Line key={`e-${p.node.code}`} points={[p.parent!, p.pos]} color={lit || onPath.has(p.node.code) ? tokens["--accent"] : tokens["--line"]}
            lineWidth={onPath.has(p.node.code) ? 2.5 : 0.8} transparent opacity={onPath.has(p.node.code) ? 1 : 0.6} />;
        })}
        {placed.map((p) => {
          const hot = onPath.has(p.node.code) || p.node.code === selected;
          const c = hot ? tokens["--accent"] : levelColour[Math.min(p.depth, 4)];
          return (
            <mesh key={p.node.code} position={p.pos} onClick={(e) => { e.stopPropagation(); onSelect(p.node); }}
              onPointerOver={() => { document.body.style.cursor = "pointer"; }} onPointerOut={() => { document.body.style.cursor = ""; }}>
              <sphereGeometry args={[[0.45, 0.22, 0.13, 0.09, 0.07][Math.min(p.depth, 4)], 20, 20]} />
              <meshPhysicalMaterial color={c} roughness={0.3} emissive={c} emissiveIntensity={hot ? 0.5 : 0.05} />
            </mesh>
          );
        })}
        <Traveller points={pathPoints} colour={tokens["--sand"]} />
        </group>
        <Labels placed={labelled} refs={labelRefs} spin={spin} />
        <OrbitControls enablePan={false} autoRotate={!path.length} autoRotateSpeed={0.3} minDistance={6} maxDistance={20} />
      </Canvas>
    </div>
  );
}
