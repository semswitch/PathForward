"""Build the Search-mirror documents (the GA runtime grounding path) and validate them.

Pre-materializes base edges, DERIVED edges (CertGap/Readiness with provenance +
validity-time), and per-worker traversal-path docs, then runs the build-time
non-empty guard. Writes data/generated/mirror/mirror_docs.json.

Run:  python scripts/build_mirror.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.iq import derivation as dv          # noqa: E402
from pathforward.iq import mirror                      # noqa: E402
from pathforward.iq.models import SOURCE_MIRROR        # noqa: E402
from pathforward.iq.seed import build_seed             # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data", "generated", "mirror")


def main() -> None:
    onto = build_seed()
    edges = dv.build_all_edges(onto, source_badge=SOURCE_MIRROR)
    docs = mirror.build_mirror_docs(onto, edges)
    mirror.assert_non_empty(docs)   # fail loud if inference didn't materialize
    path = mirror.write_mirror(docs, OUT)

    kinds: dict[str, int] = {}
    for d in docs:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    certgaps = sum(1 for d in docs if d["kind"] == "derived_edge" and d["edge"]["type"] == "certgap")
    print(f"mirror docs: {len(docs)} -> {path}")
    print(f"  by kind: {kinds}")
    print(f"  CertGap derived-edge docs: {certgaps}")
    print("  build-time non-empty guard: PASSED")


if __name__ == "__main__":
    main()
