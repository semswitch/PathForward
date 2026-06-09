// Demo Director: converts the static fixture into an ordered list of timed
// "beats" so the UI can replay the multi-agent run as if it were happening
// live. Pure data in -> data out; no React, no timers (useReplay owns time).
import type { Fixture } from "./contracts";

export type Actor =
  | "curator"
  | "generator"
  | "critic"
  | "gate"
  | "planner"
  | "insights"
  | "mint"
  | "system";

export type ChapterId = "graph" | "curator" | "loop" | "decision" | "plan" | "trust";

export type BeatKind =
  | "worker-intro"
  | "glassbox-base-edges"
  | "glassbox-derived-edges"
  | "curator-ranking"
  | "curator-choice"
  | "generator-proposes"
  | "critic-reviews"
  | "gate-criteria"
  | "gate-verdict"
  | "abstain"
  | "mint"
  | "causal-spine"
  | "planner"
  | "insights"
  | "closing";

export interface Beat {
  id: string;
  kind: BeatKind;
  actor: Actor;
  chapter: ChapterId;
  durationMs: number;
  /** Transcript index for loop beats; drives the gate's "attempt n/3" counter. */
  attempt?: number;
  /** Narration line for the aria-live region and the transport bar. */
  caption: string;
}

/** The loop's regenerate cap (mirrors pathforward/agents/loop.py). */
export const MAX_ATTEMPTS = 3;

/** Default pacing per beat kind — one table so total runtime stays tunable. */
export const BEAT_DURATIONS: Record<BeatKind, number> = {
  "worker-intro": 3000,
  "glassbox-base-edges": 3500,
  "glassbox-derived-edges": 4000,
  "curator-ranking": 3500,
  "curator-choice": 3000,
  "generator-proposes": 4000,
  "critic-reviews": 3000,
  "gate-criteria": 3500,
  "gate-verdict": 3500,
  abstain: 5000,
  mint: 3500,
  "causal-spine": 4000,
  planner: 3500,
  insights: 3500,
  closing: 3000,
};

const CHAPTERS: Record<BeatKind, ChapterId> = {
  "worker-intro": "graph",
  "glassbox-base-edges": "graph",
  "glassbox-derived-edges": "graph",
  "curator-ranking": "curator",
  "curator-choice": "curator",
  "generator-proposes": "loop",
  "critic-reviews": "loop",
  "gate-criteria": "loop",
  "gate-verdict": "loop",
  abstain: "loop",
  mint: "decision",
  "causal-spine": "decision",
  planner: "plan",
  insights: "plan",
  closing: "trust",
};

const ACTORS: Record<BeatKind, Actor> = {
  "worker-intro": "system",
  "glassbox-base-edges": "system",
  "glassbox-derived-edges": "system",
  "curator-ranking": "curator",
  "curator-choice": "curator",
  "generator-proposes": "generator",
  "critic-reviews": "critic",
  "gate-criteria": "gate",
  "gate-verdict": "gate",
  abstain: "gate",
  mint: "mint",
  "causal-spine": "mint",
  planner: "planner",
  insights: "insights",
  closing: "system",
};

function beat(kind: BeatKind, caption: string, attempt?: number): Beat {
  return {
    id: attempt === undefined ? kind : `attempt-${attempt}/${kind}`,
    kind,
    actor: ACTORS[kind],
    chapter: CHAPTERS[kind],
    durationMs: BEAT_DURATIONS[kind],
    ...(attempt === undefined ? {} : { attempt }),
    caption,
  };
}

export function buildBeats(fixture: Fixture): Beat[] {
  const { worker, glassbox, curator, loop, plan, insights } = fixture;
  const derivedCount = glassbox.edges.filter((e) => e.derived).length;
  const beats: Beat[] = [
    beat(
      "worker-intro",
      `Meet ${worker.id}: ${worker.current_role_title}, retraining as ${worker.target_role}.`,
    ),
    beat(
      "glassbox-base-edges",
      "The ontology: held skills, role requirements, certifications — base facts.",
    ),
    beat(
      "glassbox-derived-edges",
      `${derivedCount} derived edges appear — CertGap and readiness are inferred, not in the raw data.`,
    ),
    beat(
      "curator-ranking",
      `Curator ranks ${curator.ranking.length} admissible gap skills by adjacency and certification coverage.`,
    ),
    beat(
      "curator-choice",
      `Curator selects ${curator.chosen_skill_id}${curator.corrected ? " — deterministic admissibility gate applied a correction" : ""}.`,
    ),
  ];

  loop.transcript.forEach((t, i) => {
    const cites = t.item.cited_ref_ids.length;
    beats.push(
      beat(
        "generator-proposes",
        `Generator proposes attempt ${i + 1} — ${cites > 0 ? `cites ${cites} reference${cites === 1 ? "" : "s"}` : "cites nothing"}.`,
        i,
      ),
    );
    if (t.critic) {
      beats.push(
        beat("critic-reviews", `Critic (advisory only): recommends ${t.critic.recommendation}.`, i),
      );
    }
    beats.push(
      beat(
        "gate-criteria",
        "Evidence Gate runs five deterministic checks — code, not a model.",
        i,
      ),
    );
    const failed = t.verdict.failed_reasons.map((fr) => fr.criterion).join(", ");
    beats.push(
      beat(
        "gate-verdict",
        t.verdict.passed
          ? "Evidence Gate: PASS — all five criteria hold."
          : `Evidence Gate: REJECT — ${failed || "criteria failed"}. ${i + 1 < MAX_ATTEMPTS ? "Regenerating." : "Attempts exhausted."}`,
        i,
      ),
    );
  });

  if (loop.status === "verified") {
    beats.push(
      beat("mint", "Credential minted — W3C VC 2.0 shape, citation-backed."),
      beat(
        "causal-spine",
        `Causal spine: the credential cites ${fixture.driving_edge_id} — the same edge that drove the loop.`,
      ),
      beat(
        "planner",
        `Planner schedules ${plan.weeks} weeks within ${plan.weekly_capacity_hours} h/week capacity.`,
      ),
    );
    if (insights) {
      beats.push(
        beat(
          "insights",
          `Program Insights: percentile ${insights.worker_comparison.percentile} in the cohort (${insights.source}).`,
        ),
      );
    }
  } else {
    beats.push(
      beat(
        "abstain",
        "Fail-closed ABSTAIN — the gate could not verify, so no credential is minted. By design.",
      ),
    );
  }

  beats.push(beat("closing", "Replay complete — the trust metrics are on the table."));
  return beats;
}
