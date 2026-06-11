"""Bounded Orchestrator/Conductor contract.

These tests validate code contracts for the Foundry Hosted Agent Orchestrator route: the agent may
propose a route, but deterministic code validates every route before execution and the Evidence Gate
/ mint trust boundary stays unchanged.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.client import FakeLLMClient, LLMResponse
from pathforward.agents.conductor import (
    Orchestrator,
    OrchestratorPlanError,
    OrchestratorStep,
    OrchestratorValidator,
)
from pathforward.agents.critic import Critic
from pathforward.agents.curator import Curator
from pathforward.agents.evidence_gate import EvidenceGate
from pathforward.agents.generator import Generator
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.orchestrator import run_orchestrated_multiagent
from pathforward.agents.planner import Planner
from pathforward.credential.mint import mint
from pathforward.iq import derivation as dv
from pathforward.iq.seed import HERO_WORKER_ID, build_seed


class StaticClient:
    def __init__(self, parsed: dict):
        self.parsed = parsed
        self.last_instructions = ""

    def respond(self, instructions: str, input: str, *, previous_response_id=None, schema=None):
        self.last_instructions = instructions
        return LLMResponse("static", json.dumps(self.parsed), self.parsed, previous_response_id)


class TestOrchestratorValidator(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.worker = self.onto.workers[HERO_WORKER_ID]
        self.role = self.onto.roles[self.worker.target_role_id]

    def test_valid_code_test_orchestrator_plan_is_bounded(self):
        plan = Orchestrator(FakeLLMClient()).plan(self.worker, self.role, self.onto)
        self.assertEqual(plan.worker_id, HERO_WORKER_ID)
        self.assertEqual(plan.steps[0].action, "curate")
        self.assertEqual(plan.first_target_skill_id(), "S01")
        self.assertIn("S01", plan.admissible_skill_ids)

    def test_forbidden_mint_action_is_rejected_before_execution(self):
        orch = Orchestrator(StaticClient({
            "steps": [{"action": "mint", "target_skill_id": "S01",
                       "rationale": "try to mint directly"}],
            "rationale": "bad route",
        }))
        with self.assertRaises(OrchestratorPlanError):
            orch.plan(self.worker, self.role, self.onto)

    def test_non_admissible_skill_is_rejected_before_execution(self):
        orch = Orchestrator(StaticClient({
            "steps": [
                {"action": "curate", "rationale": "start"},
                {"action": "assess", "target_skill_id": "S99",
                 "rationale": "invented skill"},
            ],
            "rationale": "bad target",
        }))
        with self.assertRaises(OrchestratorPlanError):
            orch.plan(self.worker, self.role, self.onto)

    def test_mint_if_verified_requires_prior_assessment(self):
        validator = OrchestratorValidator()
        plan = Orchestrator(FakeLLMClient()).plan(self.worker, self.role, self.onto)
        bad = type(plan)(
            worker_id=plan.worker_id,
            role_id=plan.role_id,
            admissible_skill_ids=plan.admissible_skill_ids,
            steps=(OrchestratorStep("curate"), OrchestratorStep("mint_if_verified")),
            rationale="missing assessment",
        )
        with self.assertRaises(OrchestratorPlanError):
            validator.validate(bad)

    def test_initial_phase_may_curate_before_post_curator_assessment(self):
        validator = OrchestratorValidator()
        plan = Orchestrator(FakeLLMClient()).plan(self.worker, self.role, self.onto)
        initial = type(plan)(
            worker_id=plan.worker_id,
            role_id=plan.role_id,
            admissible_skill_ids=plan.admissible_skill_ids,
            steps=(OrchestratorStep("curate", rationale="rank first"),),
            rationale="initial route",
        )
        self.assertEqual(validator.validate(initial, require_assessment=False).steps[0].action,
                         "curate")
        with self.assertRaises(OrchestratorPlanError):
            validator.validate(initial)

    def test_loaded_pathforward_skill_is_injected_into_orchestrator_prompt(self):
        client = StaticClient({
            "steps": [
                {"action": "curate", "rationale": "start"},
                {"action": "assess", "target_skill_id": "S01", "rationale": "assess"},
            ],
            "rationale": "skill-driven route",
        })
        orch = Orchestrator(client, skill_instructions="# PathForward Orchestrator Skill\nRun it.")
        orch.plan(self.worker, self.role, self.onto)
        self.assertIn("Loaded Foundry Skill `/pathforward`", client.last_instructions)
        self.assertIn("PathForward Orchestrator Skill", client.last_instructions)


class TestOrchestratedMultiAgent(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.edges = dv.build_all_edges(self.onto)

    def _agents(self):
        return (
            Orchestrator(FakeLLMClient()),
            Curator(FakeLLMClient()),
            Generator(FakeLLMClient()),
            EvidenceGate(LocalNumericChecker()),
            Planner(FakeLLMClient(), LocalNumericChecker()),
            Critic(FakeLLMClient()),
        )

    def test_orchestrated_path_verifies_and_mint_still_uses_code_spine(self):
        worker = self.onto.workers[HERO_WORKER_ID]
        role = self.onto.roles[worker.target_role_id]
        orch, cur, gen, gate, plan, critic = self._agents()
        res = run_orchestrated_multiagent(worker, self.onto, self.edges, orch, cur, gen, gate, plan,
                                          critic=critic)

        self.assertIsNotNone(res.orchestrator)
        self.assertEqual(res.orchestrator["selected_target_skill_id"], "S01")
        self.assertEqual(res.loop.status, "verified")
        self.assertEqual(res.loop.driving_edge_id, "certgap::EMP-001::S01")

        cred = mint(worker, role, res.loop.driving_edge_id, res.loop.targeted_skill_id, res.loop)
        self.assertEqual(cred.credential_subject["cited_edge_id"], res.loop.driving_edge_id)

    def test_invalid_orchestrator_route_fails_before_loop_runs(self):
        worker = self.onto.workers[HERO_WORKER_ID]
        bad_orch = Orchestrator(StaticClient({
            "steps": [
                {"action": "curate", "rationale": "start"},
                {"action": "assess", "target_skill_id": "S99",
                 "rationale": "invalid target"},
            ],
            "rationale": "bad route",
        }))
        _orch, cur, gen, gate, plan, critic = self._agents()
        with self.assertRaises(OrchestratorPlanError):
            run_orchestrated_multiagent(worker, self.onto, self.edges, bad_orch, cur, gen, gate,
                                        plan, critic=critic)


if __name__ == "__main__":
    unittest.main()
