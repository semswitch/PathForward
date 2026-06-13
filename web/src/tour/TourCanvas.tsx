import { useEffect } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  useReactFlow,
} from "@xyflow/react";
import { useReducedMotion } from "motion/react";
import { nodeTypes } from "./nodes/nodeTypes";
import type { TourEdge, TourNode } from "./graph";
import type { CameraTarget } from "./script";

/** Moves the viewport to frame each beat's camera target. Playback re-takes the
 * camera after free pan/zoom; user exploration is never locked out. */
function CameraDirector({ camera }: { camera: CameraTarget | null }) {
  const { fitView } = useReactFlow();
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (!camera) return;
    const base = camera.padding ?? 0.3;
    // Defer one tick so the beat's node changes commit before framing.
    const timeout = window.setTimeout(() => {
      void fitView({
        nodes: camera.nodeIds.map((id) => ({ id })),
        // Reserve space for the overlays: caption rail (bottom), chapters (left).
        padding: {
          top: base * 0.5,
          right: base * 0.5,
          bottom: base * 0.5 + 0.22,
          left: base * 0.5 + 0.14,
        },
        duration: reducedMotion ? 0 : 800,
        maxZoom: 1.1,
      });
    }, 20);
    return () => window.clearTimeout(timeout);
  }, [camera, fitView, reducedMotion]);

  return null;
}

interface TourCanvasProps {
  nodes: TourNode[];
  edges: TourEdge[];
  camera: CameraTarget | null;
}

export function TourCanvas({ nodes, edges, camera }: TourCanvasProps) {
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      colorMode="dark"
      fitView
      fitViewOptions={{ padding: 0.1 }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      nodesFocusable={false}
      edgesFocusable={false}
      panOnDrag
      zoomOnScroll
      minZoom={0.3}
      maxZoom={1.6}
      style={{ background: "var(--surface)" }}
    >
      <CameraDirector camera={camera} />
      <Background variant={BackgroundVariant.Dots} gap={24} size={1} />
      <Controls showInteractive={false} position="bottom-left" />
    </ReactFlow>
  );
}
