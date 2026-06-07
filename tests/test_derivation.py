"""The derived-edge unit test the red-team flagged as mandatory (FB4).

Asserts CertGap == requires − has and Readiness == coverage aggregate on the frozen
EMP-001 seed, and that derived edges carry provenance + validity-time + a rule.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.iq import derivation as dv
from pathforward.iq.seed import (build_seed, HERO_WORKER_ID, HERO_TARGET_ROLE_ID,
                                 HERO_EXPECTED_GAP, HERO_EXPECTED_READINESS)


class TestDerivation(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.worker = self.onto.workers[HERO_WORKER_ID]
        self.role = self.onto.roles[HERO_TARGET_ROLE_ID]

    def test_cert_gap_is_requires_minus_has(self):
        gap = dv.cert_gap_skill_ids(self.worker, self.role)
        self.assertEqual(gap, HERO_EXPECTED_GAP)
        # equivalence with set difference, role order preserved
        have = set(self.worker.has_skill_ids)
        expected = [s for s in self.role.required_skill_ids if s not in have]
        self.assertEqual(gap, expected)

    def test_readiness_is_coverage_aggregate(self):
        self.assertEqual(dv.readiness_score(self.worker, self.role), HERO_EXPECTED_READINESS)

    def test_derived_edges_carry_provenance_and_validity(self):
        derived = dv.derived_edges(self.onto)
        certgaps = [e for e in derived if e.type == "certgap" and e.source_id == HERO_WORKER_ID]
        self.assertEqual(len(certgaps), len(HERO_EXPECTED_GAP))
        for e in certgaps:
            self.assertTrue(e.derived)
            self.assertTrue(e.derivation_rule)
            self.assertEqual(e.effective_at, dv.ONTOLOGY_AS_OF)
            self.assertTrue(e.source_ref_ids)   # justified by the requires edge

    def test_readiness_edge_weight_matches_score(self):
        derived = dv.derived_edges(self.onto)
        rid = dv.readiness_edge_id(HERO_WORKER_ID, HERO_TARGET_ROLE_ID)
        edge = next(e for e in derived if e.id == rid)
        self.assertEqual(edge.weight, HERO_EXPECTED_READINESS)

    def test_edge_ids_are_stable(self):
        self.assertEqual(dv.certgap_edge_id("EMP-001", "S01"), "certgap::EMP-001::S01")


if __name__ == "__main__":
    unittest.main()
