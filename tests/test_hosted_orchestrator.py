import os
import unittest
from pathlib import Path

from pathforward.hosted_orchestrator import HostedRequest, _SKILL_NAMES, _run_hosted_orchestrator_inner
from pathforward.skills import read_skill_file
from tests.fakes import FakeLLMClient


ROOT = Path(__file__).resolve().parents[1]


def _skill_bodies() -> dict[str, str]:
    return {
        name: read_skill_file(ROOT / "skills" / name / "SKILL.md").instructions
        for name in _SKILL_NAMES
    }


def _code_test_clients(insights=None) -> dict:
    client = FakeLLMClient()
    return {
        "orchestrator": client,
        "curator": client,
        "generator": client,
        "critic": client,
        "planner": client,
        "insights": insights or client,
    }


def _run_code_contract(request: HostedRequest, clients: dict | None = None) -> dict:
    return _run_hosted_orchestrator_inner(
        request,
        "code-test",
        _skill_bodies(),
        {"source": "unit-test"},
        clients or _code_test_clients(),
    )


class HostedOrchestratorTests(unittest.TestCase):
    def test_code_contract_hosted_route_requests_approval_without_minting(self):
        doc = _run_code_contract(HostedRequest(
            message="Run /pathforward for EMP-001",
            approve_mint=False,
        ))
        self.assertEqual(doc["surface"], "foundry-hosted-agent")
        self.assertEqual(doc["mode"], "code-test")
        self.assertEqual(doc["skill_evidence"]["source"], "unit-test")
        self.assertEqual(doc["result"]["loop"]["status"], "verified")
        self.assertIsNotNone(doc["approval_request"])
        self.assertIsNone(doc["credential"])

    def test_code_contract_hosted_route_mints_only_with_explicit_approval(self):
        doc = _run_code_contract(HostedRequest(
            message="Run /pathforward for EMP-001 with approved mint",
            approve_mint=True,
            approver="unit-test",
        ))
        self.assertEqual(doc["result"]["loop"]["status"], "verified")
        self.assertIsNotNone(doc["credential"])
        subject = doc["credential"]["credentialSubject"]
        self.assertEqual(subject["cited_edge_id"], doc["result"]["loop"]["driving_edge_id"])

    def test_code_contract_hosted_route_denied_approval_fails_closed(self):
        doc = _run_code_contract(HostedRequest(
            message="Run /pathforward for EMP-001 with denied mint",
            deny_mint=True,
            approver="unit-test",
        ))
        self.assertEqual(doc["result"]["loop"]["status"], "verified")
        self.assertIsNotNone(doc["approval_request"])
        self.assertIsNone(doc["credential"])
        self.assertIn("denied", doc["mint_error"].lower())

    def test_code_contract_hosted_route_abstain_probe_never_requests_mint(self):
        doc = _run_code_contract(HostedRequest(
            message="Run /pathforward semantic ABSTAIN proof",
            abstain_probe=True,
            approve_mint=True,
            approver="unit-test",
        ))
        self.assertEqual(doc["worker_id"], "EMP-ABSTAIN")
        self.assertEqual(doc["result"]["loop"]["status"], "abstained")
        self.assertEqual(doc["result"]["curator"]["chosen_skill_id"], "")
        self.assertIsNone(doc["approval_request"])
        self.assertIsNone(doc["credential"])
        self.assertEqual(doc["mint_error"], "")

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
        old_azure_project = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
        old_project = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        old_model = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME")
        try:
            os.environ.pop("AZURE_AI_PROJECT_ENDPOINT", None)
            os.environ["FOUNDRY_PROJECT_ENDPOINT"] = "https://example.services.ai.azure.com/api/projects/p"
            os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"] = "reasoning"
            from pathforward.config import load_settings
            settings = load_settings("__missing__.env")
            self.assertEqual(settings.foundry_project_endpoint,
                             "https://example.services.ai.azure.com/api/projects/p")
            self.assertEqual(settings.model_deployment, "reasoning")
        finally:
            if old_azure_project is None:
                os.environ.pop("AZURE_AI_PROJECT_ENDPOINT", None)
            else:
                os.environ["AZURE_AI_PROJECT_ENDPOINT"] = old_azure_project
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
            clients, closeables = _build_clients(settings, {})

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

    def test_live_hosted_rejects_non_fabric_insights_tier(self):
        old = os.environ.get("PATHFORWARD_INSIGHTS_TIER")
        try:
            os.environ["PATHFORWARD_INSIGHTS_TIER"] = "derivation-floor"
            from pathforward.config import Settings
            from pathforward.hosted_orchestrator import _build_clients

            settings = Settings(
                foundry_project_endpoint="https://example.services.ai.azure.com/api/projects/p",
                search_endpoint="https://search.example",
                fabric_connection_name="pathforward-fabric-user",
            )
            with self.assertRaisesRegex(RuntimeError, "requires PATHFORWARD_INSIGHTS_TIER=fabric-live"):
                _build_clients(settings, {})
        finally:
            if old is None:
                os.environ.pop("PATHFORWARD_INSIGHTS_TIER", None)
            else:
                os.environ["PATHFORWARD_INSIGHTS_TIER"] = old

    def test_live_hosted_requires_fabric_configuration(self):
        old = os.environ.get("PATHFORWARD_INSIGHTS_TIER")
        try:
            os.environ.pop("PATHFORWARD_INSIGHTS_TIER", None)
            from pathforward.config import Settings
            from pathforward.hosted_orchestrator import _build_clients

            settings = Settings(
                foundry_project_endpoint="https://example.services.ai.azure.com/api/projects/p",
                search_endpoint="https://search.example",
            )
            with self.assertRaisesRegex(RuntimeError, "Fabric-live Program Insights requires"):
                _build_clients(settings, {})
        finally:
            if old is None:
                os.environ.pop("PATHFORWARD_INSIGHTS_TIER", None)
            else:
                os.environ["PATHFORWARD_INSIGHTS_TIER"] = old

    def test_fabric_live_hosted_insights_agent_uses_fabric_method(self):
        old = os.environ.get("PATHFORWARD_INSIGHTS_TIER")
        try:
            os.environ["PATHFORWARD_INSIGHTS_TIER"] = "fabric-live"
            from pathforward.hosted_orchestrator import _build_insights_agent
            from pathforward.agents.client import LLMResponse
            from pathforward.iq.seed import HERO_WORKER_ID, build_seed

            class StubFabricClient:
                def respond(self, instructions, input, *, previous_response_id=None, schema=None):
                    return LLMResponse("resp_test", "fabric answer", {}, None)

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

    def test_hosted_fabric_failure_fails_closed(self):
        old = os.environ.get("PATHFORWARD_INSIGHTS_TIER")
        try:
            os.environ["PATHFORWARD_INSIGHTS_TIER"] = "fabric-live"
            class FailingFabricClient:
                def respond(self, instructions, input, *, previous_response_id=None, schema=None):
                    raise RuntimeError("Fabric data-agent run ended with status failed: server_error")

            with self.assertRaisesRegex(RuntimeError, "Fabric data-agent run ended"):
                _run_code_contract(
                    HostedRequest(message="Run /pathforward for EMP-001"),
                    clients=_code_test_clients(FailingFabricClient()),
                )
        finally:
            if old is None:
                os.environ.pop("PATHFORWARD_INSIGHTS_TIER", None)
            else:
                os.environ["PATHFORWARD_INSIGHTS_TIER"] = old


if __name__ == "__main__":
    unittest.main()
