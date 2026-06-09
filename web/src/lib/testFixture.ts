// Fixture factory for unit tests. Pure-logic tests must NOT import the
// gitignored web/src/lib/fixture.json; they build a fixture here instead.
import type {
  AssessmentItem,
  CriticReview,
  Fixture,
  LoopResult,
  Verdict,
} from "./contracts";

export function makeItem(overrides: Partial<AssessmentItem> = {}): AssessmentItem {
  return {
    id: "item-S01",
    targeted_skill_id: "S01",
    driving_edge_id: "certgap::EMP-001::S01",
    stem: "Which API style is stateless by design?",
    options: ["REST", "Sticky sessions", "Stateful RPC", "Server affinity"],
    answer_index: 0,
    cited_ref_ids: ["tg-S01-1"],
    numeric_claim: null,
    attempt: 0,
    ...overrides,
  };
}

export function makeVerdict(passed: boolean, overrides: Partial<Verdict> = {}): Verdict {
  return {
    passed,
    criteria: {
      grounded: passed,
      evidence_answerable: passed,
      single_correct: true,
      no_leakage: true,
      numeric_valid: true,
    },
    failed_reasons: passed
      ? []
      : [{ criterion: "grounded", reason: "no approved citation retrieved", citation: [] }],
    numeric_ok: null,
    ...overrides,
  };
}

export function makeCritic(recommendation: CriticReview["recommendation"]): CriticReview {
  return {
    recommendation,
    concerns:
      recommendation === "pass" ? [] : [{ criterion_name: "citation-relevance", severity: "high" }],
    advisory_notes:
      recommendation === "pass" ? "clean item" : "citations do not support the stem",
  };
}

/** Default loop: attempt 0 rejected (the on-camera bluff), attempt 1 verified. */
export function makeLoop(overrides: Partial<LoopResult> = {}): LoopResult {
  const reject = makeItem({ attempt: 0, cited_ref_ids: [] });
  const pass = makeItem({ attempt: 1 });
  return {
    status: "verified",
    driving_edge_id: "certgap::EMP-001::S01",
    targeted_skill_id: "S01",
    attempts: 2,
    item: pass,
    verdict: makeVerdict(true),
    transcript: [
      { attempt: 0, item: reject, critic: makeCritic("reject"), verdict: makeVerdict(false) },
      { attempt: 1, item: pass, critic: makeCritic("pass"), verdict: makeVerdict(true) },
    ],
    citations: ["tg-S01-1"],
    ...overrides,
  };
}

/** Abstain loop: three rejected attempts, fail-closed, nothing minted. */
export function makeAbstainLoop(): LoopResult {
  const transcript = [0, 1, 2].map((i) => ({
    attempt: i,
    item: makeItem({ attempt: i, cited_ref_ids: [] }),
    critic: makeCritic("reject"),
    verdict: makeVerdict(false),
  }));
  return makeLoop({
    status: "abstained",
    attempts: 3,
    item: null,
    verdict: null,
    transcript,
    citations: [],
  });
}

export function makeFixture(overrides: Partial<Fixture> = {}): Fixture {
  return {
    provenance: {
      mode: "offline-rehearsal",
      generator: "FakeLLMClient",
      curator: "FakeLLMClient",
      critic: "FakeLLMClient",
      planner: "FakeLLMClient",
      insights: "derivation-floor",
      fabric: "not-used",
      fixture_export: "offline",
      credential_trust_boundary: "EvidenceGate+LocalNumericChecker+mint",
    },
    worker: {
      id: "EMP-001",
      name: "Test Worker",
      current_role_title: "Database Administrator",
      target_role: "Cloud Solution Architect",
      weekly_capacity_hours: 6,
      accessibility_needs: ["screen-reader-friendly"],
    },
    glassbox: {
      nodes: [
        { id: "EMP-001", kind: "worker", label: "EMP-001" },
        { id: "R-CLOUD", kind: "role", label: "Cloud Solution Architect" },
        { id: "S01", kind: "skill", label: "API Development" },
        { id: "S02", kind: "skill", label: "Networking" },
      ],
      edges: [
        {
          id: "has::EMP-001::S02",
          type: "has",
          source_id: "EMP-001",
          target_id: "S02",
          derived: false,
          derivation_rule: null,
          source_ref_ids: [],
          provenance: "seed",
          effective_at: "2026-01-01",
          confidence: 1,
          weight: null,
          source_badge: "HR system",
        },
        {
          id: "requires::R-CLOUD::S01",
          type: "requires",
          source_id: "R-CLOUD",
          target_id: "S01",
          derived: false,
          derivation_rule: null,
          source_ref_ids: [],
          provenance: "seed",
          effective_at: "2026-01-01",
          confidence: 1,
          weight: null,
          source_badge: "Fabric IQ",
        },
        {
          id: "certgap::EMP-001::S01",
          type: "certgap",
          source_id: "EMP-001",
          target_id: "S01",
          derived: true,
          derivation_rule: "requires \\ has",
          source_ref_ids: ["requires::R-CLOUD::S01"],
          provenance: "derived",
          effective_at: "2026-01-01",
          confidence: 1,
          weight: null,
          source_badge: "Fabric IQ (derived)",
        },
      ],
      meta: {
        worker_id: "EMP-001",
        target_role_id: "R-CLOUD",
        cert_gap_skill_ids: ["S01"],
        readiness: 0.5,
        derivation_version: "test-v1",
      },
    },
    driving_edge_id: "certgap::EMP-001::S01",
    targeted_skill: "API Development",
    difficulty_band: "core",
    curator: {
      worker_id: "EMP-001",
      role_id: "R-CLOUD",
      admissible_skill_ids: ["S01", "S02"],
      ranking: ["S01", "S02"],
      chosen_skill_id: "S01",
      chosen_edge_id: "certgap::EMP-001::S01",
      rationale: { S01: "closest adjacency", S02: "secondary gap" },
      corrected: false,
    },
    loop: makeLoop(),
    calibration: { difficulty: 0.4, discrimination: 0.8, label: "cold-start" },
    credential: {
      credentialSubject: { cited_edge_id: "certgap::EMP-001::S01" },
    },
    plan: {
      worker_id: "EMP-001",
      phases: [
        { week: 1, skill_id: "S01", hours: 6, cert_id: "AZ-204" },
        { week: 2, skill_id: "S01", hours: 6, cert_id: "AZ-204" },
      ],
      total_hours: 12,
      weekly_capacity_hours: 6,
      weeks: 2,
      capacity_respected: true,
      corrected: false,
      accessibility_adaptations: ["captioned videos"],
      numeric_check: { claim: "2*6=12", ok: true },
      rationale: "two focused weeks",
    },
    insights: {
      worker_id: "EMP-001",
      role_id: "R-CLOUD",
      role_cohort: {
        role_id: "R-CLOUD",
        role_name: "Cloud Solution Architect",
        n_workers: 4,
        mean_readiness: 0.45,
        median_readiness: 0.5,
        bottleneck_skills: [
          { skill_id: "S01", name: "API Development", domain: "cloud", gap_count: 3, assessable: true },
        ],
        as_of: "2026-06-01",
        derivation_version: "test-v1",
      },
      worker_comparison: {
        worker_id: "EMP-001",
        role_id: "R-CLOUD",
        worker_readiness: 0.5,
        cohort_mean_readiness: 0.45,
        cohort_median_readiness: 0.5,
        n_cohort: 4,
        delta_vs_mean: 0.05,
        rank: 2,
        percentile: 75,
      },
      program: {
        n_workers: 10,
        n_roles: 3,
        overall_mean_readiness: 0.4,
        top_bottlenecks: [],
        unassessable_gap_skill_ids: [],
        as_of: "2026-06-01",
        derivation_version: "test-v1",
      },
      narrative: "EMP-001 sits above the cohort mean.",
      source: "derivation-floor",
    },
    metrics: {
      grounded_citation_rate: "1/1",
      attempts_to_verified: 2,
      rejected_before_pass: 1,
      readiness_pct: 50,
      ungrounded_credentials: 0,
    },
    ...overrides,
  };
}

/** Fixture for the fail-closed path: 3 rejects, no credential. */
export function makeAbstainFixture(): Fixture {
  return makeFixture({ loop: makeAbstainLoop(), credential: {}, insights: null });
}
