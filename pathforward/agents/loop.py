"""The signature: a code-driven Generator->Evidence Gate loop.

propose -> verify -> (reject => regenerate) capped at N attempts -> fail-closed ABSTAIN.

The orchestrator owns the structured payload, so citations from the verified item
propagate deterministically into `LoopResult.citations` (the "citations-survive" test).
An unbounded loop is a reliability defect on a 20-pt track, so N is hard-capped and the
terminal state on exhaustion is an explicit abstain/escalate, never a silent pass.

Each step is wrapped in an OpenTelemetry span (no-op unless tracing is configured) so the
reason/grounding/refusal decisions are observable as a trace — the glass box, timed.
"""
from __future__ import annotations

from ..iq.models import Edge, Skill
from ..obs import tracing
from .adaptive import AdaptiveController
from .critic import Critic
from .generator import Generator
from .types import CriticReview, LoopResult, Verdict
from .evidence_gate import EvidenceGate

MAX_ATTEMPTS = 3

# Fixed, CODE-OWNED remediation strings — the only guidance the reflection channel ever feeds back
# to the Generator, keyed by failed-criterion NAME. This deliberately excludes the gate's free-text
# `failed_reasons`, any citation/ref_id, and the answer/option text (anti-leak / no gate-teaching).
REMEDIATION_BY_CRITERION = {
    # Evidence Gate criteria
    "grounded": "retrieve and cite approved evidence before composing the item",
    "evidence_answerable": "ensure the answer is derivable from the cited evidence",
    "single_correct": "ensure exactly one option is correct; avoid duplicates or 'all/any of the above'",
    "no_leakage": "do not place the correct answer text in the stem",
    "numeric_valid": "register any arithmetic as a checkable numeric_claim tied to the item's numbers",
    # Critic dimensions
    "ambiguity": "make the stem and options unambiguous",
    "fairness": "remove biased or culturally narrow assumptions",
    "answerable_from_evidence": "ensure the item is answerable from the cited evidence alone",
    "citation_relevance": "cite sources that directly support the item",
}


def _build_feedback(verdict: Verdict, review: CriticReview | None,
                    difficulty_band: str | None) -> dict:
    """Assemble BOUNDED reflection feedback in CODE: failed-criterion NAMES + a fixed remediation
    string per criterion + the difficulty band. It reads `verdict.criteria` (the boolean map) and the
    Critic's concern NAMES only — never `verdict.failed_reasons`, citations, or answer/option text."""
    names: list[str] = [name for name, ok in (verdict.criteria or {}).items() if not ok]
    if review is not None and review.recommendation in ("reject", "repair"):
        names += [c.criterion_name for c in review.concerns]
    seen: list[str] = []
    for n in names:
        if n in REMEDIATION_BY_CRITERION and n not in seen:
            seen.append(n)
    return {
        "failed_criteria": seen,
        "remediation": [REMEDIATION_BY_CRITERION[n] for n in seen],
        "difficulty_band": difficulty_band,
    }


def run_assessment_loop(edge: Edge, skill: Skill, allowed_ref_ids: tuple[str, ...],
                        generator: Generator, evidence_gate: EvidenceGate,
                        max_attempts: int = MAX_ATTEMPTS,
                        critic: Critic | None = None,
                        adaptive: AdaptiveController | None = None) -> LoopResult:
    transcript: list[dict] = []
    previous_response_id = None
    feedback: dict | None = None        # bounded reflection feedback for the next attempt
    corpus = set(allowed_ref_ids)
    # Adaptive difficulty (pure code, selection-only): pick the band from cold-start calibration.
    band = adaptive.band_for(skill.id) if adaptive is not None else None
    with tracing.span("assessment.loop", **{"pf.worker": edge.source_id, "pf.skill": skill.id,
                                            "pf.driving_edge": edge.id, "pf.corpus_size": len(corpus),
                                            "pf.difficulty_band": band or "(none)"}) as root:
        if adaptive is not None:
            root.event("adaptive.band_selected", **{"pf.band": band or "core"})
        for attempt in range(max_attempts):
            # Reflection is STATELESS: on a regenerate (feedback present) drop previous_response_id so
            # the model gets the bounded feedback, never its own prior answer-bearing draft.
            gen_prev = None if feedback is not None else previous_response_id
            with tracing.span(f"generate.attempt.{attempt}",
                              **{"pf.attempt": attempt, "pf.has_feedback": feedback is not None,
                                 "pf.band": band or "(none)"}) as gen_span:
                if feedback is not None:
                    gen_span.event("reflection.applied", **{
                        "pf.failed_criteria_count": len(feedback.get("failed_criteria", ())),
                        "pf.feedback_source": "code_owned_static",
                    })
                item = generator.generate(edge, skill, allowed_ref_ids, attempt,
                                          previous_response_id=gen_prev,
                                          feedback=feedback, difficulty_band=band)
                gen_span.set(**{"pf.retrieved": len(item.retrieved_ref_ids),
                                "pf.cited": len(item.cited_ref_ids),
                                "pf.content_filtered": item.stem == "[CONTENT_FILTERED]"})
            # Phantom-citation gate: an id counts only if it is BOTH approved corpus AND was
            # actually retrieved by the tool this turn. Under autonomous tool-calling the model
            # could cite a real corpus id it never fetched — this intersection strikes it.
            # Retrieval can only ADD to the deterministic floor, never fabricate grounding.
            effective_allowed = tuple(r for r in item.retrieved_ref_ids if r in corpus)
            # Critic AGENT (advisory): reasons over quality dimensions the gate cannot compute, on
            # the SAME grounding basis (effective_allowed). It only RECOMMENDS — the gate decides.
            review = None
            if critic is not None:
                with tracing.span(f"critic.attempt.{attempt}") as crit_span:
                    review = critic.review(item, effective_allowed, skill, edge)
                    crit_span.set(**{"pf.critic_recommendation": review.recommendation,
                                     "pf.critic_concerns": len(review.concerns)})
            with tracing.span(f"verify.attempt.{attempt}",
                              **{"pf.effective_allowed": len(effective_allowed)}) as ver_span:
                verdict = evidence_gate.verify(item, effective_allowed)
                ver_span.set(**{"pf.passed": verdict.passed})
                if not verdict.passed:
                    ver_span.event("gate.struck", **{
                        "pf.failed": ",".join(f["criterion"] for f in verdict.failed_reasons)})
            transcript.append({"attempt": attempt, "item": item, "critic": review, "verdict": verdict})
            if verdict.passed:
                root.set(**{"pf.status": "verified", "pf.attempts": attempt + 1})
                return LoopResult(
                    status="verified", driving_edge_id=edge.id, targeted_skill_id=skill.id,
                    attempts=attempt + 1, item=item, verdict=verdict, transcript=transcript,
                    citations=tuple(c for c in item.cited_ref_ids if c in set(effective_allowed)),
                )
            # rejected -> assemble bounded, code-owned feedback for the next attempt (criterion
            # NAMES + static remediation only; the regenerate above will run statelessly).
            feedback = _build_feedback(verdict, review, band)
            root.event("reflection.prepared", **{
                "pf.failed_criteria_count": len(feedback.get("failed_criteria", ())),
                "pf.feedback_source": "code_owned_static",
                "pf.next_attempt": attempt + 1,
            })
        # exhausted -> fail closed
        root.set(**{"pf.status": "abstained", "pf.attempts": max_attempts})
        root.event("abstained.fail_closed")
        last = transcript[-1]
        return LoopResult(
            status="abstained", driving_edge_id=edge.id, targeted_skill_id=skill.id,
            attempts=max_attempts, item=last["item"], verdict=last["verdict"],
            transcript=transcript, citations=(),
        )
