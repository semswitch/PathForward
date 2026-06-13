/*
 * Real numbers from the live integrated baseline run on 2026-06-12
 * (Foundry Prompt Agent pathforward-orchestrator v25; evidence:
 * .agents/evidence/integrated-live-baseline-2026-06-12.md). The tour narrates
 * this run verbatim — if a value here drifts from the evidence, the tour lies.
 */

export interface TourBaseline {
  workerId: string;
  targetRoleId: string;
  skillId: string;
  citedEdgeId: string;
  orchestratorVersion: string;
  /** Gate criteria that failed on attempt 1 (exact gate criterion names). */
  attempt1FailedCriteria: readonly string[];
  cohortSize: number;
  cohortAvgReadiness: number;
  workerReadiness: number;
}

export const BASELINE_RUN: TourBaseline = {
  workerId: "EMP-001",
  targetRoleId: "R-CLOUD",
  skillId: "S01",
  citedEdgeId: "certgap::EMP-001::S01",
  orchestratorVersion: "v25",
  attempt1FailedCriteria: ["grounded", "evidence_answerable"],
  cohortSize: 11,
  cohortAvgReadiness: 0.5909,
  workerReadiness: 0.5,
};

export function makeBaseline(
  overrides: Partial<TourBaseline> = {}
): TourBaseline {
  return { ...BASELINE_RUN, ...overrides };
}
