"""Trace the full PathForward agentic flow.

This is the demo/proof artifact for the "agents reason, code notarizes" architecture. It traces:

  Versioned Foundry agents -> Orchestrator route -> Curator -> Generator/Critic/Evidence Gate with
  adaptive + reflection -> Planner -> Program Insights/Fabric -> mint, plus an explicit ABSTAIN.

This script runs the durable Foundry specialist agents. Their Skills are baked into the Foundry agent
versions by `scripts/provision_foundry_specialist_agents.py`; this script does not inject Skill text
at inference time.

    python scripts/trace_full_flow.py
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.agents.adaptive import AdaptiveController  # noqa: E402
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
from pathforward.agents.versioned import versioned_agent_evidence  # noqa: E402
from pathforward.config import load_settings  # noqa: E402
from pathforward.credential.mint import mint  # noqa: E402
from pathforward.iq import derivation as dv  # noqa: E402
from pathforward.iq import traversal  # noqa: E402
from pathforward.iq.seed import HERO_WORKER_ID, build_seed  # noqa: E402
from pathforward.obs import tracing  # noqa: E402

class FabricProgramInsightsAgent(ProgramInsightsAgent):
    """Script-only adapter: make the normal insights call use the Fabric-live tier."""

    def analyze(self, worker, role, onto):  # noqa: ANN001
        return self.analyze_via_fabric(worker, role, onto)


def _clients(settings):
    from pathforward.agents.foundry import (
        FabricDataAgentClient,
        PersistentFabricInsightsClient,
        PersistentFoundryLLMClient,
        PersistentReasoningFoundryClient,
    )
    from pathforward.agents.versioned import VERSIONED_AGENT_BY_ROLE

    if not settings.azure_ready:
        raise RuntimeError("live trace requires AZURE_AI_PROJECT_ENDPOINT and AZURE_SEARCH_ENDPOINT")

    orch = PersistentReasoningFoundryClient(
        settings.foundry_project_endpoint,
        VERSIONED_AGENT_BY_ROLE["orchestrator"].agent_name)
    curator = PersistentReasoningFoundryClient(
        settings.foundry_project_endpoint,
        VERSIONED_AGENT_BY_ROLE["curator"].agent_name)
    generator = PersistentFoundryLLMClient(
        settings.foundry_project_endpoint,
        VERSIONED_AGENT_BY_ROLE["generator"].agent_name)
    critic = PersistentReasoningFoundryClient(
        settings.foundry_project_endpoint,
        VERSIONED_AGENT_BY_ROLE["critic"].agent_name)
    planner = PersistentReasoningFoundryClient(
        settings.foundry_project_endpoint,
        VERSIONED_AGENT_BY_ROLE["planner"].agent_name)
    if settings.fabric_data_agent_openai_base:
        insights_client = FabricDataAgentClient(
            settings.fabric_data_agent_openai_base,
            os.getenv("PATHFORWARD_FABRIC_SP_TENANT_ID", ""),
            os.getenv("PATHFORWARD_FABRIC_SP_CLIENT_ID", ""),
            os.getenv("PATHFORWARD_FABRIC_SP_CLIENT_SECRET", ""),
        )
    else:
        insights_client = PersistentFabricInsightsClient(
            settings.foundry_project_endpoint,
            VERSIONED_AGENT_BY_ROLE["insights"].agent_name)
    insights_agent = FabricProgramInsightsAgent(insights_client)

    live_clients = [orch, curator, generator, critic, planner, insights_client]
    return {
        "orchestrator": orch,
        "curator": curator,
        "generator": generator,
        "critic": critic,
        "planner": planner,
        "insights_client": insights_client,
        "insights_cls": insights_agent.__class__,
        "close": lambda: [c.close() for c in live_clients],
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass

    ap = argparse.ArgumentParser(description="Trace the full PathForward agentic flow.")
    ap.add_argument("--skip-abstain", action="store_true",
                    help="skip the explicit fail-closed ABSTAIN proof segment")
    args = ap.parse_args()

    settings = load_settings(os.path.join(_ROOT, ".env"))
    active = tracing.configure_tracing(
        console=True, azure_connection_string=(settings.azure_monitor_connection_string or None))
    print(f"tracing active={active}  azure_export={'on' if settings.azure_monitor_connection_string else 'off'}")
    print("mode=live  fabric=on")

    onto = build_seed()
    edges = dv.build_all_edges(onto)
    worker = onto.workers[HERO_WORKER_ID]
    role = onto.roles[worker.target_role_id]
    clients = _clients(settings)
    agent_evidence = versioned_agent_evidence()

    # Deterministic cold-start signal for the hero path: S01 selects stretch, so adaptive is visible.
    adaptive = AdaptiveController(calibration={"item-S01": {"difficulty": 0.9}})
    gate = EvidenceGate(LocalNumericChecker())

    rc = 0
    try:
        with tracing.span("pathforward.full_flow",
                          **{"pf.worker": worker.id, "pf.skill_source": agent_evidence["source"],
                             "pf.fabric": True}) as root:
            root.event("foundry_agents.versioned", **{
                "pf.source": agent_evidence["source"],
                "pf.count": len(agent_evidence["agents"]),
            })
            result = run_orchestrated_multiagent(
                worker, onto, edges,
                Orchestrator(clients["orchestrator"]),
                Curator(clients["curator"]),
                Generator(clients["generator"]),
                gate,
                Planner(clients["planner"], LocalNumericChecker()),
                critic=Critic(clients["critic"]),
                adaptive=adaptive,
                insights=clients["insights_cls"](clients["insights_client"]),
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
                    driving, skill, (),
                    Generator(clients["generator"]),
                    gate,
                    critic=Critic(clients["critic"]),
                    adaptive=adaptive)
                abstain_root.set(**{"pf.status": abstain.status, "pf.attempts": abstain.attempts})
                print(f"abstain proof status={abstain.status} attempts={abstain.attempts}")

        insights_source = result.insights.source if result.insights else "(none)"
        print("\ntrace storyboard")
        print(f"- agent source: {agent_evidence['source']}")
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
