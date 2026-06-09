"""Shared client wiring for PathForward demo/export scripts.

The default path is deterministic rehearsal (`FakeLLMClient`). `live=True` swaps in the
Foundry/Fabric prompt-agent clients behind the same seams without changing the orchestrator or the
trust boundary. The Evidence Gate and LocalNumericChecker stay local deterministic code in every mode.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from pathforward.agents.analyst import LocalAnalyst
from pathforward.agents.client import FakeLLMClient
from pathforward.agents.critic import Critic
from pathforward.agents.curator import Curator
from pathforward.agents.evidence_gate import EvidenceGate
from pathforward.agents.foundry import FabricInsightsClient, FoundryLLMClient, ReasoningFoundryClient
from pathforward.agents.generator import Generator
from pathforward.agents.insights import ProgramInsightsAgent
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.planner import Planner
from pathforward.config import Settings
from pathforward.iq.models import Ontology, Role, Worker


CURATOR_AGENT = "pathforward-curator"
PLANNER_AGENT = "pathforward-planner"
CRITIC_AGENT = "pathforward-critic"
INSIGHTS_AGENT = "pathforward-insights"


class FabricProgramInsightsAgent(ProgramInsightsAgent):
    """Adapter for `run_multiagent`, which calls `analyze(...)`.

    The core `ProgramInsightsAgent` keeps floor and Fabric modes separate (`analyze` vs.
    `analyze_via_fabric`). The demo/export live path opts into Fabric by adapting `analyze` to the
    Fabric method, without changing the orchestrator or the trust path.
    """

    def analyze(self, worker: Worker, role: Role, onto: Ontology):  # type: ignore[override]
        return self.analyze_via_fabric(worker, role, onto)


@dataclass
class DemoAgentSet:
    curator: Curator
    generator: Generator
    gate: EvidenceGate
    planner: Planner
    critic: Critic
    insights: ProgramInsightsAgent
    analyst: LocalAnalyst
    provenance: dict
    _closables: list = field(default_factory=list)

    def close(self) -> None:
        for c in self._closables:
            try:
                c.close()
            except Exception:  # noqa: BLE001 - demo cleanup should not hide the run result
                pass


def _live_clients(s: Settings) -> Iterable:
    curator_client = ReasoningFoundryClient(endpoint=s.foundry_project_endpoint,
                                            agent_name=CURATOR_AGENT, model=s.model_deployment)
    planner_client = ReasoningFoundryClient(endpoint=s.foundry_project_endpoint,
                                            agent_name=PLANNER_AGENT, model=s.model_deployment)
    critic_client = ReasoningFoundryClient(endpoint=s.foundry_project_endpoint,
                                           agent_name=CRITIC_AGENT, model=s.model_deployment)
    generator_client = FoundryLLMClient(endpoint=s.foundry_project_endpoint, model=s.model_deployment,
                                        index_name=s.search_index)
    return curator_client, planner_client, critic_client, generator_client


def build_demo_agents(*, live: bool, settings: Settings | None = None,
                      prefer_fabric: bool = True) -> DemoAgentSet:
    """Build the demo/export agent stack.

    `live=True` requires Azure readiness. If `prefer_fabric` and `FABRIC_CONNECTION_NAME` are set, the
    Program Insights agent uses the live Fabric data-agent tier; otherwise it uses the live tool-less
    derivation-floor narrator.
    """
    gate = EvidenceGate(LocalNumericChecker())
    analyst = LocalAnalyst()

    if not live:
        fake = FakeLLMClient()
        return DemoAgentSet(
            curator=Curator(fake),
            generator=Generator(fake),
            gate=gate,
            planner=Planner(fake, LocalNumericChecker()),
            critic=Critic(fake),
            insights=ProgramInsightsAgent(fake),
            analyst=analyst,
            provenance={
                "mode": "offline-rehearsal",
                "generator": "FakeLLMClient",
                "curator": "FakeLLMClient",
                "critic": "FakeLLMClient",
                "planner": "FakeLLMClient",
                "insights": "derivation-floor",
                "fabric": "not-used",
            },
        )

    if settings is None or not settings.azure_ready:
        raise RuntimeError("live demo/export requires AZURE_AI_PROJECT_ENDPOINT and AZURE_SEARCH_ENDPOINT")

    curator_client, planner_client, critic_client, generator_client = _live_clients(settings)
    closables = [curator_client, planner_client, critic_client, generator_client]

    if prefer_fabric and settings.fabric_connection_name:
        insights_client = FabricInsightsClient(endpoint=settings.foundry_project_endpoint,
                                               connection_name=settings.fabric_connection_name,
                                               model=settings.model_deployment)
        insights: ProgramInsightsAgent = FabricProgramInsightsAgent(insights_client)
        closables.append(insights_client)
        insights_source = "fabric-live"
        fabric_state = "configured"
    else:
        insights_client = ReasoningFoundryClient(endpoint=settings.foundry_project_endpoint,
                                                 agent_name=INSIGHTS_AGENT,
                                                 model=settings.model_deployment)
        insights = ProgramInsightsAgent(insights_client)
        closables.append(insights_client)
        insights_source = "derivation-floor"
        fabric_state = "not-configured"

    return DemoAgentSet(
        curator=Curator(curator_client),
        generator=Generator(generator_client),
        gate=gate,
        planner=Planner(planner_client, LocalNumericChecker()),
        critic=Critic(critic_client),
        insights=insights,
        analyst=analyst,
        provenance={
            "mode": "live-foundry",
            "generator": "FoundryLLMClient+AzureAISearchTool",
            "curator": "ReasoningFoundryClient",
            "critic": "ReasoningFoundryClient",
            "planner": "ReasoningFoundryClient",
            "insights": insights_source,
            "fabric": fabric_state,
        },
        _closables=closables,
    )
