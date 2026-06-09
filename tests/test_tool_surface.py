import os
import unittest

from pathforward.tool_surface import MAINLINE_ROUTE, decisions_by_capability


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestToolSurfaceContract(unittest.TestCase):
    def test_mainline_is_hosted_orchestrator_route(self):
        self.assertEqual(MAINLINE_ROUTE, "foundry-hosted-orchestrator")
        decisions = decisions_by_capability()
        self.assertEqual(
            decisions["hosted-orchestrator"].status,
            "mainline-local-proven-live-pending",
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
        self.assertIn("off the credential mint path", fabric.rationale)

    def test_approval_is_the_remaining_mainline_surface_not_workflow(self):
        decisions = decisions_by_capability()
        approval = decisions["credential-approval"]
        workflow = decisions["agent-framework-workflow"]
        self.assertEqual(approval.status, "hosted-local-proven-live-pending")
        self.assertIn("Hosted Agent", approval.surface)
        self.assertEqual(workflow.status, "locked-out-not-used")
        self.assertIn("Locked-out", workflow.surface)

    def test_default_requirements_do_not_pull_in_workflow_projection(self):
        with open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8") as fh:
            requirements = fh.read()
        self.assertNotIn("agent-framework", requirements)
        self.assertNotIn("agent-framework-foundry", requirements)

    def test_pyproject_does_not_advertise_workflow_extra(self):
        with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as fh:
            pyproject = fh.read()
        self.assertNotIn("workflow = [", pyproject)
        self.assertNotIn("agent-framework-foundry", pyproject)


if __name__ == "__main__":
    unittest.main()
