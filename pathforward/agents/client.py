"""LLM client abstraction — shaped like the GA Responses API.

`respond(instructions, input, previous_response_id=..., schema=...)` mirrors
`openai.responses.create(...)` so the offline FakeLLMClient and the real
FoundryLLMClient are drop-in interchangeable. The orchestrator chains turns with
`previous_response_id` and owns the assembled payload.

The FakeLLMClient is deterministic: on a Generator's attempt 0 it returns a
DELIBERATELY ungrounded item (so the Evidence Gate rejects it on camera), then on
attempt >= 1 a clean, grounded, numerically-valid item — producing the
reject -> regenerate moment the demo leads with.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

GENERATOR_TAG = "[GENERATOR]"
CRITIC_TAG = "[CRITIC]"      # the Critic AGENT (advisory quality review); the Evidence Gate is deterministic code, not an agent
CURATOR_TAG = "[CURATOR]"
PLANNER_TAG = "[PLANNER]"


@dataclass
class LLMResponse:
    id: str
    output_text: str
    parsed: Optional[dict] = None
    previous_response_id: Optional[str] = None
    retrieved_ref_ids: tuple[str, ...] = ()   # ids the retrieval tool returned this turn (from the tool trace)


@runtime_checkable
class LLMClient(Protocol):
    def respond(self, instructions: str, input: str, *,
                previous_response_id: Optional[str] = None,
                schema: Optional[dict] = None) -> LLMResponse: ...


@dataclass
class FakeLLMClient:
    """Deterministic stand-in. Counts calls only to mint stable response ids."""
    _n: int = field(default=0)

    def respond(self, instructions: str, input: str, *,
                previous_response_id: Optional[str] = None,
                schema: Optional[dict] = None) -> LLMResponse:
        self._n += 1
        rid = f"resp_fake_{self._n:04d}"
        if GENERATOR_TAG in instructions:
            p = json.loads(input)
            parsed = self._generate(p)
            # retrieved_ref_ids simulates the TOOL TRACE (what retrieval physically returned),
            # not model output: attempt 0 grounds on nothing (the on-camera refusal); later
            # attempts retrieve the approved doc the revision then cites.
            allowed = list(p.get("allowed_ref_ids", []))
            attempt = int(p.get("attempt", 0))
            retrieved = () if attempt == 0 else tuple(allowed[:1])
            return LLMResponse(rid, json.dumps(parsed), parsed, previous_response_id,
                               retrieved_ref_ids=retrieved)
        if CURATOR_TAG in instructions:
            parsed = self._curate(json.loads(input))
            return LLMResponse(rid, json.dumps(parsed), parsed, previous_response_id)
        if PLANNER_TAG in instructions:
            parsed = self._plan(json.loads(input))
            return LLMResponse(rid, json.dumps(parsed), parsed, previous_response_id)
        # default: echo (advisory-rationale path for unrecognized tags, unused offline)
        return LLMResponse(rid, "", {"note": "fake-default"}, previous_response_id)

    @staticmethod
    def _generate(p: dict) -> dict:
        skill = p.get("skill_name", "the target skill")
        edge = p.get("driving_edge_id", "")
        allowed = list(p.get("allowed_ref_ids", []))
        attempt = int(p.get("attempt", 0))
        if attempt == 0:
            # ungrounded draft: cites nothing -> Evidence Gate strikes it (the hero refusal)
            return {
                "stem": f"Which approach best demonstrates competency in {skill}?",
                "options": [f"A plausible-sounding answer about {skill}",
                            "An unrelated distractor", "Another distractor"],
                "answer_index": 0,
                "cited_ref_ids": [],
                "numeric_claim": None,
            }
        # grounded, verifiable revision
        return {
            "stem": (f"A learner studied for {skill}. Given a recommended 24 study hours "
                     f"split as 18 hours of practice and 6 hours of review, what is the total?"),
            "options": ["20 hours", "24 hours", "30 hours"],
            "answer_index": 1,
            "cited_ref_ids": allowed[:1] or [edge],
            "numeric_claim": "18 + 6 == 24",
        }

    @staticmethod
    def _curate(p: dict) -> dict:
        """Deterministic Curator stand-in with a built-in over-reach beat: rank a skill the worker
        ALREADY HOLDS first (inadmissible) so the Curator's gate visibly strikes it (corrected),
        then the admissible candidates in role order -> the chosen target is candidates[0]."""
        candidates = list(p.get("candidate_skill_ids", []))
        has = list(p.get("has_skill_ids", []))
        head = has[0] if has else "S99"   # a held skill is by definition not a gap -> inadmissible
        ranking = [head] + candidates
        rationale = {head: "(over-reach) suggested a skill the worker already holds"}
        for s in candidates:
            rationale[s] = f"gap skill {s}: prioritized by adjacency and certification coverage"
        return {"ranking": ranking, "rationale": rationale}

    @staticmethod
    def _plan(p: dict) -> dict:
        """Deterministic Planner stand-in with two built-in beats the gate must catch: an
        OVER-CAPACITY weekly pace (3x the worker's capacity -> clamped + flagged corrected) and an
        OUT-OF-VOCABULARY accessibility suggestion (dropped by the vocabulary gate)."""
        capacity = float(p.get("weekly_capacity_hours", 0) or 0)
        gap = [g.get("id") for g in p.get("gap_skills", [])]
        return {
            "sequence": gap,
            "weekly_hours": capacity * 3 if capacity else 99,   # unrealistic -> gate clamps it
            "accessibility_adaptations": ["unlimited tutor hours", "high-contrast materials"],
            "rationale": "Front-load the highest-priority gap, then proceed in adjacency order.",
        }
