"""Evidence Gate — the deterministic 5-criterion notary (this is NOT an agent).

This is the trust boundary: "agents reason, code notarizes." The verdict is computed
entirely in CODE — no model call is ever made here, so an LLM can never judge its own
grounding. A real Critic AGENT (`critic.py`) does the *advisory* reasoning (ambiguity /
fairness / answerability) BEFORE this gate; only the gate decides whether an item may pass,
and only a passing verdict sets `status="verified"` (in `loop.py`, one place). Numeric
claims route to the NumericChecker (code). This is what makes the credential trustworthy and
what the demo's "refusal" moment shows on screen.

Criteria:
  1. grounded            — every citation is inside the approved corpus, and there is >=1
  2. evidence_answerable — derivable from cited evidence (currently implied by grounding; an
                           optional NON-GATING semantic hook is reserved — see __init__)
  3. single_correct      — exactly one valid correct option (bounds + no multi-correct/duplicate smell)
  4. no_leakage          — the answer text is not embedded in the stem (unicode/homoglyph-robust)
  5. numeric_valid       — any numeric claim independently checks out AND is tied to the item; an
                           item that asserts arithmetic must register it as a checkable claim

Hardened against the red-team taxonomy (see .agents/decisions/004): homoglyph/zero-width leakage
evasion, false-numeric-with-null-claim, tautological numeric claims, and multi-correct collapse.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from .client import LLMClient
from .numeric import NumericChecker
from .types import AssessmentItem, Verdict

# Common Cyrillic/Greek homoglyphs folded to their Latin look-alikes before the leakage check.
_CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "і": "i", "ј": "j",
    "ѕ": "s", "к": "k", "м": "m", "н": "h", "т": "t", "в": "b", "А": "a", "Е": "e", "О": "o",
    "Р": "p", "С": "c", "Х": "x", "ο": "o", "α": "a", "ε": "e", "ρ": "p", "ι": "i", "ν": "v",
})
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)
# Two numbers joined by an arithmetic operator => the item is making an arithmetic assertion.
_ARITH = re.compile(r"\d+(?:\.\d+)?\s*[-+*/x×]\s*\d+(?:\.\d+)?")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_MULTI_CORRECT = re.compile(r"\b(all|any|none|both)\b.*\babove\b", re.IGNORECASE)


def _normalize_leakage(s: str) -> str:
    """NFKC + confusable-fold + drop zero-width + lowercase + keep alphanumerics only."""
    s = unicodedata.normalize("NFKC", s).translate(_ZERO_WIDTH).translate(_CONFUSABLES).lower()
    return "".join(ch for ch in s if ch.isalnum())


def _numbers(s: str) -> set[str]:
    return set(_NUM.findall(s or ""))


class EvidenceGate:
    """Deterministic notary. `verify()` returns a Verdict computed only from code + the
    NumericChecker; it never calls a model. The Critic agent's recommendation is NOT an input
    here — the gate is the sole authority over whether an item passes."""

    def __init__(self, numeric_checker: NumericChecker, semantic_hook: Optional[LLMClient] = None):
        # Fail at CONSTRUCTION if the oracle isn't a NumericChecker — so the "the gate's oracle is
        # code" guarantee is structural, not merely fail-on-first-numeric-claim. In particular this
        # rejects a non-gating Analyst (agents/analyst.py): it has no `check()` and would otherwise be
        # silently accepted here and never error on an item that carries no numeric_claim.
        if not isinstance(numeric_checker, NumericChecker):
            raise TypeError("EvidenceGate requires a NumericChecker (code oracle); got "
                            f"{type(numeric_checker).__name__}. The gate's numeric oracle must be "
                            "deterministic code — never a model-backed analyst.")
        self.numeric_checker = numeric_checker
        # NON-GATING, reserved hook for a future semantic-answerability judge. The gate's verdict
        # does NOT read this — it exists only to preserve the seam (deleting it would silently
        # hard-code evidence_answerable == grounded). Any semantic check must remain advisory.
        self.semantic_hook = semantic_hook

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

        # 3. single_correct — bounds, plus reject multi-correct ("all/any of the above") and duplicates
        in_bounds = len(item.options) >= 2 and 0 <= item.answer_index < len(item.options)
        norm_opts = [o.strip().lower() for o in item.options]
        has_dupe = len(set(norm_opts)) != len(norm_opts)
        multi_correct = any(_MULTI_CORRECT.search(o) for o in item.options)
        single_correct = in_bounds and not has_dupe and not multi_correct
        criteria["single_correct"] = single_correct
        if not single_correct:
            reason = ("answer_index does not point to a valid single option" if not in_bounds
                      else "duplicate options" if has_dupe
                      else "an option makes multiple answers correct ('... of the above')")
            fails.append({"criterion": "single_correct", "reason": reason, "citation": []})

        # 4. no_leakage — homoglyph/zero-width-robust: the answer must not be embedded in the stem
        answer = item.options[item.answer_index] if in_bounds else ""
        norm_answer, norm_stem = _normalize_leakage(answer), _normalize_leakage(item.stem)
        leaked = len(norm_answer) >= 4 and norm_answer in norm_stem
        no_leakage = in_bounds and not leaked
        criteria["no_leakage"] = bool(no_leakage)
        if in_bounds and leaked:
            fails.append({"criterion": "no_leakage",
                          "reason": "the correct answer text appears in the stem (after normalization)",
                          "citation": []})

        # 5. numeric_valid — a claim must check out AND tie to the item; an item that asserts
        #    arithmetic must register a claim (no laundering a false total as 'non-numeric').
        criteria["numeric_valid"] = True
        numeric_ok: Optional[bool] = None
        item_text = f"{item.stem} {answer}"
        if item.numeric_claim:
            res = self.numeric_checker.check(item.numeric_claim)
            numeric_ok = res.ok
            sides = [s.strip() for s in re.split(r"==|!=|<=|>=|[<>=]", item.numeric_claim) if s.strip()]
            tautology = len(sides) >= 2 and len(set(sides)) == 1            # e.g. '80 == 80'
            claim_nums = _numbers(item.numeric_claim)
            tied = bool(claim_nums & _numbers(item_text))                  # claim references the item's numbers
            if not res.ok:
                criteria["numeric_valid"] = False
                fails.append({"criterion": "numeric_valid",
                              "reason": f"numeric check failed: {res.detail}", "citation": []})
            elif tautology or not tied:
                criteria["numeric_valid"] = False
                numeric_ok = False
                fails.append({"criterion": "numeric_valid",
                              "reason": ("numeric_claim is a tautology" if tautology
                                         else "numeric_claim is not tied to the item's asserted values"),
                              "citation": []})
        elif _ARITH.search(item_text):
            # arithmetic asserted but no checkable claim registered -> strike (false-numeric laundering)
            criteria["numeric_valid"] = False
            numeric_ok = False
            fails.append({"criterion": "numeric_valid",
                          "reason": "item asserts arithmetic but registers no numeric_claim to check",
                          "citation": []})

        passed = all(criteria.values())
        return Verdict(passed=passed, criteria=criteria, failed_reasons=fails, numeric_ok=numeric_ok)
