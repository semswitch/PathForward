// TypeScript contracts mirroring the Python fixture (scripts/export_web_fixture.py).
// Keep in sync with pathforward/iq/models.py and pathforward/agents/types.py.

export interface GlassBoxEdge {
  id: string;
  type: "has" | "requires" | "certifies" | "targets" | "certgap" | "readiness";
  source_id: string;
  target_id: string;
  derived: boolean;
  derivation_rule: string | null;
  source_ref_ids: string[];
  provenance: string;
  effective_at: string;
  confidence: number;
  weight: number | null;
  source_badge: string;
}

export interface GlassBoxNode {
  id: string;
  kind: "worker" | "role" | "skill" | "certification";
  label: string;
  [extra: string]: unknown;
}

export interface GlassBox {
  nodes: GlassBoxNode[];
  edges: GlassBoxEdge[];
  meta: {
    worker_id: string;
    target_role_id: string;
    cert_gap_skill_ids: string[];
    readiness: number;
    derivation_version: string;
  };
}

export interface AssessmentItem {
  id: string;
  targeted_skill_id: string;
  driving_edge_id: string;
  stem: string;
  options: string[];
  answer_index: number;
  cited_ref_ids: string[];
  numeric_claim: string | null;
  attempt: number;
}

export interface Verdict {
  passed: boolean;
  criteria: Record<string, boolean>;
  failed_reasons: { criterion: string; reason: string; citation: string[] }[];
  numeric_ok: boolean | null;
}

export interface CriticConcern {
  criterion_name: string;
  severity: string;
}

export interface CriticReview {
  recommendation: "pass" | "repair" | "reject";
  concerns: CriticConcern[];
  advisory_notes: string;
}

export interface LoopResult {
  status: "verified" | "abstained";
  driving_edge_id: string;
  targeted_skill_id: string;
  attempts: number;
  item: AssessmentItem | null;
  verdict: Verdict | null;
  transcript: { attempt: number; item: AssessmentItem; critic: CriticReview | null; verdict: Verdict }[];
  citations: string[];
}

export interface CuratorDecision {
  worker_id: string;
  role_id: string;
  admissible_skill_ids: string[];
  ranking: string[];
  chosen_skill_id: string;
  chosen_edge_id: string;
  rationale: Record<string, string>;
  corrected: boolean;
}

export interface PlannedPhase {
  week: number;
  skill_id: string;
  hours: number;
  cert_id: string;
}

export interface LearningPlan {
  worker_id: string;
  phases: PlannedPhase[];
  total_hours: number;
  weekly_capacity_hours: number;
  weeks: number;
  capacity_respected: boolean;
  corrected: boolean;
  accessibility_adaptations: string[];
  numeric_check: { claim?: string; ok?: boolean; detail?: string };
  rationale: string;
}

// Program Insights (read-only cohort/program reasoning; advisory, off the credential trust path).
// Every number is code-computed by pathforward/iq/cohort.py; `narrative` is display-only model prose.
export interface SkillGap {
  skill_id: string;
  name: string;
  domain: string;
  gap_count: number;
  assessable: boolean;
}

export interface RoleCohort {
  role_id: string;
  role_name: string;
  n_workers: number;
  mean_readiness: number;
  median_readiness: number;
  bottleneck_skills: SkillGap[];
  as_of: string;
  derivation_version: string;
}

export interface WorkerCohortComparison {
  worker_id: string;
  role_id: string;
  worker_readiness: number;
  cohort_mean_readiness: number;
  cohort_median_readiness: number;
  n_cohort: number;
  delta_vs_mean: number;
  rank: number;
  percentile: number;
}

export interface ProgramAggregates {
  n_workers: number;
  n_roles: number;
  overall_mean_readiness: number;
  top_bottlenecks: SkillGap[];
  unassessable_gap_skill_ids: string[];
  as_of: string;
  derivation_version: string;
}

export interface ProgramInsights {
  worker_id: string;
  role_id: string;
  role_cohort: RoleCohort;
  worker_comparison: WorkerCohortComparison;
  program: ProgramAggregates;
  narrative: string;
  source: string; // "derivation-floor" | "fabric-live"
}

export interface Fixture {
  provenance: {
    mode: string;
    generator: string;
    curator: string;
    critic: string;
    planner: string;
    insights: string;
    fabric: string;
    fixture_export: string;
    credential_trust_boundary: string;
  };
  worker: {
    id: string;
    name: string;
    current_role_title: string;
    target_role: string;
    weekly_capacity_hours: number;
    accessibility_needs: string[];
  };
  glassbox: GlassBox;
  driving_edge_id: string;
  targeted_skill: string;
  difficulty_band: string;
  curator: CuratorDecision;
  loop: LoopResult;
  calibration: { difficulty?: number; discrimination?: number; label?: string };
  credential: Record<string, unknown>;
  plan: LearningPlan;
  insights: ProgramInsights | null;
  metrics: {
    grounded_citation_rate: string;
    attempts_to_verified: number;
    rejected_before_pass: number;
    readiness_pct: number;
    ungrounded_credentials: number;
  };
}
