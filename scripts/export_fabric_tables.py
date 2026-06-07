"""Export the /iq ontology to lakehouse-ready CSV tables for Fabric IQ.

Turns the version-pinned seed + derivation into a clean star schema a Fabric
lakehouse can ingest and the Ontology item can map onto:

  entities:       skills, roles, certifications, workers
  relationships:  role_requires_skill, worker_has_skill, cert_certifies_skill,
                  worker_targets_role
  derived:        certgap, readiness   (carry derivation_rule + provenance +
                                        source_ref_ids + validity-time + badge)

Derived tables come from the SAME derivation module that feeds the Search mirror,
so the Fabric path and the runtime path can never disagree. All synthetic, no PII.

    python scripts/export_fabric_tables.py        # -> data/generated/fabric/*.csv
"""
from __future__ import annotations

import csv
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.iq import derivation as dv  # noqa: E402
from pathforward.iq.seed import build_seed   # noqa: E402

OUT = os.path.join(_ROOT, "data", "generated", "fabric")


def _write(name: str, header: list[str], rows: list[list]) -> int:
    path = os.path.join(OUT, f"{name}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return len(rows)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    onto = build_seed()
    edges = dv.build_all_edges(onto)
    by_type: dict[str, list] = {}
    for e in edges:
        by_type.setdefault(e.type, []).append(e)

    counts: dict[str, int] = {}

    # ---- entity tables ----
    counts["skills"] = _write(
        "skills", ["skill_id", "name", "domain"],
        [[s.id, s.name, s.domain] for s in onto.skills.values()])
    counts["roles"] = _write(
        "roles", ["role_id", "name"],
        [[r.id, r.name] for r in onto.roles.values()])
    counts["certifications"] = _write(
        "certifications", ["cert_id", "name", "recommended_hours"],
        [[c.id, c.name, c.recommended_hours] for c in onto.certifications.values()])
    counts["workers"] = _write(
        "workers",
        ["worker_id", "name", "current_role_title", "target_role_id",
         "weekly_capacity_hours", "accessibility_needs"],
        [[w.id, w.name, w.current_role_title, w.target_role_id,
          w.weekly_capacity_hours, "|".join(w.accessibility_needs)]
         for w in onto.workers.values()])

    # ---- base relationship tables (source/target are entity-typed) ----
    rel = [
        ("role_requires_skill", "requires", "role_id", "skill_id"),
        ("worker_has_skill", "has", "worker_id", "skill_id"),
        ("cert_certifies_skill", "certifies", "cert_id", "skill_id"),
        ("worker_targets_role", "targets", "worker_id", "role_id"),
    ]
    for name, etype, src_col, tgt_col in rel:
        counts[name] = _write(
            name, ["edge_id", src_col, tgt_col, "provenance", "effective_at"],
            [[e.id, e.source_id, e.target_id, e.provenance, e.effective_at]
             for e in by_type.get(etype, [])])

    # ---- derived tables (the inference the raw data does not contain) ----
    counts["certgap"] = _write(
        "certgap",
        ["edge_id", "worker_id", "skill_id", "derivation_rule",
         "source_ref_ids", "provenance", "effective_at", "confidence", "source_badge"],
        [[e.id, e.source_id, e.target_id, e.derivation_rule,
          "|".join(e.source_ref_ids), e.provenance, e.effective_at,
          e.confidence, e.source_badge]
         for e in by_type.get("certgap", [])])
    counts["readiness"] = _write(
        "readiness",
        ["edge_id", "worker_id", "role_id", "readiness_score", "derivation_rule",
         "source_ref_ids", "provenance", "effective_at", "confidence", "source_badge"],
        [[e.id, e.source_id, e.target_id, e.weight, e.derivation_rule,
          "|".join(e.source_ref_ids), e.provenance, e.effective_at,
          e.confidence, e.source_badge]
         for e in by_type.get("readiness", [])])

    print(f"wrote {len(counts)} tables to {OUT}")
    for name, n in counts.items():
        print(f"  {name:22} {n:>4} rows")


if __name__ == "__main__":
    main()
