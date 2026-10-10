"use client";

/**
 * HeroStage.tsx — Landing hero: the SVG bridge as an instant poster, the 3D bridge fading in when allowed.
 *
 * 3D is skipped under reduced motion, without WebGL, or when the visitor switched 3D off (demo page); the SVG
 * then stays, so the page never depends on the GPU.
 */

import dynamic from "next/dynamic";
import { use3D } from "@/components/three/use3D";
import { BridgeHero } from "./BridgeHero";

const BridgeScene = dynamic(() => import("@/components/three/BridgeScene"), { ssr: false });

export function HeroStage(props: { fromLabel: string; toLabel: string; gateLabel: string }) {
  const three = use3D();
  return (
    <div className="relative aspect-[2/1] w-full">
      <div className={three.enabled ? "invisible" : undefined}><BridgeHero {...props} /></div>
      {three.enabled && <div className="absolute inset-0"><BridgeScene {...props} /></div>}
    </div>
  );
}
