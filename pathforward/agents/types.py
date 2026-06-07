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
    numeric_claim: Optional[str] = None   # arithmetic the Verifier must independently check
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
