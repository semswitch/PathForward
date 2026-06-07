"""Search-mirror: the inference must materialize as first-class docs (FB1)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.iq import derivation as dv
from pathforward.iq import mirror
from pathforward.iq.models import SOURCE_MIRROR
from pathforward.iq.seed import build_seed, HERO_WORKER_ID


class TestMirror(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.edges = dv.build_all_edges(self.onto, source_badge=SOURCE_MIRROR)
        self.docs = mirror.build_mirror_docs(self.onto, self.edges)

    def test_non_empty_guard_passes(self):
        mirror.assert_non_empty(self.docs)  # raises if not

    def test_has_certgap_and_traversal_docs(self):
        kinds = {d["kind"] for d in self.docs}
        self.assertIn("derived_edge", kinds)
        self.assertIn("traversal_path", kinds)
        certgaps = [d for d in self.docs
                    if d["kind"] == "derived_edge" and d["edge"]["type"] == "certgap"]
        self.assertTrue(certgaps)

    def test_derived_docs_carry_provenance(self):
        for d in self.docs:
            if d["kind"] == "derived_edge":
                e = d["edge"]
                self.assertTrue(e["derivation_rule"])
                self.assertTrue(e["provenance"])
                self.assertTrue(e["effective_at"])
                self.assertEqual(e["source_badge"], SOURCE_MIRROR)

    def test_empty_guard_fails_loud(self):
        with self.assertRaises(AssertionError):
            mirror.assert_non_empty([{"kind": "base_edge", "edge": {"type": "has"}}])

    def test_hero_traversal_present(self):
        path_doc = next(d for d in self.docs if d["id"] == f"path::{HERO_WORKER_ID}")
        self.assertEqual(path_doc["path"]["meta"]["readiness"], 0.5)


if __name__ == "__main__":
    unittest.main()
