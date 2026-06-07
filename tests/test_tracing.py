"""Tracing emits the expected span tree + attributes (via an in-memory exporter), and is a
no-op when not configured."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    _OTEL = True
except ImportError:  # the offline core runs stdlib-only; tracing is an optional layer
    _OTEL = False

from pathforward.agents.client import FakeLLMClient
from pathforward.agents.generator import Generator
from pathforward.agents.loop import run_assessment_loop
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.verifier import Verifier
from pathforward.credential.mint import mint
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import build_seed, HERO_WORKER_ID
from pathforward.obs import tracing


@unittest.skipUnless(_OTEL, "opentelemetry not installed (optional observability layer)")
class TracingTest(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.worker = self.onto.workers[HERO_WORKER_ID]
        self.role = self.onto.roles[self.worker.target_role_id]
        edges = dv.build_all_edges(self.onto)
        self.driving = traversal.cert_gap_edges(self.worker, self.onto, edges)[0]
        self.skill = self.onto.skills[self.driving.target_id]
        self.allowed = traversal.approved_refs(self.worker, self.skill, self.onto)

    def tearDown(self):
        tracing.reset_tracing()

    def _run(self):
        return run_assessment_loop(self.driving, self.skill, self.allowed,
                                   Generator(FakeLLMClient()), Verifier(LocalNumericChecker()))

    def test_noop_when_not_configured(self):
        # No configure_tracing() -> the loop still runs, no spans, no error.
        result = self._run()
        self.assertEqual(result.status, "verified")

    def test_span_tree_and_attributes(self):
        exporter = InMemorySpanExporter()
        tracing.reset_tracing()
        self.assertTrue(tracing.configure_tracing(exporter=exporter))
        result = self._run()
        cred = mint(self.worker, self.role, self.driving.id, self.skill.id, result)
        tracing.flush()

        spans = {s.name: s for s in exporter.get_finished_spans()}
        # FakeLLM: attempt 0 ungrounded -> struck, attempt 1 grounded -> verified
        for name in ("assessment.loop", "generate.attempt.0", "verify.attempt.0",
                     "generate.attempt.1", "verify.attempt.1", "mint"):
            self.assertIn(name, spans, f"missing span {name}")

        root = spans["assessment.loop"]
        self.assertEqual(root.attributes.get("pf.status"), "verified")
        self.assertEqual(root.attributes.get("pf.attempts"), 2)
        self.assertEqual(root.attributes.get("pf.worker"), self.worker.id)

        # the on-camera refusal is a real, attributed span event
        v0 = spans["verify.attempt.0"]
        self.assertFalse(v0.attributes.get("pf.passed"))
        self.assertIn("verifier.struck", [e.name for e in v0.events])
        self.assertTrue(spans["verify.attempt.1"].attributes.get("pf.passed"))

        # generate spans carry the retrieval count; mint records the derived readiness
        self.assertIn("pf.retrieved", spans["generate.attempt.1"].attributes)
        self.assertTrue(spans["mint"].attributes.get("pf.minted"))
        self.assertEqual(spans["mint"].attributes.get("pf.readiness"),
                         cred.credential_subject["readiness"])

    def test_abstain_emits_fail_closed_event(self):
        exporter = InMemorySpanExporter()
        tracing.reset_tracing()
        tracing.configure_tracing(exporter=exporter)
        # force abstention: an empty corpus means every citation is struck for all 3 attempts
        run_assessment_loop(self.driving, self.skill, (), Generator(FakeLLMClient()),
                            Verifier(LocalNumericChecker()))
        tracing.flush()
        root = {s.name: s for s in exporter.get_finished_spans()}["assessment.loop"]
        self.assertEqual(root.attributes.get("pf.status"), "abstained")
        self.assertIn("abstained.fail_closed", [e.name for e in root.events])


if __name__ == "__main__":
    unittest.main()
