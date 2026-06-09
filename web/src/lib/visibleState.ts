// Maps (fixture, beats, beatIndex) -> what each panel should currently show.
// Pure and stateless so the replay is scrubbable in both directions and the
// final beat trivially yields the fully-visible page.
import type { Fixture } from "./contracts";
import type { Beat } from "./director";

export interface VisibleState {
  glassbox: { showBaseEdges: boolean; showDerivedEdges: boolean; spineHighlight: boolean };
  curator: { showRanking: boolean; showChoice: boolean };
  arena: {
    /** Transcript entries fully revealed (verdict included); rejected ones stay visible. */
    revealedAttempts: number;
    /** Transcript index currently being revealed step-by-step, if any. */
    currentAttempt: number | null;
    stemVisible: boolean;
    criticVisible: boolean;
    /** How many of the five gate criteria badges are revealed for currentAttempt. */
    criteriaRevealed: number;
    verdictVisible: boolean;
    showAbstain: boolean;
  };
  trust: { showCredential: boolean; spineHighlight: boolean; showMetrics: boolean };
  plan: { visible: boolean };
  insights: { visible: boolean };
}

const CRITERIA_COUNT = 5;

export function deriveVisibleState(
  _fixture: Fixture,
  beats: Beat[],
  beatIndex: number,
): VisibleState {
  const seen = beats.slice(0, Math.max(0, Math.min(beatIndex, beats.length - 1)) + 1);
  const has = (kind: Beat["kind"]) => seen.some((b) => b.kind === kind);

  const verdicted = seen.filter((b) => b.kind === "gate-verdict").length;
  const started = new Set(
    seen.filter((b) => b.kind === "generator-proposes").map((b) => b.attempt),
  ).size;
  const currentAttempt = started > verdicted ? started - 1 : null;
  const forCurrent = (kind: Beat["kind"]) =>
    currentAttempt !== null &&
    seen.some((b) => b.kind === kind && b.attempt === currentAttempt);

  return {
    glassbox: {
      showBaseEdges: has("glassbox-base-edges"),
      showDerivedEdges: has("glassbox-derived-edges"),
      spineHighlight: has("causal-spine"),
    },
    curator: {
      showRanking: has("curator-ranking"),
      showChoice: has("curator-choice"),
    },
    arena: {
      revealedAttempts: verdicted,
      currentAttempt,
      stemVisible: currentAttempt !== null,
      criticVisible: forCurrent("critic-reviews"),
      criteriaRevealed: forCurrent("gate-criteria") ? CRITERIA_COUNT : 0,
      verdictVisible: verdicted > 0,
      showAbstain: has("abstain"),
    },
    trust: {
      showCredential: has("mint"),
      spineHighlight: has("causal-spine"),
      showMetrics: has("closing"),
    },
    plan: { visible: has("planner") },
    insights: { visible: has("insights") },
  };
}
