"""Critic agent — a real reasoning reviewer that runs BEFORE the deterministic Evidence Gate.

This is the maker-checker layer of "agents reason, code notarizes." The Critic inspects a candidate
assessment item for the quality dimensions the deterministic gate CANNOT compute — ambiguity,
fairness/bias, whether the item is answerable from its cited evidence, and citation relevance — and
returns an ADVISORY recommendation (pass / repair / reject) plus scoped concerns.

It is constructed with ONLY an `LLMClient`: it holds no reference to the Evidence Gate, to `mint`, or
to `LoopResult`, and nothing it returns is read by `verify()` or `mint()`. The gate always runs and
always decides; a Critic 'pass' on an item the gate would reject is overruled by the gate, and a
Critic 'reject' cannot block an item the gate accepts (in P1 the recommendation is purely advisory;
P2 wires `reject`/`repair` into the bounded reflection channel). The Critic never decides `grounded`,
`single_correct`, or `numeric_valid` — those are the gate's domain; it may only flag them.
"""
from __future__ import annotations

import json

from ..iq.models import Edge, Skill
from .client import CRITIC_TAG, LLMClient
from .types import AssessmentItem, CriticConcern, CriticReview

# The quality dimensions the Critic is scoped to (the gate cannot compute these).
CRITIC_DIMENSIONS = ("ambiguity", "fairness", "answerable_from_evidence", "citation_relevance")
_RECOMMENDATIONS = ("pass", "repair", "reject")

CRIT_INSTRUCTIONS = (
    f"{CRITIC_TAG} You are the Critic — a quality reviewer for a multiple-choice competency item. "
    "Judge ONLY these dimensions: ambiguity (is the stem/options unambiguous?), fairness (free of "
    "bias or culturally narrow assumptions?), answerable_from_evidence (can the correct answer be "
    "derived from the cited evidence alone?), and citation_relevance (do the cited sources actually "
    "support the item?). Do NOT decide whether the item is grounded, single-correct, or numerically "
    "valid — a deterministic gate owns those; you may flag them but never decide them. Return a "
    "`recommendation` of 'pass', 'repair', or 'reject' and a list of `concerns` (each a "
    "criterion_name + severity high|medium|low). Never use 'fail' as a recommendation value. "
    "You advise; you never issue or block a credential."
)

CRITIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "recommendation": {"type": "string", "enum": list(_RECOMMENDATIONS)},
        "concerns": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "criterion_name": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["criterion_name", "severity"],
            },
        },
        "advisory_notes": {"type": "string"},
    },
    "required": ["recommendation", "concerns", "advisory_notes"],
}


class Critic:
    def __init__(self, client: LLMClient, skill_instructions: str = ""):
        # ONLY an LLMClient — no handle to the gate, mint, Verdict, or LoopResult (trust invariant).
        self.client = client
        self.skill_instructions = skill_instructions.strip()

    def _instructions(self) -> str:
        if not self.skill_instructions:
            return CRIT_INSTRUCTIONS
        return (
            f"{CRIT_INSTRUCTIONS}\n\n"
            "Loaded Foundry Skill `/pathforward-assess`:\n"
            f"{self.skill_instructions}\n\n"
            "Follow the Critic contract in the loaded skill. You advise only; deterministic code "
            "still owns the Evidence Gate and mint boundary."
        )

    def review(self, item: AssessmentItem, allowed_ref_ids: tuple[str, ...],
               skill: Skill, edge: Edge) -> CriticReview:
        payload = {
            "skill_name": skill.name,
            "driving_edge_id": edge.id,
            "stem": item.stem,
            "options": list(item.options),
            "answer_index": item.answer_index,
            "cited_ref_ids": list(item.cited_ref_ids),
            "allowed_ref_ids": list(allowed_ref_ids),   # same grounding basis the gate uses
            "dimensions": list(CRITIC_DIMENSIONS),
        }
        resp = self.client.respond(self._instructions(), json.dumps(payload), schema=CRITIC_SCHEMA)
        d = resp.parsed or {}
        rec = d.get("recommendation", "pass")
        if rec not in _RECOMMENDATIONS:
            rec = "pass"
        concerns = tuple(
            CriticConcern(criterion_name=str(c.get("criterion_name", "")),
                          severity=str(c.get("severity", "low")))
            for c in (d.get("concerns") or []) if isinstance(c, dict)
        )
        return CriticReview(recommendation=rec, concerns=concerns,
                            advisory_notes=str(d.get("advisory_notes", "")))
