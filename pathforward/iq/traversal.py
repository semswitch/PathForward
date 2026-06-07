"""Multi-hop traversal -> Glass-Box graph data.

Produces the node/edge structure the UI animates:

    Worker --targets--> Role --requires--> Skill <--certifies-- Certification
       \\--certgap(derived)--> Skill        \\--readiness(derived)--> Role

Every edge carries its stable ID, provenance, validity-time, and source badge so
the front-end can render the citation panel and the live/mirror degradation badge.
"""
from __future__ import annotations

from . import derivation as dv
from .models import Edge, Ontology, Skill, Worker


def _node(node_id: str, kind: str, label: str, **extra) -> dict:
    return {"id": node_id, "kind": kind, "label": label, **extra}


def build_glassbox(worker: Worker, onto: Ontology, edges: list[Edge]) -> dict:
    """Return {nodes, edges, meta} for the worker's reskilling traversal."""
    by_id = {e.id: e for e in edges}
    role = onto.roles[worker.target_role_id]

    nodes: dict[str, dict] = {}
    out_edges: list[dict] = []

    nodes[worker.id] = _node(worker.id, "worker", worker.name,
                             current_role=worker.current_role_title,
                             accessibility_needs=list(worker.accessibility_needs))
    nodes[role.id] = _node(role.id, "role", role.name)

    def add_edge(edge_id: str):
        e = by_id.get(edge_id)
        if e:
            out_edges.append(e.to_doc())

    # worker -> target role
    add_edge(dv.targets_edge_id(worker.id, role.id))

    # role -> required skills, and certifications that certify them
    for sid in role.required_skill_ids:
        skill = onto.skills[sid]
        nodes[sid] = _node(sid, "skill", skill.name, domain=skill.domain)
        add_edge(dv.requires_edge_id(role.id, sid))
        for cert in onto.certs_for_skill(sid):
            nodes[cert.id] = _node(cert.id, "certification", cert.name,
                                   recommended_hours=cert.recommended_hours)
            add_edge(dv.certifies_edge_id(cert.id, sid))

    # derived: certgap edges (worker -> missing skill) + readiness (worker -> role)
    gap = dv.cert_gap_skill_ids(worker, role)
    for sid in gap:
        add_edge(dv.certgap_edge_id(worker.id, sid))
    add_edge(dv.readiness_edge_id(worker.id, role.id))

    readiness = dv.readiness_score(worker, role)
    return {
        "nodes": list(nodes.values()),
        "edges": out_edges,
        "meta": {
            "worker_id": worker.id,
            "target_role_id": role.id,
            "cert_gap_skill_ids": gap,
            "readiness": readiness,
            "derivation_version": dv.DERIVATION_VERSION,
        },
    }


def cert_gap_edges(worker: Worker, onto: Ontology, edges: list[Edge]) -> list[Edge]:
    """The CertGap edges that drive the assessment blueprint, in role order."""
    role = onto.roles[worker.target_role_id]
    wanted = {dv.certgap_edge_id(worker.id, sid) for sid in dv.cert_gap_skill_ids(worker, role)}
    order = {dv.certgap_edge_id(worker.id, sid): i for i, sid in enumerate(role.required_skill_ids)}
    found = [e for e in edges if e.id in wanted]
    return sorted(found, key=lambda e: order.get(e.id, 1_000))


def approved_refs(worker: Worker, skill: Skill, onto: Ontology) -> tuple[str, ...]:
    """The grounding evidence neighborhood for assessing `skill` in `worker`'s gap context.

    An assessment item may ground ONLY in: the CertGap edge that selected the skill, the role's
    requirement for it, and the certifications (plus their corpus cards) that certify it. Anything
    cited outside this set fails the Verifier's grounded gate. Deterministically ordered.
    """
    refs = [dv.certgap_edge_id(worker.id, skill.id),
            dv.requires_edge_id(worker.target_role_id, skill.id)]
    for cert in onto.certs_for_skill(skill.id):
        refs.append(dv.certifies_edge_id(cert.id, skill.id))
        refs.append(f"corpus::{cert.id}")
    seen: set[str] = set()
    out: list[str] = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return tuple(out)
