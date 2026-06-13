import type { EdgeId, NodeId, NodeStatus } from "./graph";
import { TOUR_NODE_IDS } from "./graph";
import type { TourBaseline } from "./baseline";
import { BASELINE_RUN } from "./baseline";

/*
 * The scripted tour: ordered beats over the architecture graph, narrating the
 * real 2026-06-12 live run (see baseline.ts). Beats are keyed to cumulative
 * startMs — when Azure TTS narration lands, measured audio offsets replace
 * these values (retimeBeats + narration.manifest.json) and nothing downstream
 * changes.
 *
 * "Why-driven" intro: the user's chapter prose (fair test for the worker,
 * undeniable proof for the enterprise) partitioned into per-beat sentences so
 * the choreography keeps its moments — the cast contrast, the gate's red→green
 * arc, the abstain. Two channels, on purpose:
 *   caption   = the EYES. Exact runtime vocabulary — agent names, tool ids,
 *               gate criteria, telemetry events, the cited gap edge.
 *   narration = the EARS. The user's plain, why-first prose, verbatim.
 *               (Tests enforce: no underscores or "::" in narration.)
 */

export type ChapterId =
  | "meet-the-flow"
  | "route"
  | "grounded-generation"
  | "gate-rejects"
  | "reflect-retry"
  | "verified-insights"
  | "approval-mint"
  | "abstain";

export const CHAPTER_LABELS: Record<ChapterId, string> = {
  "meet-the-flow": "Meet the flow",
  route: "Route reasoning",
  "grounded-generation": "Grounded generation",
  "gate-rejects": "The Gate says no",
  "reflect-retry": "Reflection & retry",
  "verified-insights": "Verified + insights",
  "approval-mint": "Approval & mint",
  abstain: "ABSTAIN",
};

export const CHAPTER_ORDER: readonly ChapterId[] = [
  "meet-the-flow",
  "route",
  "grounded-generation",
  "gate-rejects",
  "reflect-retry",
  "verified-insights",
  "approval-mint",
  "abstain",
];

export interface CameraTarget {
  nodeIds: NodeId[];
  padding?: number;
}

export interface TourBeat {
  id: string;
  chapter: ChapterId;
  /** Cumulative start time — the audio-clock alignment key. */
  startMs: number;
  durationMs: number;
  caption: string;
  /** Spoken narration for TTS generation; may differ from the caption. */
  narration: string;
  /** Lit "focused" (pulsing) during this beat only. */
  focusNodeIds: NodeId[];
  /** Glowing/flowing during this beat only. */
  activeEdgeIds: EdgeId[];
  /** null = hold the current camera. */
  camera: CameraTarget | null;
  /** Sticky node-status updates, applied from this beat onward. */
  statusChanges?: Partial<Record<NodeId, NodeStatus>>;
}

/** Beat without startMs — buildTourScript assigns cumulative times. */
type BeatSpec = Omit<TourBeat, "startMs">;

const ALL_NODES: NodeId[] = [...TOUR_NODE_IDS];
const AGENT_NODES: NodeId[] = [
  "orchestrator",
  "curator",
  "generator",
  "critic",
  "planner",
  "insights",
];
const CODE_NODES: NodeId[] = ["gate", "mint", "fabric-mcp", "abstain"];

export function buildTourScript(
  baseline: TourBaseline = BASELINE_RUN
): TourBeat[] {
  const failedCriteria = baseline.attempt1FailedCriteria.join(" and ");
  const avgReadiness = baseline.cohortAvgReadiness.toFixed(2);
  const workerReadiness = baseline.workerReadiness.toFixed(2);

  const specs: BeatSpec[] = [
    // ——— Meet the flow ———
    {
      id: "b-welcome",
      chapter: "meet-the-flow",
      durationMs: 13000,
      caption:
        "PathForward — enterprise talent mobility you can trust. Proof for the enterprise, a fair shot for the worker. Every box is a live Microsoft Foundry component, shown by its real runtime name.",
      narration:
        "The hardest part of advancing your career isn't learning the skills — it's proving you have them. Meet PathForward. We built PathForward to solve enterprise talent mobility.",
      focusNodeIds: [],
      activeEdgeIds: [],
      camera: { nodeIds: ALL_NODES, padding: 0.1 },
    },
    {
      id: "b-promise",
      chapter: "meet-the-flow",
      durationMs: 13000,
      caption:
        "The worker needs a fair, verifiable test; the enterprise needs undeniable proof — not a resume claim, and not an AI hallucination. Watch one real request traverse the live graph.",
      narration:
        "When a worker wants to step into a new role, they need a fair test, and the enterprise needs undeniable proof. Let's watch one real request move through the map.",
      focusNodeIds: ["user"],
      activeEdgeIds: [],
      camera: { nodeIds: ["user", "orchestrator"] },
    },

    // ——— Route reasoning ———
    {
      id: "b-agents",
      chapter: "route",
      durationMs: 9000,
      caption: `Worker ${baseline.workerId} requests role ${baseline.targetRoleId}; the request enters at pathforward-orchestrator (Foundry Prompt Agent ${baseline.orchestratorVersion}). Glowing nodes are LLM agents — they reason, draft, and explain.`,
      narration:
        "PathForward uses AI, but it doesn't trust it blindly. The glowing boxes are AI agents that analyze and write.",
      focusNodeIds: [...AGENT_NODES],
      activeEdgeIds: ["e-user-orch"],
      camera: { nodeIds: [...AGENT_NODES] },
      statusChanges: { user: "completed", orchestrator: "active" },
    },
    {
      id: "b-code",
      chapter: "route",
      durationMs: 13000,
      caption:
        "Sharp, mint-edged nodes are deterministic code. Agents may reason; only code may verify and mint. The orchestrator routes — but holds no action that certifies its own work.",
      narration:
        "But the sharp-edged boxes are plain code. In PathForward, agents are allowed to reason, but only the code can verify. That guarantees every credential we issue is bulletproof.",
      focusNodeIds: [...CODE_NODES],
      activeEdgeIds: [],
      camera: { nodeIds: [...CODE_NODES] },
    },

    // ——— Grounded generation ———
    {
      id: "b-curator",
      chapter: "grounded-generation",
      durationMs: 12000,
      caption: `First specialist — the curator (pathforward-a2a-curator). It ranks ${baseline.workerId}'s skill gaps and picks the one worth assessing now: skill ${baseline.skillId}.`,
      narration:
        "Here is how PathForward creates a fair assessment. When a worker applies for a role, our first agent reviews their specific skill gaps.",
      focusNodeIds: ["curator"],
      activeEdgeIds: ["e-orch-curator"],
      camera: { nodeIds: ["orchestrator", "curator"] },
      statusChanges: { curator: "active" },
    },
    {
      id: "b-generator",
      chapter: "grounded-generation",
      durationMs: 13000,
      caption:
        "The generator drafts the assessment item, grounding every claim through its azure_ai_search tool — only documents actually retrieved from the approved corpus. No source, no question.",
      narration:
        "Another agent drafts a custom question. To prevent hallucinations, PathForward forces the AI to pull every single fact from approved company documents. No source, no question.",
      focusNodeIds: ["generator", "azure-search"],
      activeEdgeIds: ["e-orch-generator", "e-gen-search"],
      camera: { nodeIds: ["orchestrator", "generator", "azure-search"] },
      statusChanges: {
        curator: "completed",
        generator: "active",
        "azure-search": "active",
      },
    },

    // ——— The Gate says no ———
    {
      id: "b-gate",
      chapter: "gate-rejects",
      durationMs: 13000,
      caption:
        "Evidence Gate — deterministic code (verify_assessment_and_issue_mint_request), not an agent. Five checks: grounded, evidence_answerable, single_correct, no_leakage, numeric_valid.",
      narration:
        "Once drafted, the question hits the Evidence Gate. This is strict code, not AI. It runs hard checks: is the evidence real? Is it fair to the worker?",
      focusNodeIds: ["gate"],
      activeEdgeIds: ["e-orch-gate"],
      camera: { nodeIds: ["orchestrator", "gate"] },
      statusChanges: {
        generator: "completed",
        "azure-search": "completed",
        gate: "active",
      },
    },
    {
      id: "b-reject",
      chapter: "gate-rejects",
      durationMs: 13000,
      caption: `Attempt 1 fails on ${failedCriteria}; status=rejected, logged to Application Insights (pathforward.mcp.gate). Nothing runs on the honor system.`,
      narration:
        "In this run, the first attempt fails. The evidence wasn't strong enough. The Gate says no, logging the rejection to keep the PathForward system completely auditable.",
      focusNodeIds: ["gate", "app-insights"],
      activeEdgeIds: ["e-gate-tel"],
      camera: { nodeIds: ["gate", "app-insights"] },
      statusChanges: { gate: "rejected", "app-insights": "active" },
    },

    // ——— Reflection & retry ———
    {
      id: "b-feedback",
      chapter: "reflect-retry",
      durationMs: 13000,
      caption:
        "Bounded feedback: only the failed criteria and remediation flow back — never the answer. The generator rewrites and re-grounds for attempt 2.",
      narration:
        "But PathForward is built to recover. The Gate sends back exact notes on what failed. The AI reflects, fixes the question, and grounds it in better evidence.",
      focusNodeIds: ["gate", "generator"],
      activeEdgeIds: ["e-gate-feedback", "e-orch-generator", "e-gen-search"],
      camera: { nodeIds: ["orchestrator", "gate", "generator"] },
      statusChanges: { generator: "active", gate: "active" },
    },
    {
      id: "b-verified",
      chapter: "reflect-retry",
      durationMs: 10000,
      caption:
        "Attempt 2 passes all five checks. The gate flips to verified and issues a sealed mint_request token — the one artifact only it can create.",
      narration:
        "This time, it passes all checks, and the Gate issues a secure token. The worker gets a fair, verified test.",
      focusNodeIds: ["gate"],
      activeEdgeIds: ["e-orch-gate", "e-gate-mint"],
      camera: { nodeIds: ["gate", "mint"] },
      statusChanges: { generator: "completed", gate: "verified" },
    },

    // ——— Verified + insights ———
    {
      id: "b-insights",
      chapter: "verified-insights",
      durationMs: 14000,
      caption: `Insights asks Microsoft Fabric's live data agent: ${baseline.cohortSize} workers chasing ${baseline.targetRoleId}, average readiness ${avgReadiness}, ${baseline.workerId} at ${workerReadiness} — every number source="fabric-live", read not invented.`,
      narration:
        "PathForward does more than just test; it guides. With the assessment passed, the system pulls live data to show how this worker compares to peers aiming for the exact same role.",
      focusNodeIds: ["insights", "fabric-mcp", "fabric"],
      activeEdgeIds: [
        "e-orch-insights",
        "e-insights-fabricmcp",
        "e-fabricmcp-fabric",
      ],
      camera: { nodeIds: ["insights", "fabric-mcp", "fabric"] },
      statusChanges: {
        insights: "active",
        "fabric-mcp": "active",
        fabric: "active",
      },
    },
    {
      id: "b-roadmap",
      chapter: "verified-insights",
      durationMs: 6500,
      caption:
        "The planner turns the verified result and cohort data into a capacity-aware learning roadmap — advisory, deliberately off the trust path.",
      narration:
        "PathForward gives them a realistic, data-driven roadmap for their career.",
      focusNodeIds: ["planner"],
      activeEdgeIds: ["e-orch-planner"],
      camera: { nodeIds: ["orchestrator", "planner"] },
      statusChanges: {
        planner: "active",
        insights: "completed",
        "fabric-mcp": "completed",
        fabric: "completed",
      },
    },

    // ——— Approval & mint ———
    {
      id: "b-twokeys",
      chapter: "approval-mint",
      durationMs: 11000,
      caption:
        "Two keys to mint: the gate's sealed token + explicit human approval. The orchestrator can request approval — it cannot grant it.",
      narration:
        "To actually issue the credential, PathForward requires two keys: the system's mathematically secure token, and a human clicking approve.",
      focusNodeIds: ["approval", "mint"],
      activeEdgeIds: ["e-approval-mint", "e-orch-mint"],
      camera: { nodeIds: ["approval", "mint"] },
      statusChanges: { approval: "active" },
    },
    {
      id: "b-mint",
      chapter: "approval-mint",
      durationMs: 9500,
      caption: `pathforward_mint_credential re-checks readiness and the causal spine, then issues a verifiable credential for skill ${baseline.skillId} toward ${baseline.targetRoleId} — citing the gap edge that began this run: ${baseline.citedEdgeId}.`,
      narration:
        "The AI cannot mint a credential on its own. It only prepares the proof for a human to validate.",
      focusNodeIds: ["mint", "credential"],
      activeEdgeIds: ["e-mint-cred", "e-mint-tel"],
      camera: { nodeIds: ["mint", "credential"] },
      statusChanges: { approval: "completed", mint: "minted", credential: "minted" },
    },

    // ——— ABSTAIN ———
    {
      id: "b-abstain",
      chapter: "abstain",
      durationMs: 13000,
      caption:
        "No proof, no credential: after three failed attempts — or no assessable path — the route ends at ABSTAIN (status=abstained): no citations, no approval, no credential.",
      narration:
        "And what if the proof just isn't there? After three tries, PathForward does what most AI systems won't: it stops. It won't issue a credential.",
      focusNodeIds: ["abstain"],
      activeEdgeIds: ["e-orch-abstain"],
      camera: { nodeIds: ["orchestrator", "abstain"] },
      statusChanges: { abstain: "abstained" },
    },
    {
      id: "b-closing",
      chapter: "abstain",
      durationMs: 12000,
      caption:
        "Agents reason, code notarizes, humans approve, telemetry remembers. PathForward champions the worker and protects the enterprise — built on proof, end to end.",
      narration:
        "PathForward is designed to say not yet, rather than guess. It is a system built on proof — championing the worker while protecting the enterprise.",
      focusNodeIds: [],
      activeEdgeIds: [],
      camera: { nodeIds: ALL_NODES, padding: 0.1 },
    },
  ];

  let cursor = 0;
  return specs.map((spec) => {
    const beat: TourBeat = { ...spec, startMs: cursor };
    cursor += spec.durationMs;
    return beat;
  });
}

export function totalDurationMs(beats: TourBeat[]): number {
  if (beats.length === 0) return 0;
  const last = beats[beats.length - 1];
  return last.startMs + last.durationMs;
}
