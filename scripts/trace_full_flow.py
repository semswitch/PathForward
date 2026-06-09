"""Trace the full PathForward agentic flow.

This is the demo/proof artifact for the "agents reason, code notarizes" architecture. It traces:

  Foundry Skill load -> Orchestrator route -> Curator -> Generator/Critic/Evidence Gate with
  adaptive + reflection -> Planner -> Program Insights/Fabric -> mint, plus an explicit ABSTAIN.

Offline default uses deterministic fakes and the local skill file. `--live` loads the `/pathforward`
Skill through the Foundry Toolbox MCP endpoint and runs the live Foundry prompt-agent clients.

    python scripts/trace_full_flow.py
    python scripts/trace_full_flow.py --live
    python scripts/trace_full_flow.py --live --fabric
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.agents.adaptive import AdaptiveController  # noqa: E402
from pathforward.agents.client import FakeLLMClient  # noqa: E402
from pathforward.agents.conductor import Orchestrator  # noqa: E402
from pathforward.agents.critic import Critic  # noqa: E402
from pathforward.agents.curator import Curator  # noqa: E402
from pathforward.agents.evidence_gate import EvidenceGate  # noqa: E402
from pathforward.agents.generator import Generator  # noqa: E402
from pathforward.agents.insights import ProgramInsightsAgent  # noqa: E402
from pathforward.agents.loop import run_assessment_loop  # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker  # noqa: E402
from pathforward.agents.orchestrator import run_orchestrated_multiagent  # noqa: E402
from pathforward.agents.planner import Planner  # noqa: E402
from pathforward.config import load_settings  # noqa: E402
from pathforward.credential.mint import mint  # noqa: E402
from pathforward.iq import derivation as dv  # noqa: E402
from pathforward.iq import traversal  # noqa: E402
from pathforward.iq.seed import HERO_WORKER_ID, build_seed  # noqa: E402
from pathforward.obs import tracing  # noqa: E402
from pathforward.skills import read_skill_file  # noqa: E402

TOOLBOX_NAME = "pathforward-toolbox"
SKILL_NAME = "pathforward"


class FabricProgramInsightsAgent(ProgramInsightsAgent):
    """Script-only adapter: make the normal insights call use the Fabric-live tier."""

    def analyze(self, worker, role, onto):  # noqa: ANN001
        return self.analyze_via_fabric(worker, role, onto)


def _load_skill(settings, live: bool) -> tuple[str, str, dict]:
    if live:
        from pathforward.toolbox_mcp import read_skill_from_toolbox

        if not settings.foundry_project_endpoint:
            raise RuntimeError("live skill load requires AZURE_AI_PROJECT_ENDPOINT")
        body, evidence = read_skill_from_toolbox(settings.foundry_project_endpoint,
                                                TOOLBOX_NAME, SKILL_NAME)
        return body, "foundry-toolbox-mcp", evidence

    skill = read_skill_file(os.path.join(_ROOT, "skills", "pathforward", "SKILL.md"))
    return skill.instructions, "local-skill-file", {
        "skill_uri": "skills/pathforward/SKILL.md",
        "skill_chars": len(skill.instructions),
        "tools": [],
    }


def _clients(settings, live: bool, fabric: bool):
    if not live:
        fake = FakeLLMClient()
        insights = ProgramInsightsAgent(fake)
        return {
            "orchestrator": fake,
            "curator": fake,
            "generator": fake,
            "critic": fake,
            "planner": fake,
            "insights_agent": insights,
            "close": lambda: None,
        }

    from pathforward.agents.foundry import (
        FabricInsightsClient,
        FoundryLLMClient,
        ReasoningFoundryClient,
    )

    if not settings.azure_ready:
        raise RuntimeError("live trace requires AZURE_AI_PROJECT_ENDPOINT and AZURE_SEARCH_ENDPOINT")

    orch = ReasoningFoundryClient(settings.foundry_project_endpoint,
                                  agent_name="pathforward-orchestrator-trace",
                                  model=settings.model_deployment)
    curator = ReasoningFoundryClient(settings.foundry_project_endpoint,
                                     agent_name="pathforward-curator-trace",
                                     model=settings.model_deployment)
    generator = FoundryLLMClient(settings.foundry_project_endpoint,
                                 model=settings.model_deployment,
                                 index_name=settings.search_index,
                                 agent_name="pathforward-generator-trace")
    critic = ReasoningFoundryClient(settings.foundry_project_endpoint,
                                    agent_name="pathforward-critic-trace",
                                    model=settings.model_deployment)
    planner = ReasoningFoundryClient(settings.foundry_project_endpoint,
                                     agent_name="pathforward-planner-trace",
                                     model=settings.model_deployment)
    if fabric:
        if not settings.fabric_connection_name:
            raise RuntimeError("--fabric requires FABRIC_CONNECTION_NAME")
        insights_client = FabricInsightsClient(settings.foundry_project_endpoint,
                                               connection_name=settings.fabric_connection_name,
                                               agent_name="pathforward-insights-fabric-trace",
                                               model=settings.model_deployment)
        insights_agent = FabricProgramInsightsAgent(insights_client)
    else:
        insights_client = ReasoningFoundryClient(settings.foundry_project_endpoint,
                                                 agent_name="pathforward-insights-trace",
                                                 model=settings.model_deployment)
        insights_agent = ProgramInsightsAgent(insights_client)

    live_clients = [orch, curator, generator, critic, planner, insights_client]
    return {
        "orchestrator": orch,
        "curator": curator,
        "generator": generator,
        "critic": critic,
        "planner": planner,
        "insights_agent": insights_agent,
        "close": lambda: [c.close() for c in live_clients],
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass

    ap = argparse.ArgumentParser(description="Trace the full PathForward agentic flow.")
    ap.add_argument("--live", action="store_true", help="run live Foundry prompt agents")
    ap.add_argument("--fabric", action="store_true", help="use Fabric-live Program Insights")
    ap.add_argument("--skip-abstain", action="store_true",
                    help="skip the explicit fail-closed ABSTAIN proof segment")
    args = ap.parse_args()

    settings = load_settings(os.path.join(_ROOT, ".env"))
    active = tracing.configure_tracing(
        console=True, azure_connection_string=(settings.azure_monitor_connection_string or None))
    print(f"tracing active={active}  azure_export={'on' if settings.azure_monitor_connection_string else 'off'}")
    print(f"mode={'live' if args.live else 'offline'}  fabric={'on' if args.fabric else 'off'}")

    onto = build_seed()
    edges = dv.build_all_edges(onto)
    worker = onto.workers[HERO_WORKER_ID]
    role = onto.roles[worker.target_role_id]
    skill_body, skill_source, skill_evidence = _load_skill(settings, args.live)
    clients = _clients(settings, args.live, args.fabric)

    # Deterministic cold-start signal for the hero path: S01 selects stretch, so adaptive is visible.
    adaptive = AdaptiveController(calibration={"item-S01": {"difficulty": 0.9}})
    gate = EvidenceGate(LocalNumericChecker())

    rc = 0
    try:
        with tracing.span("pathforward.full_flow",
                          **{"pf.worker": worker.id, "pf.skill_source": skill_source,
                             "pf.fabric": bool(args.fabric)}) as root:
            root.event("skill.loaded", **{
                "pf.source": skill_source,
                "pf.uri": str(skill_evidence.get("skill_uri", "")),
                "pf.chars": int(skill_evidence.get("skill_chars", 0) or 0),
            })
            result = run_orchestrated_multiagent(
                worker, onto, edges,
                Orchestrator(clients["orchestrator"], skill_instructions=skill_body),
                Curator(clients["curator"]),
                Generator(clients["generator"]),
                gate,
                Planner(clients["planner"], LocalNumericChecker()),
                critic=Critic(clients["critic"]),
                adaptive=adaptive,
                insights=clients["insights_agent"],
            )
            root.set(**{"pf.status": result.loop.status,
                        "pf.attempts": result.loop.attempts,
                        "pf.insights_source": result.insights.source if result.insights else "(none)"})
            if result.loop.status == "verified":
                driving = next(e for e in traversal.cert_gap_edges(worker, onto, edges)
                               if e.id == result.loop.driving_edge_id)
                cred = mint(worker, role, driving.id, result.loop.targeted_skill_id, result.loop)
                print(f"minted cited_edge_id={cred.credential_subject['cited_edge_id']} "
                      f"readiness={cred.credential_subject['readiness']}")
            else:
                print("main flow abstained (fail-closed); no credential")

        if not args.skip_abstain:
            driving = traversal.cert_gap_edges(worker, onto, edges)[0]
            skill = onto.skills[driving.target_id]
            with tracing.span("pathforward.abstain_proof",
                              **{"pf.worker": worker.id, "pf.skill": skill.id}) as abstain_root:
                abstain = run_assessment_loop(
                    driving, skill, (), Generator(clients["generator"]), gate,
                    critic=Critic(clients["critic"]), adaptive=adaptive)
                abstain_root.set(**{"pf.status": abstain.status, "pf.attempts": abstain.attempts})
                print(f"abstain proof status={abstain.status} attempts={abstain.attempts}")

        insights_source = result.insights.source if result.insights else "(none)"
        print("\ntrace storyboard")
        print(f"- skill source: {skill_source}")
        print(f"- orchestrator target: {result.orchestrator.get('selected_target_skill_id') if result.orchestrator else '(none)'}")
        print("- adaptive band: stretch (cold-start estimated, selection-only)")
        print(f"- assessment: {result.loop.status} in {result.loop.attempts} attempt(s)")
        print(f"- insights source: {insights_source}")
        if not args.skip_abstain:
            print(f"- fail-closed proof: {abstain.status} after {abstain.attempts} attempts")
    finally:
        clients["close"]()
        tracing.flush()

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
