import type {
  EdgeId,
  NodeId,
  NodeStatus,
  TourEdge,
  TourNode,
} from "./graph";
import { TELEMETRY_EDGE_IDS, TOUR_EDGES, TOUR_NODES } from "./graph";
import type { CameraTarget, ChapterId, TourBeat } from "./script";

export interface TourFrame {
  nodes: TourNode[];
  edges: TourEdge[];
  beatId: string;
  caption: string;
  chapter: ChapterId;
  camera: CameraTarget | null;
}

/**
 * Pure fold over beats[0..beatIndex]: statuses and traversed edges accumulate
 * (sticky), focus and active edges come only from the current beat. Re-derived
 * from scratch each call, so scrubbing backward is exact, not approximate.
 */
export function deriveTourState(
  beats: TourBeat[],
  beatIndex: number
): TourFrame {
  if (beats.length === 0) {
    throw new Error("deriveTourState requires at least one beat");
  }
  const index = Math.min(Math.max(beatIndex, 0), beats.length - 1);
  const current = beats[index];

  const statuses = new Map<NodeId, NodeStatus>();
  const traversed = new Set<EdgeId>();
  for (let i = 0; i <= index; i += 1) {
    const beat = beats[i];
    if (beat.statusChanges) {
      for (const [nodeId, status] of Object.entries(beat.statusChanges)) {
        statuses.set(nodeId as NodeId, status);
      }
    }
    if (i < index) {
      for (const edgeId of beat.activeEdgeIds) traversed.add(edgeId);
    }
  }

  const focused = new Set<NodeId>(current.focusNodeIds);
  const active = new Set<EdgeId>(current.activeEdgeIds);

  const nodes: TourNode[] = TOUR_NODES.map((node) => ({
    ...node,
    data: {
      ...node.data,
      status: statuses.get(node.id as NodeId) ?? "dormant",
      focused: focused.has(node.id as NodeId),
    },
  }));

  const edges: TourEdge[] = TOUR_EDGES.map((edge) => {
    const id = edge.id as EdgeId;
    const state = active.has(id)
      ? "edge-active"
      : traversed.has(id)
        ? "edge-traversed"
        : "edge-dormant";
    return {
      ...edge,
      className: TELEMETRY_EDGE_IDS.has(id)
        ? `edge-telemetry ${state}`
        : state,
    };
  });

  return {
    nodes,
    edges,
    beatId: current.id,
    caption: current.caption,
    chapter: current.chapter,
    camera: current.camera,
  };
}
