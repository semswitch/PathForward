"""Generator agent — proposes one grounded competency item for a CertGap skill."""
from __future__ import annotations

from ..iq.models import Edge, Skill
from .client import GENERATOR_TAG, LLMClient
from .types import AssessmentItem

GEN_INSTRUCTIONS = (
    f"{GENERATOR_TAG} Propose ONE multiple-choice competency item that tests the target "
    "skill. Ground every factual claim in the approved corpus and cite the supporting "
    "ref ids. If the item makes any numeric claim, include it as `numeric_claim` so it can "
    "be independently checked. Exactly one option is correct; never embed the answer in the stem."
)

# Documented schema for the real Responses agent.
ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "stem": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
        "answer_index": {"type": "integer"},
        "cited_ref_ids": {"type": "array", "items": {"type": "string"}},
        "numeric_claim": {"type": ["string", "null"]},
    },
    # strict json_schema (the live Foundry agent enforces it): every property must be listed in
    # `required` and `numeric_claim` is nullable. The Evidence Gate
    # enforces the >=2-option rule in code.
    "required": ["stem", "options", "answer_index", "cited_ref_ids", "numeric_claim"],
}


class Generator:
    def __init__(self, client: LLMClient, skill_instructions: str = ""):
        self.client = client
        self.skill_instructions = skill_instructions.strip()

    def _instructions(self) -> str:
        if not self.skill_instructions:
            return GEN_INSTRUCTIONS
        return (
            f"{GEN_INSTRUCTIONS}\n\n"
            "Loaded Foundry Skill `/pathforward-assess`:\n"
            f"{self.skill_instructions}\n\n"
            "Follow the Generator contract in the loaded skill. The Evidence Gate and structured "
            "schema remain authoritative."
        )

    def generate(self, edge: Edge, skill: Skill, allowed_ref_ids: tuple[str, ...],
                 attempt: int, previous_response_id: str | None = None,
                 feedback: dict | None = None, difficulty_band: str | None = None) -> AssessmentItem:
        import json
        payload = {
            "skill_id": skill.id,
            "skill_name": skill.name,
            "driving_edge_id": edge.id,
            "allowed_ref_ids": list(allowed_ref_ids),
            "attempt": attempt,
            # bounded reflection feedback (criterion NAMES + static remediation only — assembled by
            # the loop in code; never gate free-text/citations/answer) and the adaptive band HINT.
            "feedback": feedback,
            "difficulty_band": difficulty_band,
        }
        resp = self.client.respond(self._instructions(), json.dumps(payload),
                                   previous_response_id=previous_response_id, schema=ITEM_SCHEMA)
        d = resp.parsed or {}
        return AssessmentItem(
            id=f"item::{edge.id}::a{attempt}",
            targeted_skill_id=skill.id,
            driving_edge_id=edge.id,
            stem=d.get("stem", ""),
            options=tuple(d.get("options", ())),
            answer_index=int(d.get("answer_index", 0)),
            cited_ref_ids=tuple(d.get("cited_ref_ids", ())),
            retrieved_ref_ids=tuple(resp.retrieved_ref_ids),   # provenance from the tool trace
            numeric_claim=d.get("numeric_claim"),
            attempt=attempt,
        )
