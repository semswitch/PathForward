"""Critic agent: it RECOMMENDS, the Evidence Gate DECIDES. These tests pin the load-bearing
invariant that no Critic recommendation can pass an item the gate rejects, nor block one the gate
accepts (in P1 the recommendation is purely advisory), and that the Critic is constructed with only
an LLMClient (no handle to the gate/mint/result)."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.client import LLMResponse
from tests.fakes import FakeLLMClient
from pathforward.agents.critic import Critic
from pathforward.agents.evidence_gate import EvidenceGate
from pathforward.agents.generator import Generator
from pathforward.agents.loop import run_assessment_loop
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import build_seed, HERO_WORKER_ID


class _AlwaysPassCritic:
    def respond(self, instructions, input, *, previous_response_id=None, schema=None):
        return LLMResponse("r", "", {"recommendation": "pass", "concerns": [], "advisory_notes": ""})


class _AlwaysRejectCritic:
    def respond(self, instructions, input, *, previous_response_id=None, schema=None):
        return LLMResponse("r", "", {"recommendation": "reject",
                                     "concerns": [{"criterion_name": "ambiguity", "severity": "high"}],
                                     "advisory_notes": "looks ambiguous"})


class _AlwaysUngroundedGen:
    """Every generation cites nothing -> the Evidence Gate always rejects (mirrors test_loop)."""
    def respond(self, instructions, input, *, previous_response_id=None, schema=None):
        return LLMResponse("r", "", {"stem": "ungrounded", "options": ["a", "b"], "answer_index": 0,
                                     "cited_ref_ids": [], "numeric_claim": None})


class TestCritic(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.worker = self.onto.workers[HERO_WORKER_ID]
        self.edges = dv.build_all_edges(self.onto)
        self.driving = traversal.cert_gap_edges(self.worker, self.onto, self.edges)[0]
        self.skill = self.onto.skills[self.driving.target_id]
        self.allowed = traversal.approved_refs(self.worker, self.skill, self.onto)

    def test_critic_constructed_with_only_an_llm_client_as_required_dependency(self):
        params = inspect.signature(Critic.__init__).parameters
        self.assertEqual(list(params)[:2], ["self", "client"])
        self.assertEqual(params["client"].default, inspect._empty)
        self.assertEqual(params["skill_instructions"].default, "")

    def test_critic_cannot_pass_an_ungrounded_item(self):
        # An always-"pass" Critic must NOT be able to push an ungrounded item past the gate.
        res = run_assessment_loop(self.driving, self.skill, self.allowed,
                                  Generator(_AlwaysUngroundedGen()), EvidenceGate(LocalNumericChecker()),
                                  max_attempts=3, critic=Critic(_AlwaysPassCritic()))
        self.assertEqual(res.status, "abstained")
        self.assertEqual(res.citations, ())
        for t in res.transcript:
            self.assertEqual(t["critic"].recommendation, "pass")   # critic advised pass...
            self.assertFalse(t["verdict"].passed)                  # ...gate struck it anyway

    def test_critic_cannot_block_a_grounded_item(self):
        # An always-"reject" Critic must NOT be able to block an item the gate accepts (advisory).
        res = run_assessment_loop(self.driving, self.skill, self.allowed,
                                  Generator(FakeLLMClient()), EvidenceGate(LocalNumericChecker()),
                                  critic=Critic(_AlwaysRejectCritic()))
        self.assertEqual(res.status, "verified")
        passed = [t for t in res.transcript if t["verdict"].passed][-1]
        self.assertEqual(passed["critic"].recommendation, "reject")  # critic advised reject...
        self.assertTrue(passed["verdict"].passed)                    # ...gate verified anyway

    def test_critic_flags_quality_on_a_passing_item(self):
        # The maker-checker beat: on the gate-PASSING item the Critic still raises a concern about a
        # dimension the deterministic gate cannot compute (advisory, recorded in the transcript).
        res = run_assessment_loop(self.driving, self.skill, self.allowed,
                                  Generator(FakeLLMClient()), EvidenceGate(LocalNumericChecker()),
                                  critic=Critic(FakeLLMClient()))
        self.assertEqual(res.status, "verified")
        passed = [t for t in res.transcript if t["verdict"].passed][-1]
        self.assertEqual(passed["critic"].recommendation, "pass")
        self.assertTrue(passed["critic"].concerns)
        self.assertEqual(passed["critic"].concerns[0].criterion_name, "ambiguity")

    def test_loop_without_critic_is_unchanged(self):
        # Backward compatibility: no critic -> transcript records critic=None, behaviour as before.
        res = run_assessment_loop(self.driving, self.skill, self.allowed,
                                  Generator(FakeLLMClient()), EvidenceGate(LocalNumericChecker()))
        self.assertEqual(res.status, "verified")
        self.assertIsNone(res.transcript[0]["critic"])


if __name__ == "__main__":
    unittest.main()
