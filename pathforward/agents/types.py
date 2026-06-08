"""Shared dataclasses for the assessment loop."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AssessmentItem:
    id: str
    targeted_skill_id: str
    driving_edge_id: str            # the CertGap edge that selected this skill (causal spine)
    stem: str
    options: tuple[str, ...]
    answer_index: int
    cited_ref_ids: tuple[str, ...] = ()
    retrieved_ref_ids: tuple[str, ...] = ()   # ids the retrieval TOOL physically returned (trace, not model output)
    numeric_claim: Optional[str] = None   # arithmetic the Evidence Gate must independently check
    attempt: int = 0

    @property
    def correct_option(self) -> str:
        if 0 <= self.answer_index < len(self.options):
            return self.options[self.answer_index]
        return ""

    def to_doc(self) -> dict:
        return {
            "id": self.id,
            "targeted_skill_id": self.targeted_skill_id,
            "driving_edge_id": self.driving_edge_id,
            "stem": self.stem,
            "options": list(self.options),
            "answer_index": self.answer_index,
            "cited_ref_ids": list(self.cited_ref_ids),
            "retrieved_ref_ids": list(self.retrieved_ref_ids),
            "numeric_claim": self.numeric_claim,
            "attempt": self.attempt,
        }


@dataclass
class Verdict:
    passed: bool
    criteria: dict                  # criterion name -> bool
    failed_reasons: list = field(default_factory=list)   # [{criterion, reason, citation}]
    numeric_ok: Optional[bool] = None

    def to_doc(self) -> dict:
        return {
            "passed": self.passed,
            "criteria": self.criteria,
            "failed_reasons": self.failed_reasons,
            "numeric_ok": self.numeric_ok,
        }


@dataclass
class CriticConcern:
    criterion_name: str          # ambiguity | fairness | answerable_from_evidence | citation_relevance
    severity: str                # high | medium | low

    def to_doc(self) -> dict:
        return {"criterion_name": self.criterion_name, "severity": self.severity}


@dataclass
class CriticReview:
    """Advisory output of the Critic AGENT — it RECOMMENDS, it does not decide. Nothing here is read
    by the Evidence Gate's `verify()` or by `mint()`; the gate is the sole authority. The Critic is
    scoped to quality dimensions the deterministic gate cannot compute (ambiguity / fairness /
    answerable-from-evidence / citation-relevance)."""
    recommendation: str          # 'pass' | 'repair' | 'reject'
    concerns: tuple = ()         # tuple[CriticConcern, ...]
    advisory_notes: str = ""     # trace/display only; never fed back to the Generator verbatim

    def to_doc(self) -> dict:
        return {
            "recommendation": self.recommendation,
            "concerns": [c.to_doc() for c in self.concerns],
            "advisory_notes": self.advisory_notes,
        }


@dataclass
class LoopResult:
    status: str                     # 'verified' | 'abstained' (fail-closed)
    driving_edge_id: str
    targeted_skill_id: str
    attempts: int
    item: Optional[AssessmentItem]
    verdict: Optional[Verdict]
    transcript: list                # [{attempt, item, critic, verdict}] (critic may be None)
    citations: tuple[str, ...]      # assembled & OWNED by the orchestrator (citations-survive)

    def to_doc(self) -> dict:
        return {
            "status": self.status,
            "driving_edge_id": self.driving_edge_id,
            "targeted_skill_id": self.targeted_skill_id,
            "attempts": self.attempts,
            "item": self.item.to_doc() if self.item else None,
            "verdict": self.verdict.to_doc() if self.verdict else None,
            "transcript": [
                {"attempt": t["attempt"], "item": t["item"].to_doc(),
                 "critic": t["critic"].to_doc() if t.get("critic") else None,
                 "verdict": t["verdict"].to_doc()}
                for t in self.transcript
            ],
            "citations": list(self.citations),
        }


@dataclass
class CuratorDecision:
    """The Curator's gap-prioritization result.

    The LLM RANKS; deterministic code OWNS which gaps are admissible and which one is chosen.
    `admissible_skill_ids` is computed from the derivation (the sole source of truth); `ranking`
    is the LLM order AFTER gate-filtering to that set; `rationale` is display-only (never trusted,
    never gates anything). `corrected` is True when the LLM's raw first pick was inadmissible.
    """
    worker_id: str
    role_id: str
    admissible_skill_ids: tuple[str, ...]   # deterministic: assessable CertGap skills, role order
    ranking: tuple[str, ...]                 # LLM rank, filtered to admissible
    chosen_skill_id: str                     # "" when there is no assessable gap (fail-closed)
    chosen_edge_id: str                      # certgap::<worker>::<chosen_skill>  ("" when none)
    rationale: dict = field(default_factory=dict)   # skill_id -> str (display-only, untrusted)
    corrected: bool = False

    def to_doc(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "role_id": self.role_id,
            "admissible_skill_ids": list(self.admissible_skill_ids),
            "ranking": list(self.ranking),
            "chosen_skill_id": self.chosen_skill_id,
            "chosen_edge_id": self.chosen_edge_id,
            "rationale": dict(self.rationale),
            "corrected": self.corrected,
        }


@dataclass
class PlannedPhase:
    week: int
    skill_id: str
    hours: float        # DERIVED from the certification (code-owned), never LLM-supplied
    cert_id: str        # the canonical (cheapest) cert sourced for this skill

    def to_doc(self) -> dict:
        return {"week": self.week, "skill_id": self.skill_id, "hours": self.hours,
                "cert_id": self.cert_id}


@dataclass
class LearningPlan:
    """The Planner's capacity- and accessibility-aware learning plan (advisory, NOT in the
    credential trust chain). Hours are derived, the weekly load is code-phased to respect the
    worker's capacity, and adaptations come from a fixed accessibility vocabulary."""
    worker_id: str
    phases: tuple[PlannedPhase, ...]
    total_hours: float
    weekly_capacity_hours: float
    weeks: int
    capacity_respected: bool
    corrected: bool                          # True if the LLM schedule exceeded capacity -> recomputed
    accessibility_adaptations: tuple[str, ...]
    numeric_check: dict = field(default_factory=dict)   # {claim, ok, detail}
    rationale: str = ""                      # display-only

    def to_doc(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "phases": [p.to_doc() for p in self.phases],
            "total_hours": self.total_hours,
            "weekly_capacity_hours": self.weekly_capacity_hours,
            "weeks": self.weeks,
            "capacity_respected": self.capacity_respected,
            "corrected": self.corrected,
            "accessibility_adaptations": list(self.accessibility_adaptations),
            "numeric_check": dict(self.numeric_check),
            "rationale": self.rationale,
        }


@dataclass
class ProgramInsights:
    """Advisory output of the Program Insights AGENT — READ-ONLY and OFF the credential trust path.

    The trust-bearing FACTS (cohort readiness, this worker's standing, the program's skill
    bottlenecks) are computed in code by `iq/cohort.py` from `derivation.py` and copied here
    verbatim — the agent CANNOT change them. The agent contributes only `narrative` (display-only
    prose: cohort framing, "why this path"). Nothing here is read by the Evidence Gate's `verify()`
    or by `mint()`. `source` records which tier produced the data: 'derivation-floor' (in-process,
    always green) or 'fabric-live' (governed OneLake via MicrosoftFabricPreviewTool / OBO, on paid
    F2+/P1+ capacity)."""
    worker_id: str
    role_id: str
    role_cohort: dict                # cohort.RoleCohort.to_doc() — code-computed, not model output
    worker_comparison: dict          # cohort.WorkerCohortComparison.to_doc() — code-computed
    program: dict                    # cohort.ProgramAggregates.to_doc() — code-computed
    narrative: str = ""              # display-only model prose; never trusted, never gates
    source: str = "derivation-floor"

    def to_doc(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "role_id": self.role_id,
            "role_cohort": dict(self.role_cohort),
            "worker_comparison": dict(self.worker_comparison),
            "program": dict(self.program),
            "narrative": self.narrative,
            "source": self.source,
        }


@dataclass
class MultiAgentResult:
    """The combined output of the multi-agent reasoning loop: Curator -> (Generator/Critic/Evidence
    Gate loop) -> Planner -> Program Insights. The loop and the credential trust chain are
    unchanged; the Curator selects the assessment target, the Planner produces an advisory plan, and
    the Program Insights agent adds read-only cohort/program reasoning. `insights` is None when no
    Insights agent is wired (the loop and mint never depend on it)."""
    curator: CuratorDecision
    loop: LoopResult
    plan: LearningPlan
    insights: Optional[ProgramInsights] = None

    def to_doc(self) -> dict:
        return {
            "curator": self.curator.to_doc(),
            "loop": self.loop.to_doc(),
            "plan": self.plan.to_doc(),
            "insights": self.insights.to_doc() if self.insights else None,
        }
