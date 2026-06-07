"""The eval harness itself is deterministically verified offline.

With the FakeLLMClient (attempt 0 ungrounded -> attempt 1 grounded), every legit hero case must
score grounded + spine-intact. This proves the scoring code BEFORE we trust it on live Azure.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.client import FakeLLMClient
from pathforward.agents.generator import Generator
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.verifier import Verifier
from pathforward.eval.cases import build_eval_cases
from pathforward.eval.runner import Scorecard, run_eval_case
from pathforward.iq import derivation as dv
from pathforward.iq.seed import _HERO_WORKERS, build_seed


class EvalHarnessTest(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.edges = dv.build_all_edges(self.onto)
        self.cases = build_eval_cases(self.onto, self.edges)

    def test_cases_cover_every_hero_worker(self):
        worker_ids = {c.worker.id for c in self.cases}
        for wid, *_ in _HERO_WORKERS:
            self.assertIn(wid, worker_ids, f"{wid} has no eval case")
        # EMP-001's known gap (S01/S02/S08) must each appear as a driving edge
        emp1_skills = {c.skill.id for c in self.cases if c.worker.id == "EMP-001"}
        self.assertEqual(emp1_skills, {"S01", "S02", "S08"})

    def test_every_legit_case_scores_grounded_and_spine_intact_offline(self):
        gen = Generator(FakeLLMClient())
        ver = Verifier(LocalNumericChecker())
        results = [run_eval_case(c, gen, ver, self.onto) for c in self.cases]
        failed = [r.headline for r in results if not r.passed]
        self.assertTrue(all(r.passed for r in results), f"offline eval regressions: {failed}")

    def test_scorecard_reports_full_pass_rate(self):
        gen = Generator(FakeLLMClient())
        ver = Verifier(LocalNumericChecker())
        results = [run_eval_case(c, gen, ver, self.onto) for c in self.cases]
        card = Scorecard("offline eval", "grounded + spine-intact", results)
        self.assertEqual(card.n_passed, card.n)
        self.assertEqual(card.rate, 1.0)
        self.assertIn("grounded + spine-intact", card.to_markdown())


if __name__ == "__main__":
    unittest.main()
