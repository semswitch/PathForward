"""Curator agent — reasons over the worker's certification gaps and picks the assessment target.

The LLM RANKS the gap skills (reasoning over adjacency to skills the worker already has, domain
proximity, and certification coverage). Deterministic code OWNS the trust-bearing facts: the
candidate set is the derivation's *assessable* CertGap skills (the model cannot invent a gap, nor
pick one with no learning content), and the chosen skill MUST be a member — otherwise the gate
falls back to the top admissible gap in role order. This mirrors the Generator->Evidence Gate shape:
reasoning proposes, code gates.
"""
from __future__ import annotations

import json

from ..iq import derivation as dv
from ..iq import traversal
from ..iq.models import Ontology, Role, Worker
from .client import CURATOR_TAG, LLMClient
from .types import CuratorDecision

CUR_INSTRUCTIONS = (
    f"{CURATOR_TAG} You are the Curator. Rank the worker's certification-gap skills by reskilling "
    "priority, reasoning over adjacency to skills the worker already has, domain proximity, and "
    "certification coverage. Return `ranking` (skill_ids, highest priority first) and a one-line "
    "`rationale` per skill. You MAY ONLY rank skills from the provided candidate_skill_ids."
)

# Documented strict schema for live reasoning agents.
CURATOR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "ranking": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "object", "additionalProperties": {"type": "string"}},
    },
    "required": ["ranking", "rationale"],
}


class Curator:
    def __init__(self, client: LLMClient, skill_instructions: str = ""):
        self.client = client
        self.skill_instructions = skill_instructions.strip()

    def _instructions(self) -> str:
        if not self.skill_instructions:
            return CUR_INSTRUCTIONS
        return f"{CUR_INSTRUCTIONS}\n\n{self.skill_instructions}"

    def curate(self, worker: Worker, role: Role, onto: Ontology) -> CuratorDecision:
        # Deterministic source of truth: the assessable CertGap skills, in the role's required
        # order. `cert_gap_skill_ids` is the ONLY place gaps are derived; `is_assessable` drops
        # skills with no certification corpus (nothing to author/answer an item from).
        admissible = tuple(s for s in dv.cert_gap_skill_ids(worker, role)
                           if traversal.is_assessable(s, onto))
        if not admissible:
            # No assessable gap -> nothing to certify. Fail-closed: the orchestrator will not mint.
            return CuratorDecision(
                worker_id=worker.id, role_id=role.id, admissible_skill_ids=(),
                ranking=(), chosen_skill_id="", chosen_edge_id="", rationale={}, corrected=False,
            )

        payload = {
            "worker_id": worker.id,
            "target_role": role.name,
            "has_skill_ids": list(worker.has_skill_ids),
            "candidate_skill_ids": list(admissible),
            "candidates": [
                {"id": s, "name": onto.skills[s].name, "domain": onto.skills[s].domain,
                 "certs": [c.id for c in onto.certs_for_skill(s)]}
                for s in admissible
            ],
        }
        resp = self.client.respond(self._instructions(), json.dumps(payload), schema=CURATOR_SCHEMA)
        parsed = resp.parsed or {}
        raw_ranking = list(parsed.get("ranking", []))
        admissible_set = set(admissible)
        rationale = {k: v for k, v in (parsed.get("rationale", {}) or {}).items()
                     if k in admissible_set}

        # GATE: keep only ids in the deterministic admissible set — the model cannot introduce a
        # non-gap, an already-held, or an uncorpused skill. De-dup, preserve order, then append any
        # admissible skill the model omitted (in role order) so the ranking is complete.
        seen: set[str] = set()
        ranking: list[str] = []
        for s in (*raw_ranking, *admissible):
            if s in admissible_set and s not in seen:
                seen.add(s)
                ranking.append(s)

        chosen = ranking[0]                                  # admissible is non-empty -> safe
        # corrected iff the model's RAW first pick was not admissible (it over-reached / was empty).
        raw_first = raw_ranking[0] if raw_ranking else None
        corrected = raw_first not in admissible_set

        return CuratorDecision(
            worker_id=worker.id, role_id=role.id, admissible_skill_ids=admissible,
            ranking=tuple(ranking), chosen_skill_id=chosen,
            chosen_edge_id=dv.certgap_edge_id(worker.id, chosen),
            rationale=rationale, corrected=corrected,
        )
