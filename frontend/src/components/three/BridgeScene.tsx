"use client";

/**
 * BridgeScene.tsx — The landing hero in 3D: shipments cross a bridge from India to the UAE through a governance gate.
 *
 * Why: one picture of the product. Every crossing passes the keystone (the governance gate) before it reaches the
 * buyer. Frosted-glass materials and soft contact shadows suit the pearl theme; colours come from the theme tokens,
 * so the midnight theme re-colours the scene live. Labels are DOM text (Arabic shapes correctly).
 */

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { ContactShadows, Float, OrbitControls, RoundedBox } from "@react-three/drei";
import type { Group, Mesh } from "three";
import { CatmullRomCurve3, Vector3 } from "three";
import { useThemeTokens, type Tokens } from "./useThemeTokens";

const ARCH = new CatmullRomCurve3([
  new Vector3(-3.2, -0.6, 0), new Vector3(-2, 1.0, 0), new Vector3(0, 1.85, 0), new Vector3(2, 1.0, 0),
  new Vector3(3.2, -0.6, 0),
]);

function Shipments({ tokens }: { tokens: Tokens }) {
  const refs = useRef<(Mesh | null)[]>([]);
  useFrame(({ clock }) => {
    refs.current.forEach((m, i) => {
      if (!m) return;
      const t = (clock.elapsedTime * 0.12 + i / 4) % 1;
      m.position.copy(ARCH.getPoint(t)).add(new Vector3(0, 0.16, 0));
      m.rotation.y = clock.elapsedTime;
      // A parcel glows as it passes the gate (middle of the arch).
      const near = Math.max(0, 1 - Math.abs(t - 0.5) * 8);
      (m.material as unknown as { emissiveIntensity: number }).emissiveIntensity = 0.1 + near * 0.9;
    });
  });
  return (
    <>
      {[0, 1, 2, 3].map((i) => (
        <mesh key={i} ref={(m) => { refs.current[i] = m; }} castShadow>
          <boxGeometry args={[0.22, 0.16, 0.16]} />
          <meshStandardMaterial color={tokens["--sand"]} emissive={tokens["--sand"]} roughness={0.4} />
        </mesh>
      ))}
    </>
  );
}

function Gate({ tokens }: { tokens: Tokens }) {
  const ref = useRef<Group>(null);
  useFrame(({ clock }) => {
    if (ref.current) ref.current.rotation.z = Math.sin(clock.elapsedTime * 0.8) * 0.08;
  });
  return (
    <group ref={ref} position={[0, 1.95, 0]}>
      <mesh castShadow>
        <torusGeometry args={[0.36, 0.09, 24, 64]} />
        <meshPhysicalMaterial color={tokens["--sand"]} roughness={0.2} metalness={0.2} emissive={tokens["--sand"]}
          emissiveIntensity={0.25} />
      </mesh>
    </group>
  );
}

function Labels({ refs }: { refs: React.RefObject<(HTMLSpanElement | null)[]> }) {
  const v = useMemo(() => new Vector3(), []);
  const anchors = useMemo(() => [new Vector3(-3.2, -1.75, 0), new Vector3(3.2, -1.75, 0), new Vector3(0, 2.55, 0)], []);
  useFrame(({ camera, size }) => {
    anchors.forEach((a, i) => {
      const el = refs.current?.[i];
      if (!el) return;
      v.copy(a).project(camera);
      el.style.transform = `translate(${((v.x + 1) / 2) * size.width}px, ${((1 - v.y) / 2) * size.height}px) translate(-50%, -50%)`;
    });
  });
  return null;
}

export default function BridgeScene({ fromLabel, toLabel, gateLabel }: { fromLabel: string; toLabel: string; gateLabel: string }) {
  const tokens = useThemeTokens();
  const labelRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const tube = useMemo(() => ARCH, []);
  if (!tokens) return null;
  return (
    <div className="relative h-full w-full" aria-hidden>
      <div className="pointer-events-none absolute inset-0 z-10" style={{ direction: "ltr" }}>
        {[fromLabel, toLabel, gateLabel].map((label, i) => (
          <span key={label} ref={(el) => { labelRefs.current[i] = el; }} dir="auto"
            className={`absolute start-0 top-0 whitespace-nowrap font-semibold ${i === 2 ? "text-xs text-ink-2" : "text-sm text-ink"}`}>
            {label}
          </span>
        ))}
      </div>
      <Canvas shadows dpr={[1, 2]} camera={{ position: [0, 1.2, 7.2], fov: 40 }} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={0.8} />
        <directionalLight position={[2, 6, 4]} intensity={1.2} castShadow />
        <Float speed={1.2} rotationIntensity={0.08} floatIntensity={0.25}>
          <RoundedBox args={[0.9, 0.9, 0.9]} radius={0.12} position={[-3.2, -0.95, 0]} castShadow>
            <meshPhysicalMaterial color={tokens["--sand"]} roughness={0.3} transmission={0.2} thickness={0.6} />
          </RoundedBox>
          <RoundedBox args={[0.9, 0.9, 0.9]} radius={0.12} position={[3.2, -0.95, 0]} castShadow>
            <meshPhysicalMaterial color={tokens["--accent"]} roughness={0.3} transmission={0.2} thickness={0.6} />
          </RoundedBox>
          <mesh castShadow>
            <tubeGeometry args={[tube, 96, 0.07, 16, false]} />
            <meshPhysicalMaterial color={tokens["--accent"]} roughness={0.25} metalness={0.1} />
          </mesh>
          <mesh position={[0, -0.6, 0]}>
            <boxGeometry args={[6.4, 0.06, 0.5]} />
            <meshStandardMaterial color={tokens["--ink-3"]} roughness={0.8} />
          </mesh>
          <Gate tokens={tokens} />
          <Shipments tokens={tokens} />
        </Float>
        <ContactShadows position={[0, -1.45, 0]} opacity={0.28} blur={2.6} scale={12} far={4} />
        <OrbitControls enablePan={false} enableZoom={false} autoRotate autoRotateSpeed={0.35}
          minPolarAngle={Math.PI / 2.6} maxPolarAngle={Math.PI / 2} minAzimuthAngle={-0.6} maxAzimuthAngle={0.6} />
        <Labels refs={labelRefs} />
      </Canvas>
    </div>
  );
}
