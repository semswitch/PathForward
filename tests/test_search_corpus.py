"""The Search corpus materializes the hero grounding refs so the live corpus-intersect-
retrieved gate can confirm EMP-001 -- BEFORE any Azure call."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.iq import derivation as dv
from pathforward.iq import mirror
from pathforward.iq.models import SOURCE_MIRROR
from pathforward.iq.seed import build_seed, HERO_EXPECTED_GAP, HERO_TARGET_ROLE_ID, HERO_WORKER_ID


class TestSearchCorpus(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.edges = dv.build_all_edges(self.onto, source_badge=SOURCE_MIRROR)
        self.docs = mirror.build_search_docs(self.onto, self.edges)
        self.by_ref = {d["ref_id"]: d for d in self.docs}

    def test_hero_certgaps_are_indexed(self):
        for sid in HERO_EXPECTED_GAP:                       # S01, S02, S08
            ref = dv.certgap_edge_id(HERO_WORKER_ID, sid)
            self.assertIn(ref, self.by_ref)
            self.assertEqual(self.by_ref[ref]["kind"], "derived_edge")

    def test_hero_grounding_refs_match_the_allow_list(self):
        # the exact refs run_assessment_loop approves for EMP-001's first gap (S01)
        for ref in ("requires::R-CLOUD::S01", "corpus::AZ-204"):
            self.assertIn(ref, self.by_ref)

    def test_readiness_doc_states_the_score(self):
        ref = dv.readiness_edge_id(HERO_WORKER_ID, HERO_TARGET_ROLE_ID)
        self.assertIn(ref, self.by_ref)
        self.assertIn("50%", self.by_ref[ref]["content"])    # readiness 0.5 rendered

    def test_az204_corpus_card_present(self):
        card = self.by_ref.get("corpus::AZ-204")
        self.assertIsNotNone(card)
        self.assertEqual(card["kind"], "corpus_card")
        self.assertIn("AZ-204", card["content"])

    def test_keys_are_search_safe_and_reversible(self):
        # Azure AI Search forbids ':' in document keys; the key must decode back to ref_id
        for d in self.docs:
            self.assertNotIn(":", d["id"])
            self.assertEqual(d["id"].replace("__", "::"), d["ref_id"])

    def test_guard_fails_without_corpus_cards(self):
        only_edges = [d for d in self.docs if d["kind"] != "corpus_card"]
        with self.assertRaises(AssertionError):
            mirror.assert_search_corpus(only_edges)


if __name__ == "__main__":
    unittest.main()
