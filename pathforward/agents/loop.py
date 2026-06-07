"""The signature: a code-driven Generator->Verifier loop.

propose -> verify -> (reject => regenerate) capped at N attempts -> fail-closed ABSTAIN.

The orchestrator owns the structured payload, so citations from the verified item
propagate deterministically into `LoopResult.citations` (the "citations-survive" test).
An unbounded loop is a reliability defect on a 20-pt track, so N is hard-capped and the
terminal state on exhaustion is an explicit abstain/escalate, never a silent pass.
"""
from __future__ import annotations

from ..iq.models import Edge, Skill
from .generator import Generator
from .types import LoopResult
from .verifier import Verifier

MAX_ATTEMPTS = 3


def run_assessment_loop(edge: Edge, skill: Skill, allowed_ref_ids: tuple[str, ...],
                        generator: Generator, verifier: Verifier,
                        max_attempts: int = MAX_ATTEMPTS) -> LoopResult:
    transcript: list[dict] = []
    previous_response_id = None
    corpus = set(allowed_ref_ids)
    for attempt in range(max_attempts):
        item = generator.generate(edge, skill, allowed_ref_ids, attempt,
                                  previous_response_id=previous_response_id)
        # Phantom-citation gate: an id counts only if it is BOTH approved corpus AND was
        # actually retrieved by the tool this turn. Under autonomous tool-calling the model
        # could cite a real corpus id it never fetched — this intersection strikes it.
        # Retrieval can only ADD to the deterministic floor, never fabricate grounding.
        effective_allowed = tuple(r for r in item.retrieved_ref_ids if r in corpus)
        verdict = verifier.verify(item, effective_allowed)
        transcript.append({"attempt": attempt, "item": item, "verdict": verdict})
        if verdict.passed:
            return LoopResult(
                status="verified", driving_edge_id=edge.id, targeted_skill_id=skill.id,
                attempts=attempt + 1, item=item, verdict=verdict, transcript=transcript,
                citations=tuple(c for c in item.cited_ref_ids if c in set(effective_allowed)),
            )
    # exhausted -> fail closed
    last = transcript[-1]
    return LoopResult(
        status="abstained", driving_edge_id=edge.id, targeted_skill_id=skill.id,
        attempts=max_attempts, item=last["item"], verdict=last["verdict"],
        transcript=transcript, citations=(),
    )
