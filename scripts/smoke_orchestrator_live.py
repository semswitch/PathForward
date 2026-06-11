"""Live Orchestrator smoke for checklist #1.

This proves the Orchestrator/Conductor is a real Foundry-backed reasoning agent:

  - Orchestrator runs on a TOOL-LESS Foundry reasoning agent (`pathforward-orchestrator`).
  - Curator / Planner / Critic / Insights run on tool-less Foundry reasoning agents.
  - Generator runs on the search-grounded FoundryLLMClient.
  - Code validates the Orchestrator's route before execution.
  - Evidence Gate / LocalNumericChecker / mint remain deterministic code.

It also runs a local negative validation check to show that an invalid Orchestrator route is rejected
before the assessment loop or mint path can run.

    python scripts/smoke_orchestrator_live.py

Exit 0 = the live Orchestrator route ran, the code validator accepted the bounded route, the loop
verified a grounded item, and the minted credential's causal spine is intact.
"""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # for generate_data

from pathforward.agents.adaptive import AdaptiveController            # noqa: E402
from pathforward.agents.calibration import cold_start_calibrate       # noqa: E402
from pathforward.agents.client import LLMResponse                     # noqa: E402
from pathforward.agents.conductor import Orchestrator, OrchestratorPlanError  # noqa: E402
from pathforward.agents.critic import Critic                          # noqa: E402
from pathforward.agents.curator import Curator                        # noqa: E402
from pathforward.agents.evidence_gate import EvidenceGate             # noqa: E402
from pathforward.agents.foundry import FoundryLLMClient, ReasoningFoundryClient  # noqa: E402
from pathforward.agents.generator import Generator                    # noqa: E402
from pathforward.agents.insights import ProgramInsightsAgent          # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker            # noqa: E402
from pathforward.agents.orchestrator import run_orchestrated_multiagent  # noqa: E402
from pathforward.agents.planner import Planner                        # noqa: E402
from pathforward.config import load_settings                          # noqa: E402
from pathforward.credential.mint import mint                          # noqa: E402
from pathforward.iq import derivation as dv                           # noqa: E402
from pathforward.iq import traversal                                  # noqa: E402
from pathforward.iq.seed import HERO_WORKER_ID, build_seed            # noqa: E402
from generate_data import _learner_responses                          # noqa: E402

ORCHESTRATOR_AGENT = "pathforward-orchestrator"
CURATOR_AGENT = "pathforward-curator"
PLANNER_AGENT = "pathforward-planner"
CRITIC_AGENT = "pathforward-critic"
INSIGHTS_AGENT = "pathforward-insights"


class _InvalidRouteClient:
    """Local negative stand-in: proposes an invalid target so code validation must reject it."""

    def respond(self, instructions: str, input: str, *, previous_response_id=None, schema=None):
        parsed = {
            "steps": [
                {"action": "curate", "rationale": "start with gaps"},
                {"action": "assess", "target_skill_id": "S99",
                 "rationale": "invalid non-admissible skill"},
            ],
            "rationale": "malicious invalid route",
        }
        return LLMResponse("invalid_route", json.dumps(parsed), parsed, previous_response_id)


def _negative_validation_probe(worker, role, onto) -> bool:
    try:
        Orchestrator(_InvalidRouteClient()).plan(worker, role, onto)
    except OrchestratorPlanError as exc:
        print(f"  [PASS] invalid route rejected before execution: {exc}")
        return True
    print("  [FAIL] invalid route was accepted")
    return False


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    settings = load_settings(os.path.join(_ROOT, ".env"))
    if not settings.azure_ready:
        print("SKIP: live Orchestrator smoke requires AZURE_AI_PROJECT_ENDPOINT and AZURE_SEARCH_ENDPOINT")
        return 0

    onto = build_seed()
    worker = onto.workers[HERO_WORKER_ID]
    role = onto.roles[worker.target_role_id]
    edges = dv.build_all_edges(onto)
    adaptive = AdaptiveController(calibration=cold_start_calibrate(_learner_responses(onto)))

    print(f"worker={worker.id} target={role.name} model={settings.model_deployment}")
    print("\n[VALIDATOR NEGATIVE PROBE]")
    negative_ok = _negative_validation_probe(worker, role, onto)

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
                                        index_name=settings.search_index)
    clients = (orchestrator_client, curator_client, planner_client, critic_client,
               insights_client, generator_client)

    rc = 1
    try:
        result = run_orchestrated_multiagent(
            worker, onto, edges,
            Orchestrator(orchestrator_client),
            Curator(curator_client),
            Generator(generator_client),
            EvidenceGate(LocalNumericChecker()),
            Planner(planner_client, LocalNumericChecker()),
            critic=Critic(critic_client),
            adaptive=adaptive,
            insights=ProgramInsightsAgent(insights_client),
        )
        orch = result.orchestrator or {}
        route = orch.get("route", {})
        steps = route.get("steps", [])
        selected = orch.get("selected_target_skill_id", "")

        print("\n[ORCHESTRATOR]")
        print(f"  live agent: {ORCHESTRATOR_AGENT}")
        print(f"  selected target: {selected or '(none)'}")
        for i, step in enumerate(steps, start=1):
            print(f"   {i}. {step.get('action')} target={step.get('target_skill_id') or '-'} "
                  f"reason={step.get('rationale') or ''}")

        admissible = [s for s in dv.cert_gap_skill_ids(worker, role) if traversal.is_assessable(s, onto)]
        route_ok = bool(selected) and selected in admissible
        print(f"  route target admissible: {route_ok}")

        loop = result.loop
        print("\n[LOOP]")
        print(f"  status={loop.status.upper()} attempts={loop.attempts} driving_edge={loop.driving_edge_id}")
        for t in loop.transcript:
            item = t["item"]
            verdict = t["verdict"]
            critic = t.get("critic")
            print(f"   attempt {t['attempt']}: gate={'PASS' if verdict.passed else 'REJECT'} "
                  f"critic={critic.recommendation if critic else '-'} "
                  f"retrieved={len(item.retrieved_ref_ids)} cited={list(item.cited_ref_ids)}")

        spine_ok = False
        if loop.status == "verified":
            cred = mint(worker, role, loop.driving_edge_id, loop.targeted_skill_id, loop)
            cs = cred.credential_subject
            spine_ok = cs["cited_edge_id"] == loop.driving_edge_id
            print("\n[MINT]")
            print(f"  worker={cs['worker_id']} skill={cs['skill_id']} "
                  f"readiness={cs['readiness']} cited_edge_id={cs['cited_edge_id']}")
            print(f"  spine intact: {spine_ok}")

        checks = {
            "invalid route rejected by code": negative_ok,
            "orchestrator chose admissible target": route_ok,
            "loop verified": loop.status == "verified",
            "credential spine intact": spine_ok,
            "planner produced capacity-safe plan": result.plan.capacity_respected,
            "insights reconcile to derivation": bool(result.insights) and abs(
                result.insights.worker_comparison["worker_readiness"] -
                dv.readiness_score(worker, role)) < 1e-9,
        }
        print("\n=== checks ===")
        for name, ok in checks.items():
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        rc = 0 if all(checks.values()) else 1
        print("\nLIVE ORCHESTRATOR", "PASS" if rc == 0 else "FAIL")
    finally:
        for c in clients:
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
        print("agents deleted")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
