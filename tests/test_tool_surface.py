import os
import unittest

from pathforward.tool_surface import MAINLINE_ROUTE, decisions_by_capability
from pathforward.agents.versioned import VERSIONED_AGENT_BY_ROLE, VERSIONED_AGENT_SPECS


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestToolSurfaceContract(unittest.TestCase):
    def test_mainline_is_hosted_orchestrator_route(self):
        self.assertEqual(MAINLINE_ROUTE, "foundry-hosted-orchestrator")
        decisions = decisions_by_capability()
        self.assertEqual(
            decisions["hosted-orchestrator"].status,
            "mainline-live-proven",
        )
        self.assertEqual(decisions["orchestrator-and-specialist-skills"].status,
                         "mainline-supporting-surface")

    def test_generator_and_fabric_direct_tools_are_explicit_foundry_seams(self):
        decisions = decisions_by_capability()
        generator = decisions["generator-search-grounding"]
        fabric = decisions["fabric-program-insights"]
        self.assertEqual(generator.status, "accepted-mainline-seam")
        self.assertIn("Azure AI Search", generator.surface)
        self.assertIn("corpus", generator.rationale)
        self.assertEqual(fabric.status, "accepted-mainline-seam")
        self.assertIn("MicrosoftFabricPreviewTool", fabric.surface)
        self.assertIn("direct published Fabric", fabric.surface)
        self.assertIn("off the credential mint path", fabric.rationale)

    def test_versioned_specialist_agents_are_declared_for_product_roles(self):
        self.assertEqual(
            set(VERSIONED_AGENT_BY_ROLE),
            {"orchestrator", "curator", "generator", "critic", "planner", "insights"},
        )
        by_role = VERSIONED_AGENT_BY_ROLE
        self.assertEqual(by_role["generator"].tool_surface, "azure_ai_search")
        self.assertEqual(by_role["insights"].tool_surface, "fabric_iq")
        self.assertEqual(
            {spec.agent_name for spec in VERSIONED_AGENT_SPECS},
            {
                "pathforward-specialist-orchestrator",
                "pathforward-specialist-curator",
                "pathforward-specialist-generator",
                "pathforward-specialist-critic",
                "pathforward-specialist-planner",
                "pathforward-specialist-insights-fabric",
            },
        )

    def test_approval_architecture_is_not_declared_by_tool_surface(self):
        decisions = decisions_by_capability()
        unauthorized_surface = decisions["agent-framework-workflow"]
        self.assertNotIn("credential-approval", decisions)
        self.assertEqual(unauthorized_surface.status, "locked-out-not-used")
        self.assertIn("Locked-out", unauthorized_surface.surface)

    def test_root_requirements_file_is_absent(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "requirements.txt")))

    def test_pyproject_does_not_advertise_unauthorized_agent_framework_extra(self):
        with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as fh:
            pyproject = fh.read()
        self.assertNotIn("workflow = [", pyproject)
        self.assertNotIn("agent-framework-foundry", pyproject)


if __name__ == "__main__":
    unittest.main()
