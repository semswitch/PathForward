"""Curator behaviour: the LLM ranks, but deterministic code owns which gaps are admissible and
which one is chosen. The chosen skill is ALWAYS a real, assessable, derived CertGap; an
inadmissible model pick is struck and the gate falls back to role order."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.client import FakeLLMClient, LLMResponse
from pathforward.agents.curator import Curator
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.models import Worker
from pathforward.iq.seed import build_seed, HERO_WORKER_ID


class _GarbageCuratorClient:
    """Ranks only inadmissible ids -> the gate filters everything -> fall back to role order."""
    def respond(self, instructions, input, *, previous_response_id=None, schema=None):
        return LLMResponse("r", "", {"ranking": ["S99", "S98"], "rationale": {}})


class _CleanCuratorClient:
    """Returns a VALID admissible ranking (reversed role order) with an admissible first pick,
    so the gate honours the model's reasoning and does not flag a correction."""
    def __init__(self, admissible):
        self._rank = list(reversed(admissible))

    def respond(self, instructions, input, *, previous_response_id=None, schema=None):
        return LLMResponse("r", "", {"ranking": self._rank, "rationale": {}})


class TestCurator(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()

    def _admissible(self, worker):
        role = self.onto.roles[worker.target_role_id]
        return [s for s in dv.cert_gap_skill_ids(worker, role)
                if traversal.is_assessable(s, self.onto)]

    def test_chosen_is_always_a_real_assessable_derived_gap(self):
        cur = Curator(FakeLLMClient())
        for wid in ("EMP-001", "EMP-002", "EMP-003", "EMP-004", "EMP-005", "EMP-006"):
            worker = self.onto.workers[wid]
            role = self.onto.roles[worker.target_role_id]
            d = cur.curate(worker, role, self.onto)
            if not self._admissible(worker):
                self.assertEqual(d.chosen_skill_id, "", f"{wid} has no assessable gap")
                continue
            self.assertIn(d.chosen_skill_id, dv.cert_gap_skill_ids(worker, role),
                          f"{wid}: chosen must be a derived gap")
            self.assertTrue(traversal.is_assessable(d.chosen_skill_id, self.onto),
                            f"{wid}: chosen must be assessable")

    def test_emp001_picks_S01(self):
        worker = self.onto.workers[HERO_WORKER_ID]
        role = self.onto.roles[worker.target_role_id]
        d = Curator(FakeLLMClient()).curate(worker, role, self.onto)
        self.assertEqual(d.chosen_skill_id, "S01")                 # pins the demo invariant
        self.assertEqual(d.chosen_edge_id, "certgap::EMP-001::S01")
        self.assertTrue(d.corrected)                               # code-test client over-reaches
        self.assertEqual(d.admissible_skill_ids, ("S01", "S02", "S08"))

    def test_inadmissible_pick_is_corrected_and_falls_back(self):
        worker = self.onto.workers[HERO_WORKER_ID]
        role = self.onto.roles[worker.target_role_id]
        d = Curator(_GarbageCuratorClient()).curate(worker, role, self.onto)
        self.assertTrue(d.corrected)
        self.assertEqual(d.chosen_skill_id, "S01")                 # admissible[0] (role order)
        # the garbage ids never leak into the ranking
        self.assertNotIn("S99", d.ranking)
        self.assertEqual(set(d.ranking), set(d.admissible_skill_ids))

    def test_admissible_llm_choice_is_honoured(self):
        worker = self.onto.workers[HERO_WORKER_ID]
        role = self.onto.roles[worker.target_role_id]
        admissible = self._admissible(worker)
        d = Curator(_CleanCuratorClient(admissible)).curate(worker, role, self.onto)
        self.assertFalse(d.corrected)                              # first pick was admissible
        self.assertEqual(d.chosen_skill_id, admissible[-1])        # reversed -> last gap chosen
        self.assertEqual(set(d.ranking), set(admissible))

    def test_zero_assessable_gap_returns_empty(self):
        # A worker whose ONLY missing skill is S09 (Containers) — required by R-DEVOPS but
        # certified by no certification -> not assessable -> no admissible gap -> fail-closed.
        role = self.onto.roles["R-DEVOPS"]              # requires S06,S07,S08,S09,S11
        worker = Worker("EMP-TEST", "Test", "at-risk role", "R-DEVOPS",
                        ("S06", "S07", "S08", "S11"), 5.0, ())
        self.assertEqual(dv.cert_gap_skill_ids(worker, role), ["S09"])
        self.assertFalse(traversal.is_assessable("S09", self.onto))
        d = Curator(FakeLLMClient()).curate(worker, role, self.onto)
        self.assertEqual(d.chosen_skill_id, "")
        self.assertEqual(d.chosen_edge_id, "")
        self.assertEqual(d.admissible_skill_ids, ())


if __name__ == "__main__":
    unittest.main()
