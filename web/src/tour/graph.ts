import { Position } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";

/*
 * The Architecture Tour graph. Every label is the REAL runtime name — agent names,
 * MCP tool names, gate criteria, and telemetry events as they exist in the live
 * Foundry deployment. Do not invent friendlier aliases here; friendliness lives in
 * the beat captions.
 */

export type NodeId =
  | "user"
  | "orchestrator"
  | "curator"
  | "generator"
  | "critic"
  | "planner"
  | "insights"
  | "gate"
  | "mint"
  | "fabric-mcp"
  | "approval"
  | "azure-search"
  | "credential"
  | "fabric"
  | "app-insights"
  | "abstain";

export type EdgeId =
  | "e-user-orch"
  | "e-orch-curator"
  | "e-orch-generator"
  | "e-orch-critic"
  | "e-orch-planner"
  | "e-orch-insights"
  | "e-gen-search"
  | "e-orch-gate"
  | "e-gate-feedback"
  | "e-gate-mint"
  | "e-orch-mint"
  | "e-approval-mint"
  | "e-mint-cred"
  | "e-insights-fabricmcp"
  | "e-fabricmcp-fabric"
  | "e-gate-tel"
  | "e-mint-tel"
  | "e-fabric-tel"
  | "e-orch-abstain";

export type NodeStatus =
  | "dormant"
  | "active"
  | "completed"
  | "rejected"
  | "verified"
  | "minted"
  | "abstained";

export interface HandleSpec {
  id: string;
  type: "source" | "target";
  position: Position;
  /** Offset along the side (CSS percentage), for nodes with two handles on one side. */
  offset?: string;
}

export interface TourNodeData extends Record<string, unknown> {
  /** Small uppercase kind tag, e.g. "LLM AGENT" / "DETERMINISTIC CODE". */
  tag: string;
  label: string;
  sublabel?: string;
  status: NodeStatus;
  focused: boolean;
  handles: HandleSpec[];
}

export type TourNode = Node<TourNodeData>;
export type TourEdge = Edge;

const { Left, Right, Top, Bottom } = Position;

interface NodeSpec {
  id: NodeId;
  type: "agent" | "code" | "service" | "user";
  x: number;
  y: number;
  tag: string;
  label: string;
  sublabel?: string;
  handles: HandleSpec[];
}

const NODE_SPECS: NodeSpec[] = [
  {
    id: "user",
    type: "user",
    x: 0,
    y: 330,
    tag: "HUMAN",
    label: "Worker EMP-001",
    sublabel: "aiming for role R-CLOUD",
    handles: [{ id: "out", type: "source", position: Right }],
  },
  {
    id: "orchestrator",
    type: "agent",
    x: 340,
    y: 330,
    tag: "FOUNDRY PROMPT AGENT",
    label: "pathforward-orchestrator",
    sublabel: "v25 · Skill /pathforward · routes every step",
    handles: [
      { id: "in", type: "target", position: Left },
      { id: "out", type: "source", position: Right },
      { id: "down", type: "source", position: Bottom },
      { id: "in-top", type: "target", position: Top },
    ],
  },
  {
    id: "curator",
    type: "agent",
    x: 740,
    y: 40,
    tag: "LLM AGENT",
    label: "pathforward-specialist-curator",
    sublabel: "picks the one skill worth assessing",
    handles: [{ id: "in", type: "target", position: Left }],
  },
  {
    id: "generator",
    type: "agent",
    x: 740,
    y: 200,
    tag: "LLM AGENT",
    label: "pathforward-specialist-generator",
    sublabel: "writes the assessment · azure_ai_search",
    handles: [
      { id: "in", type: "target", position: Left },
      { id: "out", type: "source", position: Right },
    ],
  },
  {
    id: "critic",
    type: "agent",
    x: 740,
    y: 360,
    tag: "LLM AGENT",
    label: "pathforward-specialist-critic",
    sublabel: "advisory review — recommends, never decides",
    handles: [{ id: "in", type: "target", position: Left }],
  },
  {
    id: "planner",
    type: "agent",
    x: 740,
    y: 520,
    tag: "LLM AGENT",
    label: "pathforward-specialist-planner",
    sublabel: "capacity-aware learning plan",
    handles: [{ id: "in", type: "target", position: Left }],
  },
  {
    id: "insights",
    type: "agent",
    x: 740,
    y: 680,
    tag: "LLM AGENT",
    label: "pathforward-specialist-insights-fabric",
    sublabel: "cohort story · fabric_mcp",
    handles: [
      { id: "in", type: "target", position: Left },
      { id: "out", type: "source", position: Right },
    ],
  },
  {
    id: "gate",
    type: "code",
    x: 1160,
    y: 160,
    tag: "DETERMINISTIC CODE",
    label: "Evidence Gate",
    sublabel: "verify_assessment_and_issue_mint_request · Azure Function MCP",
    handles: [
      { id: "in", type: "target", position: Left },
      { id: "up", type: "source", position: Top },
      { id: "down", type: "source", position: Bottom },
    ],
  },
  {
    id: "mint",
    type: "code",
    x: 1160,
    y: 430,
    tag: "DETERMINISTIC CODE",
    label: "Governed Mint",
    sublabel: "pathforward_mint_credential · requires approval",
    handles: [
      { id: "in", type: "target", position: Left },
      { id: "in-top", type: "target", position: Top },
      { id: "in-bottom", type: "target", position: Bottom, offset: "30%" },
      { id: "down", type: "source", position: Bottom, offset: "70%" },
      { id: "out", type: "source", position: Right },
    ],
  },
  {
    id: "fabric-mcp",
    type: "code",
    x: 1160,
    y: 680,
    tag: "DETERMINISTIC CODE",
    label: "Fabric MCP server",
    sublabel: "Azure Function · read-only",
    handles: [
      { id: "in", type: "target", position: Left },
      { id: "out", type: "source", position: Right },
      { id: "down", type: "source", position: Bottom },
    ],
  },
  {
    id: "approval",
    type: "user",
    x: 1000,
    y: 560,
    tag: "HUMAN",
    label: "Human approval",
    sublabel: "nothing mints without it",
    handles: [{ id: "up", type: "source", position: Top }],
  },
  {
    id: "azure-search",
    type: "service",
    x: 1560,
    y: 140,
    tag: "AZURE SERVICE",
    label: "Azure AI Search",
    sublabel: "approved evidence corpus",
    handles: [{ id: "in", type: "target", position: Left }],
  },
  {
    id: "credential",
    type: "code",
    x: 1560,
    y: 430,
    tag: "OUTCOME",
    label: "Verifiable credential",
    sublabel: "status=minted · causal spine intact",
    handles: [{ id: "in", type: "target", position: Left }],
  },
  {
    id: "fabric",
    type: "service",
    x: 1560,
    y: 680,
    tag: "AZURE SERVICE",
    label: "Microsoft Fabric",
    sublabel: "live cohort data agent",
    handles: [{ id: "in", type: "target", position: Left }],
  },
  {
    id: "app-insights",
    type: "service",
    x: 1560,
    y: 880,
    tag: "AZURE SERVICE",
    label: "Application Insights",
    sublabel: "pathforward.mcp.* telemetry",
    handles: [{ id: "in", type: "target", position: Left }],
  },
  {
    id: "abstain",
    type: "code",
    x: 560,
    y: 880,
    tag: "FAIL CLOSED",
    label: "ABSTAIN",
    sublabel: "no proof → no credential. By design.",
    handles: [{ id: "in-top", type: "target", position: Top }],
  },
];

export const TOUR_NODES: TourNode[] = NODE_SPECS.map((spec) => ({
  id: spec.id,
  type: spec.type,
  position: { x: spec.x, y: spec.y },
  draggable: false,
  connectable: false,
  selectable: false,
  data: {
    tag: spec.tag,
    label: spec.label,
    sublabel: spec.sublabel,
    status: "dormant",
    focused: false,
    handles: spec.handles,
  },
}));

interface EdgeSpec {
  id: EdgeId;
  source: NodeId;
  sourceHandle: string;
  target: NodeId;
  targetHandle: string;
  label?: string;
  telemetry?: boolean;
}

const EDGE_SPECS: EdgeSpec[] = [
  { id: "e-user-orch", source: "user", sourceHandle: "out", target: "orchestrator", targetHandle: "in", label: "prompt" },
  { id: "e-orch-curator", source: "orchestrator", sourceHandle: "out", target: "curator", targetHandle: "in", label: "pathforward-a2a-curator" },
  { id: "e-orch-generator", source: "orchestrator", sourceHandle: "out", target: "generator", targetHandle: "in", label: "pathforward-a2a-generator" },
  { id: "e-orch-critic", source: "orchestrator", sourceHandle: "out", target: "critic", targetHandle: "in", label: "pathforward-a2a-critic" },
  { id: "e-orch-planner", source: "orchestrator", sourceHandle: "out", target: "planner", targetHandle: "in", label: "pathforward-a2a-planner" },
  { id: "e-orch-insights", source: "orchestrator", sourceHandle: "out", target: "insights", targetHandle: "in", label: "pathforward-a2a-insights" },
  { id: "e-gen-search", source: "generator", sourceHandle: "out", target: "azure-search", targetHandle: "in", label: "azure_ai_search" },
  { id: "e-orch-gate", source: "orchestrator", sourceHandle: "out", target: "gate", targetHandle: "in", label: "verify_assessment_and_issue_mint_request" },
  { id: "e-gate-feedback", source: "gate", sourceHandle: "up", target: "orchestrator", targetHandle: "in-top", label: "rejected → failed_criteria + remediation" },
  { id: "e-gate-mint", source: "gate", sourceHandle: "down", target: "mint", targetHandle: "in-top", label: "verified → sealed mint_request" },
  { id: "e-orch-mint", source: "orchestrator", sourceHandle: "out", target: "mint", targetHandle: "in", label: "pathforward_mint_credential" },
  { id: "e-approval-mint", source: "approval", sourceHandle: "up", target: "mint", targetHandle: "in-bottom", label: "explicit approval" },
  { id: "e-mint-cred", source: "mint", sourceHandle: "out", target: "credential", targetHandle: "in", label: "status=minted" },
  { id: "e-insights-fabricmcp", source: "insights", sourceHandle: "out", target: "fabric-mcp", targetHandle: "in", label: "fabric_mcp" },
  { id: "e-fabricmcp-fabric", source: "fabric-mcp", sourceHandle: "out", target: "fabric", targetHandle: "in", label: 'source="fabric-live"' },
  { id: "e-gate-tel", source: "gate", sourceHandle: "down", target: "app-insights", targetHandle: "in", label: "pathforward.mcp.gate", telemetry: true },
  { id: "e-mint-tel", source: "mint", sourceHandle: "down", target: "app-insights", targetHandle: "in", label: "pathforward.mcp.mint", telemetry: true },
  { id: "e-fabric-tel", source: "fabric-mcp", sourceHandle: "down", target: "app-insights", targetHandle: "in", label: "pathforward.mcp.fabric", telemetry: true },
  { id: "e-orch-abstain", source: "orchestrator", sourceHandle: "down", target: "abstain", targetHandle: "in-top", label: "abstain (fail closed)" },
];

export const TOUR_EDGES: TourEdge[] = EDGE_SPECS.map((spec) => ({
  id: spec.id,
  source: spec.source,
  sourceHandle: spec.sourceHandle,
  target: spec.target,
  targetHandle: spec.targetHandle,
  label: spec.label,
  className: spec.telemetry ? "edge-telemetry edge-dormant" : "edge-dormant",
  focusable: false,
}));

export const TOUR_NODE_IDS: readonly NodeId[] = NODE_SPECS.map((s) => s.id);
export const TOUR_EDGE_IDS: readonly EdgeId[] = EDGE_SPECS.map((s) => s.id);
export const TELEMETRY_EDGE_IDS: ReadonlySet<EdgeId> = new Set(
  EDGE_SPECS.filter((s) => s.telemetry).map((s) => s.id)
);
