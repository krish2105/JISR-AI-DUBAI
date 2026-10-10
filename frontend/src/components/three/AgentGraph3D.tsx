"use client";

/**
 * AgentGraph3D.tsx — The live agent graph in 3D: same RunView as the 2D graph, rendered with React Three Fiber.
 *
 * Why: the demo's "wow" moment. Work fans out from the supervisor to the specialist agents, converges on the
 * governance gate and only then reaches the human. Active agents pulse, finished ones glow softly, a held action
 * turns the gate amber, a blocked one flashes it red. Light theme: depth comes from soft shadows, not bloom.
 *
 * Loaded lazily (no SSR), never on approvals/audit/settings pages; the 2D graph is always one click away and is the
 * fallback under reduced motion or without WebGL.
 */

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { ContactShadows, Line, OrbitControls } from "@react-three/drei";
import type { Mesh } from "three";
import { QuadraticBezierCurve3, Vector3 } from "three";
import type { GraphNode, NodeState, RunView } from "@/lib/runView";
import { useThemeTokens, type Tokens } from "./useThemeTokens";

// Positions in 3D: a fan from left to right, workers spread on an arc in depth.
const POS: Record<GraphNode, [number, number, number]> = {
  ingest: [-5.2, 0, 0], guard: [-3.8, 0, 0], supervisor: [-2.2, 0, 0],
  quote: [0.3, 2.2, -0.4], duty: [0.5, 1.1, 0.2], docs: [0.6, 0, 0.5], trust: [0.5, -1.1, 0.2],
  outreach: [0.3, -2.2, -0.4],
  governance: [2.8, 0, 0], human: [4.8, 0, 0],
};
const WORKERS: GraphNode[] = ["quote", "duty", "docs", "trust", "outreach"];
const EDGES: [GraphNode, GraphNode][] = [
  ["ingest", "guard"], ["guard", "supervisor"],
  ...WORKERS.map((w) => ["supervisor", w] as [GraphNode, GraphNode]),
  ...WORKERS.map((w) => [w, "governance"] as [GraphNode, GraphNode]),
  ["governance", "human"],
];

function colour(state: NodeState, t: Tokens): string {
  return { idle: t["--muted"], active: t["--accent"], done: t["--accent"], held: t["--warn"], waiting: t["--warn"],
    blocked: t["--risk"] }[state];
}

function AgentNode({ id, state, tokens }: { id: GraphNode; state: NodeState; tokens: Tokens }) {
  const ref = useRef<Mesh>(null);
  const gate = id === "governance";
  useFrame(({ clock }) => {
    if (!ref.current) return;
    const pulse = state === "active" || (gate && state === "blocked") ? 1 + Math.sin(clock.elapsedTime * 6) * 0.08 : 1;
    ref.current.scale.setScalar(pulse);
  });
  const c = colour(state, tokens);
  return (
    <group position={POS[id]}>
      <mesh ref={ref} castShadow>
        {gate ? <torusGeometry args={[0.42, 0.13, 24, 64]} /> : <icosahedronGeometry args={[0.32, 2]} />}
        <meshPhysicalMaterial color={c} roughness={0.25} metalness={0.05} transmission={state === "idle" ? 0.5 : 0.15}
          thickness={0.5} emissive={c} emissiveIntensity={state === "idle" ? 0 : state === "done" ? 0.15 : 0.45} />
      </mesh>
    </group>
  );
}

function Edge({ a, b, lit, tokens }: { a: GraphNode; b: GraphNode; lit: boolean; tokens: Tokens }) {
  const points = useMemo(() => {
    const p0 = new Vector3(...POS[a]);
    const p2 = new Vector3(...POS[b]);
    const mid = p0.clone().add(p2).multiplyScalar(0.5).add(new Vector3(0, 0.25, 0));
    return new QuadraticBezierCurve3(p0, mid, p2).getPoints(24);
  }, [a, b]);
  return <Line points={points} color={lit ? tokens["--accent"] : tokens["--line"]} lineWidth={lit ? 2.2 : 1}
    transparent opacity={lit ? 0.9 : 0.6} />;
}

/** A parcel of work travelling along the lit edges (stops under reduced motion because the scene is not mounted). */
function Packets({ view, tokens }: { view: RunView; tokens: Tokens }) {
  const refs = useRef<(Mesh | null)[]>([]);
  const litKey = EDGES.filter(([a, b]) => view.nodes[a] !== "idle" && view.nodes[b] !== "idle")
    .map((e) => e.join(">")).join("|");
  const curves = useMemo(() => (litKey ? litKey.split("|") : []).map((edge) => {
    const [a, b] = edge.split(">") as [GraphNode, GraphNode];
    const p0 = new Vector3(...POS[a]);
    const p2 = new Vector3(...POS[b]);
    return new QuadraticBezierCurve3(p0, p0.clone().add(p2).multiplyScalar(0.5).add(new Vector3(0, 0.25, 0)), p2);
  }), [litKey]);
  useFrame(({ clock }) => {
    curves.forEach((curve, i) => {
      const m = refs.current[i];
      if (m) m.position.copy(curve.getPoint((clock.elapsedTime * 0.5 + i * 0.17) % 1));
    });
  });
  return (
    <>
      {curves.map((_, i) => (
        <mesh key={i} ref={(m) => { refs.current[i] = m; }}>
          <sphereGeometry args={[0.06, 12, 12]} />
          <meshStandardMaterial color={tokens["--sand"]} emissive={tokens["--sand"]} emissiveIntensity={0.6} />
        </mesh>
      ))}
    </>
  );
}

/**
 * Labels are ordinary DOM text (so Arabic shapes correctly and no extra React roots are created). Each frame, the
 * node positions are projected to screen space and the label elements are moved directly (no React re-render).
 */
function LabelProjector({ labels }: { labels: React.RefObject<Partial<Record<GraphNode, HTMLSpanElement | null>>> }) {
  const v = useMemo(() => new Vector3(), []);
  useFrame(({ camera, size }) => {
    (Object.keys(POS) as GraphNode[]).forEach((id) => {
      const el = labels.current?.[id];
      if (!el) return;
      const side = WORKERS.includes(id);                      // workers: label beside the node, others: below
      v.set(POS[id][0] + (side ? 0.42 : 0), POS[id][1] - (side ? 0 : id === "governance" ? 0.72 : 0.55), POS[id][2])
        .project(camera);
      const x = ((v.x + 1) / 2) * size.width;
      const y = ((1 - v.y) / 2) * size.height;
      el.style.transform = side ? `translate(${x}px, ${y}px) translate(0, -50%)` : `translate(${x}px, ${y}px) translate(-50%, 0)`;
    });
  });
  return null;
}

export default function AgentGraph3D({ view, labels }: { view: RunView; labels: Record<string, string> }) {
  const tokens = useThemeTokens();
  const labelRefs = useRef<Partial<Record<GraphNode, HTMLSpanElement | null>>>({});
  if (!tokens) return <div className="aspect-[10/5] w-full" />;
  return (
    <div className="relative aspect-[10/5] w-full overflow-hidden" aria-hidden>
      <div className="pointer-events-none absolute inset-0 z-10" style={{ direction: "ltr" }}>
        {(Object.keys(POS) as GraphNode[]).map((id) => (
          <span key={id} ref={(el) => { labelRefs.current[id] = el; }} dir="auto"
            className="absolute start-0 top-0 whitespace-nowrap text-[11px] font-medium text-ink-2">{labels[id] ?? id}</span>
        ))}
      </div>
      <Canvas shadows dpr={[1, 2]} camera={{ position: [0, 0.9, 9.5], fov: 40 }} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={0.75} />
        <directionalLight position={[3, 6, 4]} intensity={1.1} castShadow />
        {EDGES.map(([a, b]) => (
          <Edge key={`${a}-${b}`} a={a} b={b} lit={view.nodes[a] !== "idle" && view.nodes[b] !== "idle"} tokens={tokens} />
        ))}
        {(Object.keys(POS) as GraphNode[]).map((id) => (
          <AgentNode key={id} id={id} state={view.nodes[id]} tokens={tokens} />
        ))}
        <Packets view={view} tokens={tokens} />
        <LabelProjector labels={labelRefs} />
        <ContactShadows position={[0, -2.8, 0]} opacity={0.25} blur={2.5} scale={14} far={4} />
        <OrbitControls enablePan={false} enableZoom={false} autoRotate autoRotateSpeed={0.4}
          minPolarAngle={Math.PI / 3} maxPolarAngle={Math.PI / 2} minAzimuthAngle={-0.5} maxAzimuthAngle={0.5} />
      </Canvas>
    </div>
  );
}
