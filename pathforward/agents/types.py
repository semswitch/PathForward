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
class LoopResult:
    status: str                     # 'verified' | 'abstained' (fail-closed)
    driving_edge_id: str
    targeted_skill_id: str
    attempts: int
    item: Optional[AssessmentItem]
    verdict: Optional[Verdict]
    transcript: list                # [{attempt, item, verdict}]
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
                {"attempt": t["attempt"], "item": t["item"].to_doc(), "verdict": t["verdict"].to_doc()}
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
class MultiAgentResult:
    """The combined output of the three-agent reasoning loop: Curator -> (Generator/Evidence Gate
    loop) -> Planner. The loop and the credential trust chain are unchanged; the Curator selects
    the assessment target and the Planner produces an advisory plan around it."""
    curator: CuratorDecision
    loop: LoopResult
    plan: LearningPlan

    def to_doc(self) -> dict:
        return {
            "curator": self.curator.to_doc(),
            "loop": self.loop.to_doc(),
            "plan": self.plan.to_doc(),
        }
