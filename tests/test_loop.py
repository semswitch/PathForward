"""Loop behaviour: verify-then-stop, fail-closed abstain at N, and citations-survive."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.client import FakeLLMClient, LLMResponse
from pathforward.agents.generator import Generator
from pathforward.agents.loop import run_assessment_loop
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.verifier import Verifier
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import build_seed, HERO_WORKER_ID


class _AlwaysUngroundedClient:
    """Every generation cites nothing -> the Verifier always rejects."""
    def respond(self, instructions, input, *, previous_response_id=None, schema=None):
        return LLMResponse("r", "", {
            "stem": "ungrounded stem", "options": ["a", "b"], "answer_index": 0,
            "cited_ref_ids": [], "numeric_claim": None,
        })


class TestLoop(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.worker = self.onto.workers[HERO_WORKER_ID]
        self.edges = dv.build_all_edges(self.onto)
        self.driving = traversal.cert_gap_edges(self.worker, self.onto, self.edges)[0]
        self.skill = self.onto.skills[self.driving.target_id]
        self.allowed = tuple(self.driving.source_ref_ids) + ("corpus::AZ-204",)

    def test_verifies_and_stops(self):
        gen = Generator(FakeLLMClient())
        ver = Verifier(LocalNumericChecker())
        res = run_assessment_loop(self.driving, self.skill, self.allowed, gen, ver)
        self.assertEqual(res.status, "verified")
        self.assertEqual(res.attempts, 2)          # attempt 0 rejected, attempt 1 passes

    def test_citations_survive(self):
        gen = Generator(FakeLLMClient())
        ver = Verifier(LocalNumericChecker())
        res = run_assessment_loop(self.driving, self.skill, self.allowed, gen, ver)
        self.assertTrue(res.citations)             # propagated into the owned payload
        self.assertTrue(all(c in self.allowed for c in res.citations))
        # round-trips through serialization too
        self.assertEqual(res.to_doc()["citations"], list(res.citations))

    def test_fail_closed_abstain_at_N(self):
        gen = Generator(_AlwaysUngroundedClient())
        ver = Verifier(LocalNumericChecker())
        res = run_assessment_loop(self.driving, self.skill, self.allowed, gen, ver, max_attempts=3)
        self.assertEqual(res.status, "abstained")
        self.assertEqual(res.attempts, 3)
        self.assertEqual(res.citations, ())        # nothing minted from an abstain


if __name__ == "__main__":
    unittest.main()
