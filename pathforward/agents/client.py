"""LLM client abstraction — shaped like the GA Responses API.

`respond(instructions, input, previous_response_id=..., schema=...)` mirrors
`openai.responses.create(...)` so the offline FakeLLMClient and the real
FoundryLLMClient are drop-in interchangeable. The orchestrator chains turns with
`previous_response_id` and owns the assembled payload.

The FakeLLMClient is deterministic: on a Generator's attempt 0 it returns a
DELIBERATELY ungrounded item (so the Verifier rejects it on camera), then on
attempt >= 1 a clean, grounded, numerically-valid item — producing the
reject -> regenerate moment the demo leads with.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

GENERATOR_TAG = "[GENERATOR]"
VERIFIER_TAG = "[VERIFIER]"


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
        # default: echo (verifier semantic rationale path, unused offline)
        return LLMResponse(rid, "", {"note": "fake-default"}, previous_response_id)

    @staticmethod
    def _generate(p: dict) -> dict:
        skill = p.get("skill_name", "the target skill")
        edge = p.get("driving_edge_id", "")
        allowed = list(p.get("allowed_ref_ids", []))
        attempt = int(p.get("attempt", 0))
        if attempt == 0:
            # ungrounded draft: cites nothing -> Verifier strikes it (the hero refusal)
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


@dataclass
class FoundryLLMClient:
    """Azure stub — wire to azure-ai-projects Responses API on Day 3.

    Build (Day 0): verify `from azure.ai.projects import AIProjectClient` and
    `PromptAgentDefinition` / `create_version` import from the pinned >=2.2.0 SDK.
    Runtime: `project.get_openai_client().responses.create(model=..., instructions=...,
    input=..., previous_response_id=...)`, with Entra `DefaultAzureCredential`.
    """
    endpoint: str = ""
    model: str = "reasoning"  # deployment name; underlying model gpt-5.5 (2026-04-24)

    def respond(self, instructions: str, input: str, *,  # pragma: no cover - Azure-only
                previous_response_id: Optional[str] = None,
                schema: Optional[dict] = None) -> LLMResponse:
        raise NotImplementedError(
            "Wire to the GA Responses API on Day 3 (see 03-Build-Plan.md §3.1 / §8)."
        )
