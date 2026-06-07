"""Search-mirror builder — the GA runtime grounding path.

The red-team's load-bearing correction: a plain Azure AI Search index does
keyword/vector/hybrid retrieval only — it cannot traverse a graph or compute a
set-difference. So we PRE-MATERIALIZE the inference: one document per base edge,
one per DERIVED edge (carrying the derivation rule + source ref_ids + provenance +
validity-time), and one per demo traversal-path. The agent grounds on these docs;
the "reasoning" was done at build time in `derivation.py`.

`assert_non_empty` is the build-time guard: if the derived edges or traversal docs
are missing, the mirror silently guts the Best-IQ story — so we fail the build loud.
"""
from __future__ import annotations

import json
import os

from . import derivation as dv
from . import traversal
from .models import Edge, Ontology, SOURCE_MIRROR


def _edge_content(e: Edge, onto: Ontology) -> str:
    """Natural-language serialization the retriever grounds on."""
    def label(_id: str) -> str:
        if _id in onto.skills:
            return f"skill '{onto.skills[_id].name}'"
        if _id in onto.roles:
            return f"role '{onto.roles[_id].name}'"
        if _id in onto.certifications:
            return f"certification '{onto.certifications[_id].name}'"
        if _id in onto.workers:
            return f"worker {_id}"
        return _id

    src, tgt = label(e.source_id), label(e.target_id)
    if e.type == "certgap":
        return (f"Certification gap: {src} (targeting their reskilling role) is missing {tgt}. "
                f"Derived as {e.derivation_rule}. Justified by {', '.join(e.source_ref_ids)}. "
                f"Valid as of {e.effective_at} (confidence {e.confidence}).")
    if e.type == "readiness":
        return (f"Readiness: {src} is {round((e.weight or 0) * 100)}% ready for {tgt}. "
                f"Derived as {e.derivation_rule}. Valid as of {e.effective_at}.")
    verb = {"has": "has", "requires": "requires", "certifies": "certifies", "targets": "is targeting"}[e.type]
    return f"{src} {verb} {tgt}. {e.provenance}. Valid as of {e.effective_at}."


def build_mirror_docs(onto: Ontology, edges: list[Edge]) -> list[dict]:
    docs: list[dict] = []
    for e in edges:
        kind = "derived_edge" if e.derived else "base_edge"
        docs.append({
            "id": f"edge::{e.id}",
            "kind": kind,
            "content": _edge_content(e, onto),
            "edge": e.to_doc(),
            "source_badge": SOURCE_MIRROR,
        })
    # one traversal-path doc per worker (the multi-hop the Glass-Box renders)
    mirror_edges = dv.build_all_edges(onto, source_badge=SOURCE_MIRROR)
    for w in onto.workers.values():
        gb = traversal.build_glassbox(w, onto, mirror_edges)
        gap_names = [onto.skills[s].name for s in gb["meta"]["cert_gap_skill_ids"]]
        docs.append({
            "id": f"path::{w.id}",
            "kind": "traversal_path",
            "content": (f"Reskilling path for {w.id}: from '{w.current_role_title}' toward "
                        f"'{onto.roles[w.target_role_id].name}'. Readiness {gb['meta']['readiness']}. "
                        f"Certification gaps: {', '.join(gap_names) or 'none'}."),
            "path": gb,
            "source_badge": SOURCE_MIRROR,
        })
    return docs


def assert_non_empty(docs: list[dict]) -> None:
    """Build-time guard — fail loud if the inference didn't materialize."""
    derived = [d for d in docs if d["kind"] == "derived_edge"]
    certgaps = [d for d in derived if d["edge"]["type"] == "certgap"]
    paths = [d for d in docs if d["kind"] == "traversal_path"]
    if not certgaps:
        raise AssertionError("mirror build produced ZERO CertGap derived-edge docs")
    if not paths:
        raise AssertionError("mirror build produced ZERO traversal-path docs")


def write_mirror(docs: list[dict], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "mirror_docs.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(docs, f, indent=2)
    return path
