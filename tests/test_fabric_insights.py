"""Code-contract guards for the Fabric-live Program Insights tier.

These run without Azure SDK imports at module load time. They prove:
  - `FabricDataAgentClient` is import-safe and creates live resources lazily.
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


class _RecordingFabricClient:
    """Records the Fabric question and returns a free-text narrative."""

    def __init__(self, text: str):
        self._text = text
        self.last_input = None
        self.closed = False

    def respond(self, instructions, input, *, previous_response_id=None, schema=None):
        self.last_input = input
        return LLMResponse("resp_test", self._text, {}, None, retrieved_ref_ids=())

    def close(self):
        self.closed = True


class FabricInsightsCodeContractTest(unittest.TestCase):
    def test_direct_fabric_data_agent_client_is_import_safe_and_lazy(self):
        from pathforward.agents import foundry

        self.assertTrue(hasattr(foundry, "FabricDataAgentClient"))
        c = foundry.FabricDataAgentClient(
            base_url="https://api.fabric.microsoft.com/v1/workspaces/w/aiskills/a/aiassistant/openai/",
            tenant_id="tenant",
            client_id="client",
            client_secret="secret",
        )
        self.assertIsNone(c._openai)
        self.assertIsNone(c._assistant)
        self.assertEqual(c.scope, "https://analysis.windows.net/powerbi/api/.default")
        self.assertEqual(c.api_version, "2024-05-01-preview")

    def test_analyze_via_fabric_sets_source_and_keeps_code_anchor(self):
        onto = build_seed()
        worker = onto.workers[HERO_WORKER_ID]
        role = onto.roles[worker.target_role_id]
        recording_client = _RecordingFabricClient("11 workers target this role; mean readiness ~0.59.")
        agent = ProgramInsightsAgent(recording_client)

        ins = agent.analyze_via_fabric(worker, role, onto)

        self.assertEqual(ins.source, "fabric-live")
        self.assertTrue(ins.narrative)
        self.assertEqual(ins.worker_id, worker.id)
        self.assertEqual(ins.role_id, role.id)
        # the code-owned reconciliation anchor is present regardless of what the model returned
        self.assertTrue(ins.role_cohort)
        self.assertTrue(ins.worker_comparison)
        # the model was actually asked the cohort question (not handed pre-computed numbers)
        self.assertIn(role.id, recording_client.last_input)

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
