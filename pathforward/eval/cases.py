"""Eval case set, derived from the synthetic ontology (reproducible).

EvalCase — a legitimate CertGap the agent SHOULD assess (hero workers x their gaps).
The adversarial red-team lives in `pathforward.eval.attacks` (live) and
`tests/test_redteam_gate.py` (offline defense-logic proofs).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..iq import traversal
from ..iq.models import Edge, Ontology, Skill, Worker
from ..iq.seed import _HERO_WORKERS


@dataclass(frozen=True)
class EvalCase:
    """A legitimate assessment the agent should ground and pass."""
    id: str
    worker: Worker
    edge: Edge                       # the driving CertGap edge
    skill: Skill
    approved_refs: tuple[str, ...]   # the grounding neighborhood the gate allows


def build_eval_cases(onto: Ontology, edges: list[Edge]) -> list[EvalCase]:
    """One case per (hero worker, CertGap edge) — the deterministic groundedness benchmark."""
    cases: list[EvalCase] = []
    for wid, *_ in _HERO_WORKERS:
        worker = onto.workers[wid]
        for edge in traversal.cert_gap_edges(worker, onto, edges):
            skill = onto.skills[edge.target_id]
            if not traversal.is_assessable(skill.id, onto):
                continue   # uncorpused skills are flagged 'no assessment available', not bluffed
            refs = traversal.approved_refs(worker, skill, onto)
            cases.append(EvalCase(id=f"eval::{wid}::{skill.id}", worker=worker,
                                  edge=edge, skill=skill, approved_refs=refs))
    return cases
