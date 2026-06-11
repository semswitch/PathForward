"""LLM client abstraction shaped like the GA Responses API.

`respond(instructions, input, previous_response_id=..., schema=...)` mirrors
`openai.responses.create(...)` so hosted Foundry clients can be swapped behind the
same interface. The orchestrator chains turns with `previous_response_id` and owns
the assembled payload.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

GENERATOR_TAG = "[GENERATOR]"
CRITIC_TAG = "[CRITIC]"      # the Critic AGENT (advisory quality review); the Evidence Gate is deterministic code, not an agent
CURATOR_TAG = "[CURATOR]"
PLANNER_TAG = "[PLANNER]"
INSIGHTS_TAG = "[INSIGHTS]"  # the Program Insights AGENT (read-only cohort narration over code-computed aggregates)
ORCHESTRATOR_TAG = "[ORCHESTRATOR]"  # the Orchestrator/Conductor AGENT (bounded route reasoning)


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
