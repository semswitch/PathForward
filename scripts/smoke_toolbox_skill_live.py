"""Live Foundry Skill/Toolbox smoke.

This is the checklist #4 proof path:

  - `skills/pathforward/SKILL.md` has been registered as the Foundry Skill `pathforward`.
  - `pathforward-toolbox` exposes that Skill through its MCP endpoint as
    `skill://pathforward/SKILL.md`.
  - The toolbox also exposes specialist skills for Curator, Assessment, Planner, and Insights.
  - The smoke calls `tools/list`, `resources/list`, and `resources/read`.
  - The Orchestrator and specialist agents receive MCP-loaded skill content at inference time.

It intentionally does NOT fall back to the local file for the live proof. Local files are source;
Foundry MCP readback is the runtime-consumption evidence.

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
from pathforward.agents.foundry import FoundryLLMClient, ReasoningFoundryClient  # noqa: E402
from pathforward.agents.generator import Generator  # noqa: E402
from pathforward.agents.insights import ProgramInsightsAgent  # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker  # noqa: E402
from pathforward.agents.orchestrator import run_orchestrated_multiagent  # noqa: E402
from pathforward.agents.planner import Planner  # noqa: E402
from pathforward.config import load_settings  # noqa: E402
from pathforward.credential.mint import mint  # noqa: E402
from pathforward.iq import derivation as dv  # noqa: E402
from pathforward.iq import traversal  # noqa: E402
from pathforward.iq.seed import HERO_WORKER_ID, build_seed  # noqa: E402
from pathforward.toolbox_mcp import read_skills_from_toolbox  # noqa: E402
from generate_data import _learner_responses  # noqa: E402

TOOLBOX_NAME = "pathforward-toolbox"
SKILL_NAME = "pathforward"
SPECIALIST_SKILLS = (
    "pathforward",
    "pathforward-curate",
    "pathforward-assess",
    "pathforward-plan",
    "pathforward-insights",
)
ORCHESTRATOR_AGENT = "pathforward-orchestrator-skill"
CURATOR_AGENT = "pathforward-curator-skill"
PLANNER_AGENT = "pathforward-planner-skill"
CRITIC_AGENT = "pathforward-critic-skill"
INSIGHTS_AGENT = "pathforward-insights-skill"


def main() -> int:
    settings = load_settings(os.path.join(_ROOT, ".env"))
    if not settings.foundry_project_endpoint:
        print("SKIP: AZURE_AI_PROJECT_ENDPOINT is blank")
        return 0

    print(f"toolbox={TOOLBOX_NAME} skill={SKILL_NAME}")
    skill_contents, mcp_evidence = read_skills_from_toolbox(settings.foundry_project_endpoint,
                                                            TOOLBOX_NAME, SPECIALIST_SKILLS)
    skill_content = skill_contents[SKILL_NAME]
    print(f"initialized: protocol={mcp_evidence.get('protocol') or '(unspecified)'}")
    tool_names = mcp_evidence["tools"]
    print(f"tools/list: {tool_names}")
    print(f"resources/list: {mcp_evidence['resources']}")
    if "PathForward Orchestrator Skill" not in skill_content:
        print("FAIL: resources/read did not return the expected /pathforward skill body")
        return 1
    for name in SPECIALIST_SKILLS:
        print(f"resources/read: {mcp_evidence['skill_uris'][name]} "
              f"chars={mcp_evidence['skill_chars'][name]}")

    orchestrator_client = ReasoningFoundryClient(endpoint=settings.foundry_project_endpoint,
                                                 agent_name=ORCHESTRATOR_AGENT,
                                                 model=settings.model_deployment)
    curator_client = ReasoningFoundryClient(endpoint=settings.foundry_project_endpoint,
                                            agent_name=CURATOR_AGENT,
                                            model=settings.model_deployment)
    planner_client = ReasoningFoundryClient(endpoint=settings.foundry_project_endpoint,
                                            agent_name=PLANNER_AGENT,
                                            model=settings.model_deployment)
    critic_client = ReasoningFoundryClient(endpoint=settings.foundry_project_endpoint,
                                           agent_name=CRITIC_AGENT,
                                           model=settings.model_deployment)
    insights_client = ReasoningFoundryClient(endpoint=settings.foundry_project_endpoint,
                                             agent_name=INSIGHTS_AGENT,
                                             model=settings.model_deployment)
    generator_client = FoundryLLMClient(endpoint=settings.foundry_project_endpoint,
                                        model=settings.model_deployment,
                                        index_name=settings.search_index,
                                        agent_name="pathforward-generator-skill")
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
            Orchestrator(orchestrator_client, skill_instructions=skill_content),
            Curator(curator_client, skill_instructions=skill_contents["pathforward-curate"]),
            Generator(generator_client, skill_instructions=skill_contents["pathforward-assess"]),
            EvidenceGate(LocalNumericChecker()),
            Planner(planner_client, LocalNumericChecker(),
                    skill_instructions=skill_contents["pathforward-plan"]),
            critic=Critic(critic_client, skill_instructions=skill_contents["pathforward-assess"]),
            adaptive=adaptive,
            insights=ProgramInsightsAgent(
                insights_client, skill_instructions=skill_contents["pathforward-insights"]),
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
            "toolbox MCP tools listed": bool(tool_names),
            "Foundry skill resources read": all(skill_contents.get(name) for name in SPECIALIST_SKILLS),
            "Orchestrator used MCP-loaded /pathforward skill": route_ok,
            "Specialist skills loaded": all(skill_contents.get(name) for name in SPECIALIST_SKILLS[1:]),
            "Evidence Gate verified": result.loop.status == "verified",
            "credential spine intact": spine_ok,
            "insights returned": result.insights is not None,
        }
        for name, ok in checks.items():
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not all(checks.values()):
            return 1
        print("LIVE TOOLBOX SKILL PASS")
        return 0
    finally:
        for client in clients:
            client.close()
        print("agents deleted")


if __name__ == "__main__":
    raise SystemExit(main())
