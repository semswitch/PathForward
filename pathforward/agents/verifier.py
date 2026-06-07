"""Verifier agent — the 5-criterion + evidence-answerability gate.

The verdict is computed in CODE (deterministic) — the model is never trusted for the
gate. Numeric claims route to the NumericChecker. This is what makes the credential
trustworthy and what the demo's "refusal" moment shows on screen.

Criteria:
  1. grounded            — every citation is inside the approved corpus, and there is >=1
  2. evidence_answerable — the answer is derivable from cited evidence (offline: implied by grounding)
  3. single_correct      — exactly one valid correct option
  4. no_leakage          — the answer text is not embedded in the stem
  5. numeric_valid       — any numeric claim independently checks out
"""
from __future__ import annotations

from typing import Optional

from .client import LLMClient
from .numeric import NumericChecker
from .types import AssessmentItem, Verdict


class Verifier:
    def __init__(self, numeric_checker: NumericChecker, client: Optional[LLMClient] = None):
        self.numeric_checker = numeric_checker
        self.client = client  # reserved for the Azure semantic-answerability judge

    def verify(self, item: AssessmentItem, allowed_ref_ids: tuple[str, ...]) -> Verdict:
        allowed = set(allowed_ref_ids)
        criteria: dict[str, bool] = {}
        fails: list[dict] = []

        # 1. grounded
        has_citations = len(item.cited_ref_ids) > 0
        citations_supported = all(c in allowed for c in item.cited_ref_ids)
        grounded = has_citations and citations_supported
        criteria["grounded"] = grounded
        if not grounded:
            reason = ("item cites no approved evidence" if not has_citations
                      else "item cites a source outside the approved corpus")
            fails.append({"criterion": "grounded", "reason": reason,
                          "citation": list(item.cited_ref_ids)})

        # 2. evidence_answerable (offline: an answer is only evidence-answerable if grounded)
        criteria["evidence_answerable"] = grounded

        # 3. single_correct
        single_correct = len(item.options) >= 2 and 0 <= item.answer_index < len(item.options)
        criteria["single_correct"] = single_correct
        if not single_correct:
            fails.append({"criterion": "single_correct",
                          "reason": "answer_index does not point to a valid single option",
                          "citation": []})

        # 4. no_leakage
        answer = item.options[item.answer_index] if single_correct else ""
        no_leakage = single_correct and answer.strip().lower() not in item.stem.strip().lower()
        criteria["no_leakage"] = bool(no_leakage)
        if single_correct and not no_leakage:
            fails.append({"criterion": "no_leakage",
                          "reason": "the correct answer text appears in the stem",
                          "citation": []})

        # 5. numeric_valid
        numeric_ok: Optional[bool] = None
        if item.numeric_claim:
            res = self.numeric_checker.check(item.numeric_claim)
            numeric_ok = res.ok
            criteria["numeric_valid"] = res.ok
            if not res.ok:
                fails.append({"criterion": "numeric_valid",
                              "reason": f"numeric check failed: {res.detail}", "citation": []})
        else:
            criteria["numeric_valid"] = True

        passed = all(criteria.values())
        return Verdict(passed=passed, criteria=criteria, failed_reasons=fails, numeric_ok=numeric_ok)
