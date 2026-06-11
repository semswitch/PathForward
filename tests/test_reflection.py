"""Bounded reflection: on reject the Generator gets criterion NAMES + fixed code-owned remediation
only — never the gate's free-text reasons, citations, or the answer — and the regenerate is stateless
(previous_response_id dropped) so a chained attempt can't see its own prior answer-bearing draft."""
import ast
import inspect
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.client import FakeLLMClient, LLMResponse
from pathforward.agents.evidence_gate import EvidenceGate
from pathforward.agents.generator import Generator
from pathforward.agents.loop import REMEDIATION_BY_CRITERION, _build_feedback, run_assessment_loop
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.types import CriticConcern, CriticReview, Verdict
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import build_seed, HERO_WORKER_ID


class _RecordingGen:
    """Generator-side client that records each turn, then returns ungrounded @0 and grounded @1."""
    def __init__(self):
        self.calls = []

    def respond(self, instructions, input, *, previous_response_id=None, schema=None):
        p = json.loads(input)
        self.calls.append({"prev": previous_response_id, "feedback": p.get("feedback"),
                           "attempt": int(p.get("attempt", 0))})
        retrieved = () if int(p.get("attempt", 0)) == 0 else tuple(p.get("allowed_ref_ids", [])[:1])
        return LLMResponse(f"r{len(self.calls)}", "", FakeLLMClient._generate(p),
                           previous_response_id, retrieved_ref_ids=retrieved)


class TestReflectionAntiLeak(unittest.TestCase):
    def test_assembler_never_reads_gate_free_text(self):
        # AST guard: the assembler must not ACCESS verdict.failed_reasons (the gate's free text).
        # We check attribute access, not the string, so the docstring may safely name the field.
        tree = ast.parse(inspect.getsource(_build_feedback))
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        self.assertNotIn("failed_reasons", attrs)
        self.assertIn("criteria", attrs)        # it reads the boolean criteria map instead

    def test_feedback_is_only_names_and_static_remediation(self):
        verdict = Verdict(passed=False, criteria={"grounded": False, "single_correct": True},
                          failed_reasons=[{"criterion": "grounded",
                                           "reason": "LEAK: the answer is 24 hours",
                                           "citation": ["certgap::EMP-001::S01"]}])
        fb = _build_feedback(verdict, None, "core")
        self.assertEqual(fb["failed_criteria"], ["grounded"])
        self.assertEqual(fb["remediation"], [REMEDIATION_BY_CRITERION["grounded"]])
        blob = json.dumps(fb)
        for forbidden in ("LEAK", "24 hours", "certgap::EMP-001::S01"):
            self.assertNotIn(forbidden, blob)   # no gate free-text, answer, or ref_id leaks through

    def test_feedback_includes_critic_concerns_on_reject(self):
        verdict = Verdict(passed=False, criteria={"grounded": True}, failed_reasons=[])
        review = CriticReview(recommendation="reject", concerns=(CriticConcern("ambiguity", "high"),))
        fb = _build_feedback(verdict, review, "core")
        self.assertIn("ambiguity", fb["failed_criteria"])

    def test_remediation_is_subset_of_the_static_lookup(self):
        verdict = Verdict(passed=False, criteria={"grounded": False, "no_leakage": False},
                          failed_reasons=[])
        fb = _build_feedback(verdict, None, None)
        self.assertTrue(set(fb["remediation"]) <= set(REMEDIATION_BY_CRITERION.values()))

    def test_loop_reflection_present_and_stateless_on_regenerate(self):
        onto = build_seed()
        worker = onto.workers[HERO_WORKER_ID]
        edges = dv.build_all_edges(onto)
        driving = traversal.cert_gap_edges(worker, onto, edges)[0]
        skill = onto.skills[driving.target_id]
        allowed = traversal.approved_refs(worker, skill, onto)
        rec = _RecordingGen()
        res = run_assessment_loop(driving, skill, allowed, Generator(rec),
                                  EvidenceGate(LocalNumericChecker()))
        self.assertEqual(res.status, "verified")
        self.assertGreaterEqual(len(rec.calls), 2)
        self.assertIsNone(rec.calls[0]["feedback"])           # attempt 0: no feedback
        self.assertIsNotNone(rec.calls[1]["feedback"])        # attempt 1: bounded feedback present
        self.assertIsNone(rec.calls[1]["prev"])               # ...and STATELESS (prev dropped)
        self.assertIn("grounded", rec.calls[1]["feedback"]["failed_criteria"])


if __name__ == "__main__":
    unittest.main()
