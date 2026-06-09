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
from pathforward.agents.adaptive import AdaptiveController
from pathforward.agents.conductor import Orchestrator
from pathforward.agents.critic import Critic
from pathforward.agents.curator import Curator
from pathforward.agents.generator import Generator
from pathforward.agents.insights import ProgramInsightsAgent
from pathforward.agents.loop import run_assessment_loop
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.orchestrator import run_orchestrated_multiagent
from pathforward.agents.planner import Planner
from pathforward.agents.evidence_gate import EvidenceGate
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
                                   Generator(FakeLLMClient()), EvidenceGate(LocalNumericChecker()))

    def _adaptive(self):
        return AdaptiveController(calibration={f"item-{self.skill.id}": {"difficulty": 0.9}})

    def test_noop_when_not_configured(self):
        # No configure_tracing() -> the loop still runs, no spans, no error.
        result = self._run()
        self.assertEqual(result.status, "verified")

    def test_span_tree_and_attributes(self):
        exporter = InMemorySpanExporter()
        tracing.reset_tracing()
        self.assertTrue(tracing.configure_tracing(exporter=exporter))
        result = run_assessment_loop(
            self.driving, self.skill, self.allowed,
            Generator(FakeLLMClient()), EvidenceGate(LocalNumericChecker()),
            critic=Critic(FakeLLMClient()), adaptive=self._adaptive())
        cred = mint(self.worker, self.role, self.driving.id, self.skill.id, result)
        tracing.flush()

        spans = {s.name: s for s in exporter.get_finished_spans()}
        # FakeLLM: attempt 0 ungrounded -> struck, attempt 1 grounded -> verified
        for name in ("assessment.loop", "generate.attempt.0", "critic.attempt.0",
                     "verify.attempt.0", "generate.attempt.1", "critic.attempt.1",
                     "verify.attempt.1", "mint"):
            self.assertIn(name, spans, f"missing span {name}")

        root = spans["assessment.loop"]
        self.assertEqual(root.attributes.get("pf.status"), "verified")
        self.assertEqual(root.attributes.get("pf.attempts"), 2)
        self.assertEqual(root.attributes.get("pf.worker"), self.worker.id)
        self.assertEqual(root.attributes.get("pf.difficulty_band"), "stretch")
        self.assertIn("adaptive.band_selected", [e.name for e in root.events])
        self.assertIn("reflection.prepared", [e.name for e in root.events])

        # the on-camera refusal is a real, attributed span event
        v0 = spans["verify.attempt.0"]
        self.assertFalse(v0.attributes.get("pf.passed"))
        self.assertIn("gate.struck", [e.name for e in v0.events])
        self.assertTrue(spans["verify.attempt.1"].attributes.get("pf.passed"))
        self.assertEqual(spans["critic.attempt.0"].attributes.get("pf.critic_recommendation"),
                         "reject")
        self.assertEqual(spans["critic.attempt.1"].attributes.get("pf.critic_recommendation"),
                         "pass")
        self.assertIn("reflection.applied", [e.name for e in spans["generate.attempt.1"].events])

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
                            EvidenceGate(LocalNumericChecker()))
        tracing.flush()
        root = {s.name: s for s in exporter.get_finished_spans()}["assessment.loop"]
        self.assertEqual(root.attributes.get("pf.status"), "abstained")
        self.assertIn("abstained.fail_closed", [e.name for e in root.events])

    def test_orchestrated_full_flow_spans(self):
        exporter = InMemorySpanExporter()
        tracing.reset_tracing()
        tracing.configure_tracing(exporter=exporter)
        fake = FakeLLMClient()
        result = run_orchestrated_multiagent(
            self.worker, self.onto, dv.build_all_edges(self.onto),
            Orchestrator(fake, skill_instructions="# PathForward Orchestrator Skill\nRun it."),
            Curator(fake),
            Generator(fake),
            EvidenceGate(LocalNumericChecker()),
            Planner(fake, LocalNumericChecker()),
            critic=Critic(fake),
            adaptive=self._adaptive(),
            insights=ProgramInsightsAgent(fake),
        )
        tracing.flush()

        self.assertEqual(result.loop.status, "verified")
        spans = {s.name: s for s in exporter.get_finished_spans()}
        for name in ("orchestrated_multiagent", "orchestrator.initial", "curate",
                     "orchestrator.route", "assessment.loop", "critic.attempt.0",
                     "plan", "insights"):
            self.assertIn(name, spans, f"missing span {name}")
        self.assertTrue(spans["orchestrated_multiagent"].attributes.get("pf.skill_loaded"))
        self.assertEqual(spans["orchestrated_multiagent"].attributes.get("pf.orchestrator_target"),
                         result.orchestrator["selected_target_skill_id"])
        self.assertIn("orchestrator.initial.validated",
                      [e.name for e in spans["orchestrator.initial"].events])
        self.assertIn("orchestrator.route.validated",
                      [e.name for e in spans["orchestrator.route"].events])
        self.assertEqual(spans["insights"].attributes.get("pf.source"), "derivation-floor")


if __name__ == "__main__":
    unittest.main()
