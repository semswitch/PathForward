"""IQ layer: ontology models, the version-pinned derivation module, the synthetic
seed, multi-hop traversal (Glass-Box graph data), and the Search-mirror builder.

Design rule (from the red-team): CertGap / Readiness are DERIVED here, once, in a
single version-pinned module (`derivation.py`) that feeds BOTH the Fabric ontology
load and the Search-mirror build — so a derivation bug cannot diverge the two.
"""
