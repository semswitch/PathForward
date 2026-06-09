import os
import unittest
from pathlib import Path

from pathforward.hosted_orchestrator import HostedRequest, run_hosted_orchestrator


class HostedOrchestratorTests(unittest.TestCase):
    def test_offline_hosted_route_requests_approval_without_minting(self):
        doc = run_hosted_orchestrator(HostedRequest(
            message="Run /pathforward for EMP-001",
            mode="offline",
            approve_mint=False,
        ))
        self.assertEqual(doc["surface"], "foundry-hosted-agent")
        self.assertEqual(doc["mode"], "offline")
        self.assertEqual(doc["skill_evidence"]["source"], "local-skill-files")
        self.assertEqual(doc["result"]["loop"]["status"], "verified")
        self.assertIsNotNone(doc["approval_request"])
        self.assertIsNone(doc["credential"])

    def test_offline_hosted_route_mints_only_with_explicit_approval(self):
        doc = run_hosted_orchestrator(HostedRequest(
            message="Run /pathforward for EMP-001 with approved mint",
            mode="offline",
            approve_mint=True,
            approver="unit-test",
        ))
        self.assertEqual(doc["result"]["loop"]["status"], "verified")
        self.assertIsNotNone(doc["credential"])
        subject = doc["credential"]["credentialSubject"]
        self.assertEqual(subject["cited_edge_id"], doc["result"]["loop"]["driving_edge_id"])

    def test_agent_yaml_does_not_set_foundry_reserved_environment(self):
        manifest = Path("agent.yaml").read_text(encoding="utf-8")
        forbidden = ("FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_AGENT_NAME", "FOUNDRY_TOOLBOX_ENDPOINT",
                     "APPLICATIONINSIGHTS_CONNECTION_STRING", "PORT")
        for name in forbidden:
            self.assertNotIn(f"name: {name}", manifest)

    def test_config_accepts_hosted_runtime_env_names(self):
        old_project = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        old_model = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME")
        try:
            os.environ["FOUNDRY_PROJECT_ENDPOINT"] = "https://example.services.ai.azure.com/api/projects/p"
            os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"] = "reasoning"
            from pathforward.config import load_settings
            settings = load_settings("__missing__.env")
            self.assertEqual(settings.foundry_project_endpoint,
                             "https://example.services.ai.azure.com/api/projects/p")
            self.assertEqual(settings.model_deployment, "reasoning")
        finally:
            if old_project is None:
                os.environ.pop("FOUNDRY_PROJECT_ENDPOINT", None)
            else:
                os.environ["FOUNDRY_PROJECT_ENDPOINT"] = old_project
            if old_model is None:
                os.environ.pop("AZURE_AI_MODEL_DEPLOYMENT_NAME", None)
            else:
                os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"] = old_model

    def test_config_treats_manifest_placeholders_as_unset(self):
        old_connection = os.environ.get("FABRIC_CONNECTION_NAME")
        try:
            os.environ["FABRIC_CONNECTION_NAME"] = "${FABRIC_CONNECTION_NAME}"
            from pathforward.config import load_settings
            settings = load_settings("__missing__.env")
            self.assertEqual(settings.fabric_connection_name, "")
        finally:
            if old_connection is None:
                os.environ.pop("FABRIC_CONNECTION_NAME", None)
            else:
                os.environ["FABRIC_CONNECTION_NAME"] = old_connection


if __name__ == "__main__":
    unittest.main()
