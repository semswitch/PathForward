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

export interface LoopResult {
  status: "verified" | "abstained";
  driving_edge_id: string;
  targeted_skill_id: string;
  attempts: number;
  item: AssessmentItem | null;
  verdict: Verdict | null;
  transcript: { attempt: number; item: AssessmentItem; verdict: Verdict }[];
  citations: string[];
}

export interface Fixture {
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
  loop: LoopResult;
  calibration: { difficulty?: number; discrimination?: number; label?: string };
  credential: Record<string, unknown>;
  metrics: {
    grounded_citation_rate: string;
    attempts_to_verified: number;
    rejected_before_pass: number;
    readiness_pct: number;
    ungrounded_credentials: number;
  };
}
