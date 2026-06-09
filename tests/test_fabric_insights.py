"""Offline guards for the Fabric-live Program Insights tier.

These run with NO azure SDK installed (the live client imports azure lazily). They prove:
  - `FabricInsightsClient` is offline-safe (constructable without azure; lazy create).
  - `analyze_via_fabric` returns a fabric-live ProgramInsights that still carries the code-owned
    `cohort.py` aggregates as the reconciliation anchor.
  - the insights module stays OFF the trust path (imports neither the gate nor mint).
"""
from __future__ import annotations

import ast
import os
import unittest

from pathforward.agents.client import LLMResponse
from pathforward.agents.insights import ProgramInsightsAgent
from pathforward.iq.seed import HERO_WORKER_ID, build_seed

_INSIGHTS_SRC = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             "pathforward", "agents", "insights.py")


class _StubFabricClient:
    """Stands in for FabricInsightsClient: records the question, returns a free-text narrative."""

    def __init__(self, text: str):
        self._text = text
        self.last_input = None
        self.closed = False

    def respond(self, instructions, input, *, previous_response_id=None, schema=None):
        self.last_input = input
        return LLMResponse("resp_stub", self._text, {}, None, retrieved_ref_ids=())

    def close(self):
        self.closed = True


class FabricInsightsOfflineTest(unittest.TestCase):
    def test_client_is_offline_safe_and_lazy(self):
        # Importable and constructable with NO azure installed; the agent version is created lazily.
        from pathforward.agents import foundry

        self.assertTrue(hasattr(foundry, "FabricInsightsClient"))
        c = foundry.FabricInsightsClient(endpoint="https://x", connection_name="pf-fabric")
        self.assertIsNone(c._agent)        # nothing created until respond()
        self.assertTrue(c.force_tool)      # the Fabric tool is forced by default

    def test_analyze_via_fabric_sets_source_and_keeps_code_anchor(self):
        onto = build_seed()
        worker = onto.workers[HERO_WORKER_ID]
        role = onto.roles[worker.target_role_id]
        stub = _StubFabricClient("11 workers target this role; mean readiness ~0.59.")
        agent = ProgramInsightsAgent(stub)

        ins = agent.analyze_via_fabric(worker, role, onto)

        self.assertEqual(ins.source, "fabric-live")
        self.assertTrue(ins.narrative)
        self.assertEqual(ins.worker_id, worker.id)
        self.assertEqual(ins.role_id, role.id)
        # the code-owned reconciliation anchor is present regardless of what the model returned
        self.assertTrue(ins.role_cohort)
        self.assertTrue(ins.worker_comparison)
        # the model was actually asked the cohort question (not handed pre-computed numbers)
        self.assertIn(role.id, stub.last_input)

    def test_insights_module_stays_off_the_trust_path(self):
        # No import of the Evidence Gate or mint anywhere in insights.py (AST-level, not substring).
        with open(_INSIGHTS_SRC, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
                for alias in node.names:
                    imported.add(f"{node.module}.{alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
        joined = " ".join(imported)
        self.assertNotIn("evidence_gate", joined)
        self.assertNotIn("credential", joined)
        self.assertNotIn("mint", joined)


if __name__ == "__main__":
    unittest.main()
