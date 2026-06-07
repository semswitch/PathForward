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


def _cert_content(c, onto: Ontology) -> str:
    skills = [onto.skills[s].name for s in c.certifies_skill_ids if s in onto.skills]
    return (f"Certification {c.id} '{c.name}'. Recommended study: {c.recommended_hours} hours. "
            f"Certifies these skills: {', '.join(skills) or 'none'}. Earning {c.id} demonstrates "
            f"competency in those skills toward a reskilling target.")


def _ref_to_key(ref_id: str) -> str:
    """Azure AI Search document keys forbid ':' — map the '::' id separator to '__'.

    A bijection (no source id contains '__'), so a retrieved key decodes back with
    key.replace('__', '::'). This keeps the index key tied to the derivation ref id
    that the assessment loop's allow-list is expressed in.
    """
    return ref_id.replace("::", "__")


def _membership(onto: Ontology, *ids: str) -> dict:
    m = {"worker_id": "", "skill_id": "", "role_id": "", "cert_id": ""}
    for _id in ids:
        if _id in onto.workers:
            m["worker_id"] = _id
        elif _id in onto.skills:
            m["skill_id"] = _id
        elif _id in onto.roles:
            m["role_id"] = _id
        elif _id in onto.certifications:
            m["cert_id"] = _id
    return m


def build_search_docs(onto: Ontology, edges: list[Edge]) -> list[dict]:
    """Flat docs for the Azure AI Search index the agent's AzureAISearchTool retrieves over.

    Each doc's `ref_id` is the derivation id (e.g. requires::R-CLOUD::S01, corpus::AZ-204),
    so a retrieved doc is directly a member of the loop's allow-list — that alignment is
    what lets the live `corpus INTERSECT retrieved` gate fire. `id` is the search-safe key.
    """
    docs: list[dict] = []

    def add(ref_id: str, kind: str, content: str, title: str, *,
            edge_type: str = "", worker_id: str = "", skill_id: str = "",
            role_id: str = "", cert_id: str = "") -> None:
        docs.append({
            "id": _ref_to_key(ref_id), "ref_id": ref_id, "kind": kind,
            "title": title, "content": content, "edge_type": edge_type,
            "worker_id": worker_id, "skill_id": skill_id, "role_id": role_id,
            "cert_id": cert_id, "source_badge": SOURCE_MIRROR,
        })

    for e in edges:
        kind = "derived_edge" if e.derived else "base_edge"
        add(e.id, kind, _edge_content(e, onto), f"{e.type}: {e.source_id} -> {e.target_id}",
            edge_type=e.type, **_membership(onto, e.source_id, e.target_id))

    # certification corpus cards — the grounded evidence for "which cert closes this gap"
    for c in onto.certifications.values():
        add(f"corpus::{c.id}", "corpus_card", _cert_content(c, onto),
            f"Certification {c.id} {c.name}", cert_id=c.id)

    # one traversal-path summary per worker (the multi-hop the Glass-Box renders)
    mirror_edges = dv.build_all_edges(onto, source_badge=SOURCE_MIRROR)
    for w in onto.workers.values():
        gb = traversal.build_glassbox(w, onto, mirror_edges)
        gap_names = [onto.skills[s].name for s in gb["meta"]["cert_gap_skill_ids"]]
        add(f"path::{w.id}", "traversal_path",
            (f"Reskilling path for {w.id}: from '{w.current_role_title}' toward "
             f"'{onto.roles[w.target_role_id].name}'. Readiness {gb['meta']['readiness']}. "
             f"Certification gaps: {', '.join(gap_names) or 'none'}."),
            f"Reskilling path for {w.id}", worker_id=w.id, role_id=w.target_role_id)
    return docs


def assert_search_corpus(docs: list[dict]) -> None:
    """Build-time guard — fail loud if the inference or the hero grounding didn't materialize."""
    kinds: dict[str, int] = {}
    for d in docs:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    if not kinds.get("derived_edge"):
        raise AssertionError("search corpus has ZERO derived-edge docs")
    if not kinds.get("corpus_card"):
        raise AssertionError("search corpus has ZERO certification corpus cards")
    if not kinds.get("traversal_path"):
        raise AssertionError("search corpus has ZERO traversal-path docs")
    refs = {d["ref_id"] for d in docs}
    # the exact grounding refs EMP-001's first gap is verified against — if these are not
    # retrievable, the live corpus-intersect-retrieved gate can never confirm the hero case
    for ref in ("requires::R-CLOUD::S01", "corpus::AZ-204", "certgap::EMP-001::S01"):
        if ref not in refs:
            raise AssertionError(f"search corpus missing required hero grounding ref: {ref}")


def write_mirror(docs: list[dict], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "mirror_docs.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(docs, f, indent=2)
    return path
