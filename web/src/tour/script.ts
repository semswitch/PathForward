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
 * caption = displayed text. narration = spoken text (written for the ear:
 * no literal underscores, ids, or punctuation soup).
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
      durationMs: 7000,
      caption:
        "This is PathForward's real production flow — every box is a live component in Microsoft Foundry, drawn with its real name. Press play and watch one worker's request move through it.",
      narration:
        "This is PathForward's real production flow. Every box you see is a live component running in Microsoft Foundry, drawn with its real name. Let's follow one worker's request through the whole system.",
      focusNodeIds: [],
      activeEdgeIds: [],
      camera: { nodeIds: ALL_NODES, padding: 0.1 },
    },
    {
      id: "b-cast-agents",
      chapter: "meet-the-flow",
      durationMs: 7000,
      caption:
        "Rounded, glowing nodes are LLM agents — they reason, rank, write, and narrate. PathForward runs six of them as versioned Microsoft Foundry agents.",
      narration:
        "The rounded, glowing nodes are language model agents. They reason, rank, write, and narrate. PathForward runs six of them, as versioned Microsoft Foundry agents.",
      focusNodeIds: [
        "orchestrator",
        "curator",
        "generator",
        "critic",
        "planner",
        "insights",
      ],
      activeEdgeIds: [],
      camera: {
        nodeIds: [
          "orchestrator",
          "curator",
          "generator",
          "critic",
          "planner",
          "insights",
        ],
      },
    },
    {
      id: "b-cast-code",
      chapter: "meet-the-flow",
      durationMs: 7500,
      caption:
        "Sharp, mint-edged nodes are deterministic code. They hold the power the agents never get: verifying evidence and minting credentials. Agents reason — code notarizes.",
      narration:
        "The sharp, mint-edged nodes are deterministic code. They hold the power the agents never get: verifying evidence, and minting credentials. Agents reason. Code notarizes.",
      focusNodeIds: ["gate", "mint", "fabric-mcp", "abstain"],
      activeEdgeIds: [],
      camera: { nodeIds: ["gate", "mint", "fabric-mcp", "abstain"] },
    },

    // ——— Route reasoning ———
    {
      id: "b-prompt",
      chapter: "route",
      durationMs: 7000,
      caption: `Worker ${baseline.workerId} wants to move into the cloud role ${baseline.targetRoleId}. Their request lands on the orchestrator — a Microsoft Foundry Prompt Agent (${baseline.orchestratorVersion}) that loads its /pathforward Skill.`,
      narration:
        "Our worker wants to move into a cloud role. Their request lands on the orchestrator — a Microsoft Foundry prompt agent that starts by loading its PathForward skill.",
      focusNodeIds: ["user", "orchestrator"],
      activeEdgeIds: ["e-user-orch"],
      camera: { nodeIds: ["user", "orchestrator"] },
      statusChanges: { user: "completed", orchestrator: "active" },
    },
    {
      id: "b-allowed",
      chapter: "route",
      durationMs: 8000,
      caption:
        "The orchestrator may only choose from eight allowed moves — curate, assess, reflect_retry, plan, insights, request_approval, mint_if_verified, abstain. Deterministic validation rejects anything else.",
      narration:
        "The orchestrator can only choose from eight allowed moves — curate, assess, reflect and retry, plan, insights, request approval, mint if verified, or abstain. Deterministic validation rejects anything else.",
      focusNodeIds: ["orchestrator"],
      activeEdgeIds: [],
      camera: { nodeIds: ["orchestrator"], padding: 0.4 },
    },
    {
      id: "b-forbidden",
      chapter: "route",
      durationMs: 7500,
      caption:
        "Five actions are forbidden outright: mint, verify, set_verified, override_gate, issue_credential. The reasoning agent has no path to certify its own work.",
      narration:
        "And five actions are forbidden outright: mint, verify, set verified, override gate, and issue credential. The reasoning agent simply has no path to certify its own work.",
      focusNodeIds: ["orchestrator", "gate", "mint"],
      activeEdgeIds: [],
      camera: { nodeIds: ["orchestrator", "gate", "mint"] },
    },

    // ——— Grounded generation ———
    {
      id: "b-curator",
      chapter: "grounded-generation",
      durationMs: 7000,
      caption: `First move: the curator. Over an agent-to-agent call (pathforward-a2a-curator) it ranks ${baseline.workerId}'s skill gaps and picks the one skill worth assessing — ${baseline.skillId}.`,
      narration:
        "First move: the curator. Over an agent-to-agent call, it ranks the worker's skill gaps, and picks the one skill worth assessing right now.",
      focusNodeIds: ["curator"],
      activeEdgeIds: ["e-orch-curator"],
      camera: { nodeIds: ["orchestrator", "curator"] },
      statusChanges: { curator: "active" },
    },
    {
      id: "b-generator",
      chapter: "grounded-generation",
      durationMs: 7500,
      caption:
        "The generator writes an assessment item, grounding every claim through its azure_ai_search tool — it can only cite documents it actually retrieved from the approved corpus.",
      narration:
        "Next, the generator writes an assessment item, grounding every claim through Azure AI Search. It can only cite documents it actually retrieved from the approved corpus.",
      focusNodeIds: ["generator", "azure-search"],
      activeEdgeIds: ["e-orch-generator", "e-gen-search"],
      camera: { nodeIds: ["orchestrator", "generator", "azure-search"] },
      statusChanges: {
        curator: "completed",
        generator: "active",
        "azure-search": "active",
      },
    },
    {
      id: "b-critic",
      chapter: "grounded-generation",
      durationMs: 7000,
      caption:
        "The critic reviews the draft for fairness, ambiguity, and answerability. It recommends — pass, repair, or reject — but it never decides. Advice only.",
      narration:
        "The critic reviews the draft for fairness, ambiguity, and answerability. It recommends — pass, repair, or reject — but it never decides. Advice only.",
      focusNodeIds: ["critic"],
      activeEdgeIds: ["e-orch-critic"],
      camera: { nodeIds: ["orchestrator", "critic"] },
      statusChanges: {
        generator: "completed",
        "azure-search": "completed",
        critic: "active",
      },
    },

    // ——— The Gate says no ———
    {
      id: "b-gate-intro",
      chapter: "gate-rejects",
      durationMs: 7000,
      caption:
        "Now the draft faces the Evidence Gate — not an agent, a deterministic Azure Function called over MCP: verify_assessment_and_issue_mint_request.",
      narration:
        "Now the draft faces the Evidence Gate. Not an agent — a deterministic Azure Function, called over MCP. Its one job: verify the assessment, and issue a mint request.",
      focusNodeIds: ["gate"],
      activeEdgeIds: ["e-orch-gate"],
      camera: { nodeIds: ["orchestrator", "gate"] },
      statusChanges: { critic: "completed", gate: "active" },
    },
    {
      id: "b-criteria",
      chapter: "gate-rejects",
      durationMs: 7500,
      caption:
        "Five hard criteria, checked in code: grounded, evidence_answerable, single_correct, no_leakage, numeric_valid. No model opinion is consulted.",
      narration:
        "Five hard criteria, checked in code. Grounded. Answerable from the evidence. Exactly one correct option. No answer leakage. And valid arithmetic. No model opinion is consulted.",
      focusNodeIds: ["gate"],
      activeEdgeIds: [],
      camera: { nodeIds: ["gate"], padding: 0.4 },
    },
    {
      id: "b-reject",
      chapter: "gate-rejects",
      durationMs: 7000,
      caption: `In this real run, attempt one failed: the citations didn't hold up — ${failedCriteria} both failed. Status: rejected.`,
      narration:
        "In this real run, the first attempt failed. The citations didn't hold up — grounding, and answerability from evidence, both failed. Status: rejected.",
      focusNodeIds: ["gate"],
      activeEdgeIds: [],
      camera: { nodeIds: ["gate"], padding: 0.4 },
      statusChanges: { gate: "rejected" },
    },
    {
      id: "b-tel-reject",
      chapter: "gate-rejects",
      durationMs: 6500,
      caption:
        "Every verdict is logged — Application Insights records pathforward.mcp.gate with pf.status=rejected. Nothing here runs on the honor system.",
      narration:
        "And every verdict is logged. Application Insights records the gate event, with status rejected. Nothing here runs on the honor system.",
      focusNodeIds: ["app-insights"],
      activeEdgeIds: ["e-gate-tel"],
      camera: { nodeIds: ["gate", "app-insights"] },
      statusChanges: { "app-insights": "active" },
    },

    // ——— Reflection & retry ———
    {
      id: "b-feedback",
      chapter: "reflect-retry",
      durationMs: 7000,
      caption:
        "The gate sends back only its failed criteria and fixed remediation strings — never the answer, never its internals. Bounded feedback, by design.",
      narration:
        "The gate sends back only its failed criteria, and fixed remediation strings. Never the answer. Never its internals. Bounded feedback, by design.",
      focusNodeIds: ["gate", "orchestrator"],
      activeEdgeIds: ["e-gate-feedback"],
      camera: { nodeIds: ["orchestrator", "gate"] },
    },
    {
      id: "b-retry",
      chapter: "reflect-retry",
      durationMs: 6500,
      caption:
        "The orchestrator plays reflect_retry: the generator rewrites the item against the remediation, re-grounding through Azure AI Search.",
      narration:
        "The orchestrator plays its reflect-and-retry move. The generator rewrites the item against that feedback, re-grounding through Azure AI Search.",
      focusNodeIds: ["generator", "azure-search"],
      activeEdgeIds: ["e-orch-generator", "e-gen-search"],
      camera: { nodeIds: ["orchestrator", "generator", "azure-search"] },
      statusChanges: { generator: "active", gate: "active" },
    },
    {
      id: "b-verified",
      chapter: "reflect-retry",
      durationMs: 7500,
      caption:
        "Attempt two passes all five criteria. The gate flips to verified — and issues the one thing only it can create: a sealed mint_request token.",
      narration:
        "Attempt two passes all five criteria. The gate flips to verified — and issues the one thing only it can create: a sealed mint request token.",
      focusNodeIds: ["gate"],
      activeEdgeIds: ["e-orch-gate", "e-gate-mint"],
      camera: { nodeIds: ["gate", "mint"] },
      statusChanges: { generator: "completed", gate: "verified" },
    },

    // ——— Verified + insights ———
    {
      id: "b-planner",
      chapter: "verified-insights",
      durationMs: 6000,
      caption:
        "With the assessment verified, the planner drafts a capacity-aware learning plan — advisory, deliberately off the trust path.",
      narration:
        "With the assessment verified, the planner drafts a learning plan that respects the worker's weekly capacity. Advisory — deliberately off the trust path.",
      focusNodeIds: ["planner"],
      activeEdgeIds: ["e-orch-planner"],
      camera: { nodeIds: ["orchestrator", "planner"] },
      statusChanges: { planner: "active" },
    },
    {
      id: "b-insights",
      chapter: "verified-insights",
      durationMs: 7500,
      caption: `The insights agent asks Microsoft Fabric's live data agent how ${baseline.workerId} sits in their cohort: ${baseline.cohortSize} workers, average readiness ${avgReadiness}, ${baseline.workerId} at ${workerReadiness}.`,
      narration: `The insights agent asks Microsoft Fabric's live data agent how our worker sits in their cohort: ${baseline.cohortSize} workers, average readiness ${avgReadiness}, our worker at ${workerReadiness}.`,
      focusNodeIds: ["insights", "fabric-mcp", "fabric"],
      activeEdgeIds: [
        "e-orch-insights",
        "e-insights-fabricmcp",
        "e-fabricmcp-fabric",
      ],
      camera: { nodeIds: ["insights", "fabric-mcp", "fabric"] },
      statusChanges: {
        planner: "completed",
        insights: "active",
        "fabric-mcp": "active",
        fabric: "active",
      },
    },
    {
      id: "b-fabric-live",
      chapter: "verified-insights",
      durationMs: 6500,
      caption:
        'Every number is source="fabric-live" — read from Fabric, never invented. The agent narrates the statistics; code computes them.',
      narration:
        "Every number is read live from Fabric — never invented. The agent narrates the statistics. Code computes them.",
      focusNodeIds: ["fabric"],
      activeEdgeIds: ["e-fabric-tel"],
      camera: { nodeIds: ["fabric-mcp", "fabric", "app-insights"] },
      statusChanges: {
        insights: "completed",
        "fabric-mcp": "completed",
        fabric: "completed",
      },
    },

    // ——— Approval & mint ———
    {
      id: "b-approval",
      chapter: "approval-mint",
      durationMs: 7000,
      caption:
        "Minting needs two keys: the gate's sealed token and a human saying yes. The orchestrator can request approval — it cannot grant it.",
      narration:
        "Minting needs two keys. The gate's sealed token — and a human saying yes. The orchestrator can request approval. It cannot grant it.",
      focusNodeIds: ["approval", "mint"],
      activeEdgeIds: ["e-approval-mint"],
      camera: { nodeIds: ["approval", "mint"] },
      statusChanges: { approval: "active" },
    },
    {
      id: "b-mint",
      chapter: "approval-mint",
      durationMs: 7000,
      caption:
        "Approval granted. The MCP mint tool — pathforward_mint_credential — re-checks readiness and the causal spine, then mints.",
      narration:
        "Approval granted. The MCP mint tool re-checks readiness and the causal spine — then mints.",
      focusNodeIds: ["mint"],
      activeEdgeIds: ["e-orch-mint", "e-approval-mint"],
      camera: { nodeIds: ["mint"], padding: 0.4 },
      statusChanges: { approval: "completed", mint: "minted" },
    },
    {
      id: "b-credential",
      chapter: "approval-mint",
      durationMs: 8000,
      caption: `${baseline.workerId} now holds a credential for skill ${baseline.skillId} toward role ${baseline.targetRoleId} — citing the exact gap edge that started this run: ${baseline.citedEdgeId}. A provable chain, end to end.`,
      narration:
        "Our worker now holds a credential for the exact skill gap that started this run — citing the very edge in the graph that drove it. A provable chain, end to end.",
      focusNodeIds: ["credential"],
      activeEdgeIds: ["e-mint-cred", "e-mint-tel"],
      camera: { nodeIds: ["mint", "credential"] },
      statusChanges: { credential: "minted" },
    },

    // ——— ABSTAIN ———
    {
      id: "b-abstain-path",
      chapter: "abstain",
      durationMs: 7000,
      caption:
        "And when the evidence isn't there? After three failed attempts — or no assessable path at all — the route ends here: ABSTAIN.",
      narration:
        "And when the evidence isn't there? After three failed attempts — or no assessable path at all — the route ends here. Abstain.",
      focusNodeIds: ["abstain"],
      activeEdgeIds: ["e-orch-abstain"],
      camera: { nodeIds: ["orchestrator", "abstain"] },
      statusChanges: { abstain: "abstained" },
    },
    {
      id: "b-abstain-meaning",
      chapter: "abstain",
      durationMs: 7000,
      caption:
        "Status abstained: no citations, no approval, no credential. PathForward would rather say “not yet” than mint a claim it can't prove.",
      narration:
        "Status: abstained. No citations. No approval. No credential. PathForward would rather say not yet, than mint a claim it can't prove.",
      focusNodeIds: ["abstain"],
      activeEdgeIds: [],
      camera: { nodeIds: ["abstain"], padding: 0.4 },
    },
    {
      id: "b-closing",
      chapter: "abstain",
      durationMs: 8000,
      caption:
        "That's the whole loop: agents reason, code notarizes, humans approve, telemetry remembers. Explore the graph freely — or replay any chapter.",
      narration:
        "And that's the whole loop. Agents reason. Code notarizes. Humans approve. And telemetry remembers. Explore the graph freely — or replay any chapter.",
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
