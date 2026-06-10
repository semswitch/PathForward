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

    def test_agent_yaml_passes_azure_monitor_connection_string(self):
        manifest = Path("agent.yaml").read_text(encoding="utf-8")
        self.assertIn("name: AZURE_MONITOR_CONNECTION_STRING", manifest)
        self.assertIn("value: ${AZURE_MONITOR_CONNECTION_STRING}", manifest)

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

    def test_config_accepts_hosted_fabric_data_agent_base(self):
        old_base = os.environ.get("FABRIC_DATA_AGENT_OPENAI_BASE")
        try:
            os.environ["FABRIC_DATA_AGENT_OPENAI_BASE"] = (
                "https://api.fabric.microsoft.com/v1/workspaces/w/aiskills/a/aiassistant/openai/"
            )
            from pathforward.config import load_settings
            settings = load_settings("__missing__.env")
            self.assertEqual(settings.fabric_data_agent_openai_base,
                             "https://api.fabric.microsoft.com/v1/workspaces/w/aiskills/a/aiassistant/openai/")
        finally:
            if old_base is None:
                os.environ.pop("FABRIC_DATA_AGENT_OPENAI_BASE", None)
            else:
                os.environ["FABRIC_DATA_AGENT_OPENAI_BASE"] = old_base

    def test_live_hosted_prefers_direct_fabric_data_agent_client_when_configured(self):
        old = {name: os.environ.get(name) for name in (
            "PATHFORWARD_INSIGHTS_TIER",
            "PATHFORWARD_FABRIC_SP_TENANT_ID",
            "PATHFORWARD_FABRIC_SP_CLIENT_ID",
            "PATHFORWARD_FABRIC_SP_CLIENT_SECRET",
        )}
        try:
            os.environ["PATHFORWARD_INSIGHTS_TIER"] = "fabric-live"
            os.environ["PATHFORWARD_FABRIC_SP_TENANT_ID"] = "tenant"
            os.environ["PATHFORWARD_FABRIC_SP_CLIENT_ID"] = "client"
            os.environ["PATHFORWARD_FABRIC_SP_CLIENT_SECRET"] = "secret"
            from pathforward.config import Settings
            from pathforward.hosted_orchestrator import _build_clients

            settings = Settings(
                foundry_project_endpoint="https://example.services.ai.azure.com/api/projects/p",
                search_endpoint="https://search.example",
                fabric_connection_name="pathforward-fabric-user",
                fabric_data_agent_openai_base=(
                    "https://api.fabric.microsoft.com/v1/workspaces/w/aiskills/a/aiassistant/openai/"
                ),
            )
            clients, closeables = _build_clients(settings, "live", {})

            self.assertEqual(clients["insights"].__class__.__name__, "FabricDataAgentClient")
            self.assertEqual(clients["insights"].base_url,
                             "https://api.fabric.microsoft.com/v1/workspaces/w/aiskills/a/aiassistant/openai/")
            for client in closeables:
                client.close()
        finally:
            for name, value in old.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_fabric_live_hosted_insights_agent_uses_fabric_method(self):
        old = os.environ.get("PATHFORWARD_INSIGHTS_TIER")
        try:
            os.environ["PATHFORWARD_INSIGHTS_TIER"] = "fabric-live"
            from pathforward.hosted_orchestrator import _build_insights_agent
            from pathforward.agents.client import LLMResponse
            from pathforward.iq.seed import HERO_WORKER_ID, build_seed

            class StubFabricClient:
                def respond(self, instructions, input, *, previous_response_id=None, schema=None):
                    return LLMResponse("resp_stub", "fabric answer", {}, None)

            onto = build_seed()
            worker = onto.workers[HERO_WORKER_ID]
            role = onto.roles[worker.target_role_id]
            agent = _build_insights_agent(StubFabricClient(), "")
            insights = agent.analyze(worker, role, onto)

            self.assertEqual(insights.source, "fabric-live")
            self.assertEqual(insights.narrative, "fabric answer")
        finally:
            if old is None:
                os.environ.pop("PATHFORWARD_INSIGHTS_TIER", None)
            else:
                os.environ["PATHFORWARD_INSIGHTS_TIER"] = old


if __name__ == "__main__":
    unittest.main()
