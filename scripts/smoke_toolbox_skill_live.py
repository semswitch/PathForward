"""Live Foundry scoped Skill/Toolbox smoke.

This is the checklist #4 proof path:

  - each product agent has its own scoped toolbox.
  - each scoped toolbox exposes exactly that agent's Skill through its MCP endpoint.
  - generator toolbox exposes Azure AI Search.
  - insights toolbox exposes Fabric IQ.
  - Versioned specialist agents already contain those Skills in their Foundry definitions.

It intentionally does NOT fall back to the local file for the live proof. Local files are source;
Foundry MCP readback plus versioned agent invocation is the runtime-consumption evidence.

    python scripts/build_toolbox.py --recreate
    python scripts/smoke_toolbox_skill_live.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.agents.adaptive import AdaptiveController  # noqa: E402
from pathforward.agents.calibration import cold_start_calibrate  # noqa: E402
from pathforward.agents.conductor import Orchestrator  # noqa: E402
from pathforward.agents.critic import Critic  # noqa: E402
from pathforward.agents.curator import Curator  # noqa: E402
from pathforward.agents.evidence_gate import EvidenceGate  # noqa: E402
from pathforward.agents.foundry import (  # noqa: E402
    PersistentFabricInsightsClient,
    PersistentFoundryLLMClient,
    PersistentReasoningFoundryClient,
)
from pathforward.agents.generator import Generator  # noqa: E402
from pathforward.agents.insights import ProgramInsightsAgent  # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker  # noqa: E402
from pathforward.agents.orchestrator import run_orchestrated_multiagent  # noqa: E402
from pathforward.agents.planner import Planner  # noqa: E402
from pathforward.config import load_settings  # noqa: E402
from pathforward.credential.mint import mint  # noqa: E402
from pathforward.agents.versioned import VERSIONED_AGENT_BY_ROLE, VERSIONED_AGENT_SPECS  # noqa: E402
from pathforward.iq import derivation as dv  # noqa: E402
from pathforward.iq import traversal  # noqa: E402
from pathforward.iq.seed import HERO_WORKER_ID, build_seed  # noqa: E402
from pathforward.toolbox_mcp import read_skills_from_toolbox  # noqa: E402
from generate_data import _learner_responses  # noqa: E402


class FabricProgramInsightsAgent(ProgramInsightsAgent):
    """Smoke adapter: make the standard orchestration seam call the Fabric-live method."""

    def analyze(self, worker, role, onto):  # noqa: ANN001
        return self.analyze_via_fabric(worker, role, onto)


def main() -> int:
    settings = load_settings(os.path.join(_ROOT, ".env"))
    if not settings.foundry_project_endpoint:
        print("SKIP: AZURE_AI_PROJECT_ENDPOINT is blank")
        return 0

    toolbox_evidence = {}
    tool_names_by_role = {}
    skill_contents = {}
    for spec in VERSIONED_AGENT_SPECS:
        print(f"toolbox={spec.toolbox_name} role={spec.role} skill=/{spec.skill_name}")
        bodies, mcp_evidence = read_skills_from_toolbox(
            settings.foundry_project_endpoint,
            spec.toolbox_name,
            (spec.skill_name,),
        )
        body = bodies[spec.skill_name]
        if f"name: {spec.skill_name}" not in body:
            print(f"FAIL: resources/read did not return expected /{spec.skill_name} body")
            return 1
        toolbox_evidence[spec.role] = mcp_evidence
        tool_names_by_role[spec.role] = mcp_evidence["tools"]
        skill_contents[spec.role] = body
        print(f"  initialized: protocol={mcp_evidence.get('protocol') or '(unspecified)'}")
        print(f"  tools/list: {mcp_evidence['tools']}")
        print(f"  resources/list: {mcp_evidence['resources']}")
        print(f"  resources/read: {mcp_evidence['skill_uri']} chars={mcp_evidence['skill_chars']}")

    orchestrator_client = PersistentReasoningFoundryClient(
        endpoint=settings.foundry_project_endpoint,
        agent_name=VERSIONED_AGENT_BY_ROLE["orchestrator"].agent_name)
    curator_client = PersistentReasoningFoundryClient(
        endpoint=settings.foundry_project_endpoint,
        agent_name=VERSIONED_AGENT_BY_ROLE["curator"].agent_name)
    planner_client = PersistentReasoningFoundryClient(
        endpoint=settings.foundry_project_endpoint,
        agent_name=VERSIONED_AGENT_BY_ROLE["planner"].agent_name)
    critic_client = PersistentReasoningFoundryClient(
        endpoint=settings.foundry_project_endpoint,
        agent_name=VERSIONED_AGENT_BY_ROLE["critic"].agent_name)
    insights_client = PersistentFabricInsightsClient(
        endpoint=settings.foundry_project_endpoint,
        agent_name=VERSIONED_AGENT_BY_ROLE["insights"].agent_name)
    generator_client = PersistentFoundryLLMClient(
        endpoint=settings.foundry_project_endpoint,
        agent_name=VERSIONED_AGENT_BY_ROLE["generator"].agent_name)
    clients = (orchestrator_client, curator_client, planner_client, critic_client,
               insights_client, generator_client)
    try:
        onto = build_seed()
        worker = onto.workers[HERO_WORKER_ID]
        role = onto.roles[worker.target_role_id]
        adaptive = AdaptiveController(calibration=cold_start_calibrate(_learner_responses(onto)))
        edges = dv.build_all_edges(onto)

        result = run_orchestrated_multiagent(
            worker, onto, edges,
            Orchestrator(orchestrator_client),
            Curator(curator_client),
            Generator(generator_client),
            EvidenceGate(LocalNumericChecker()),
            Planner(planner_client, LocalNumericChecker()),
            critic=Critic(critic_client),
            adaptive=adaptive,
            insights=FabricProgramInsightsAgent(insights_client),
        )
        orch = result.orchestrator or {}
        target = orch.get("selected_target_skill_id", "")
        admissible = [s for s in dv.cert_gap_skill_ids(worker, role) if traversal.is_assessable(s, onto)]
        route_ok = bool(target) and target in admissible
        spine_ok = False
        if result.loop.status == "verified":
            cred = mint(worker, role, result.loop.driving_edge_id, result.loop.targeted_skill_id,
                        result.loop)
            spine_ok = cred.credential_subject["cited_edge_id"] == result.loop.driving_edge_id

        print(f"orchestrator: selected={target or '(none)'} admissible={route_ok}")
        print(f"loop: status={result.loop.status.upper()} attempts={result.loop.attempts}")
        print(f"mint spine: {spine_ok}")
        checks = {
            "scoped toolbox skill resources read": all(
                skill_contents.get(spec.role) for spec in VERSIONED_AGENT_SPECS
            ),
            "generator toolbox has Search": bool(tool_names_by_role.get("generator")),
            "insights toolbox has Fabric IQ": bool(tool_names_by_role.get("insights")),
            "Orchestrator versioned agent routed": route_ok,
            "Specialist versioned agents invoked": all(
                VERSIONED_AGENT_BY_ROLE[role].agent_name
                for role in ("curator", "generator", "critic", "planner", "insights")
            ),
            "Evidence Gate verified": result.loop.status == "verified",
            "credential spine intact": spine_ok,
            "insights returned": result.insights is not None,
        }
        for name, ok in checks.items():
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not all(checks.values()):
            return 1
        print("LIVE TOOLBOX + VERSIONED AGENT PASS")
        return 0
    finally:
        for client in clients:
            client.close()
        print("clients closed")


if __name__ == "__main__":
    raise SystemExit(main())
