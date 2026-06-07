"""The single, version-pinned derivation module.

CertGap and Readiness are computed HERE and nowhere else. Both the Fabric
ontology load and the Search-mirror build consume these functions, so the live
path and the fallback path can never disagree on a derived value.

  CertGap(worker, role)  = Role.requires.Skill  \\  Worker.has.Skill   (role order preserved)
  Readiness(worker, role) = |has ∩ required| / |required|             (0..1)

Edge IDs are deterministic strings so the same edge has the same ID across the
live ontology, the mirror, and the credential that cites it (the demo's causal
spine depends on this stable identity).
"""
from __future__ import annotations

from .models import Edge, Ontology, Role, Worker, SOURCE_LIVE

DERIVATION_VERSION = "1.0.0"
ONTOLOGY_AS_OF = "2026-06-01"  # fixed validity-time; never use wall-clock (keeps derivation deterministic)

CERTGAP_RULE = "CertGap(worker, role) = Role.requires.Skill \\ Worker.has.Skill"
READINESS_RULE = "Readiness(worker, role) = |has ∩ required| / |required|"


# ---- deterministic edge IDs -------------------------------------------------

def has_edge_id(worker_id: str, skill_id: str) -> str:
    return f"has::{worker_id}::{skill_id}"


def requires_edge_id(role_id: str, skill_id: str) -> str:
    return f"requires::{role_id}::{skill_id}"


def certifies_edge_id(cert_id: str, skill_id: str) -> str:
    return f"certifies::{cert_id}::{skill_id}"


def targets_edge_id(worker_id: str, role_id: str) -> str:
    return f"targets::{worker_id}::{role_id}"


def certgap_edge_id(worker_id: str, skill_id: str) -> str:
    return f"certgap::{worker_id}::{skill_id}"


def readiness_edge_id(worker_id: str, role_id: str) -> str:
    return f"readiness::{worker_id}::{role_id}"


# ---- the derivations (the only place these are computed) ---------------------

def cert_gap_skill_ids(worker: Worker, role: Role) -> list[str]:
    """Missing skills, in the role's required order (deterministic)."""
    have = set(worker.has_skill_ids)
    return [s for s in role.required_skill_ids if s not in have]


def readiness_score(worker: Worker, role: Role) -> float:
    required = role.required_skill_ids
    if not required:
        return 1.0
    have = set(worker.has_skill_ids)
    covered = sum(1 for s in required if s in have)
    return round(covered / len(required), 4)


# ---- edge builders ----------------------------------------------------------

def base_edges(onto: Ontology, as_of: str = ONTOLOGY_AS_OF) -> list[Edge]:
    edges: list[Edge] = []
    for w in onto.workers.values():
        for sid in w.has_skill_ids:
            edges.append(Edge(has_edge_id(w.id, sid), "has", w.id, sid,
                              provenance="source: worker skill record", effective_at=as_of))
        edges.append(Edge(targets_edge_id(w.id, w.target_role_id), "targets", w.id, w.target_role_id,
                          provenance="source: worker reskilling target", effective_at=as_of))
    for r in onto.roles.values():
        for sid in r.required_skill_ids:
            edges.append(Edge(requires_edge_id(r.id, sid), "requires", r.id, sid,
                              provenance="source: role competency model", effective_at=as_of))
    for c in onto.certifications.values():
        for sid in c.certifies_skill_ids:
            edges.append(Edge(certifies_edge_id(c.id, sid), "certifies", c.id, sid,
                              provenance="source: certification blueprint", effective_at=as_of))
    return edges


def derived_edges(onto: Ontology, as_of: str = ONTOLOGY_AS_OF) -> list[Edge]:
    """The inference the raw data does not contain: CertGap + Readiness."""
    prov = f"derived v{DERIVATION_VERSION}"
    edges: list[Edge] = []
    for w in onto.workers.values():
        role = onto.roles.get(w.target_role_id)
        if role is None:
            continue
        # CertGap: one derived edge per missing skill, justified by the requires edge.
        for sid in cert_gap_skill_ids(w, role):
            edges.append(Edge(
                certgap_edge_id(w.id, sid), "certgap", w.id, sid,
                derived=True, derivation_rule=CERTGAP_RULE,
                source_ref_ids=(requires_edge_id(role.id, sid),),
                provenance=f"{prov}: {CERTGAP_RULE}", effective_at=as_of, confidence=1.0,
            ))
        # Readiness: one derived edge worker->target role, score on `weight`.
        score = readiness_score(w, role)
        ref_ids = tuple(requires_edge_id(role.id, s) for s in role.required_skill_ids)
        edges.append(Edge(
            readiness_edge_id(w.id, role.id), "readiness", w.id, role.id,
            derived=True, derivation_rule=READINESS_RULE, source_ref_ids=ref_ids,
            provenance=f"{prov}: {READINESS_RULE}", effective_at=as_of, confidence=1.0, weight=score,
        ))
    return edges


def build_all_edges(onto: Ontology, as_of: str = ONTOLOGY_AS_OF,
                    source_badge: str = SOURCE_LIVE) -> list[Edge]:
    """Base + derived, stamped with a source badge (live vs mirror)."""
    all_edges = base_edges(onto, as_of) + derived_edges(onto, as_of)
    if source_badge != SOURCE_LIVE:
        all_edges = [Edge(**{**e.__dict__, "source_badge": source_badge}) for e in all_edges]
    return all_edges
