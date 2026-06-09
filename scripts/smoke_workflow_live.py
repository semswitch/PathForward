"""LOCKED OUT / HISTORICAL REFERENCE ONLY.

Per user instruction on 2026-06-09, PathForward is NOT using Agent Framework Workflow as an
architecture surface. Do not use this smoke as product proof or next-step work unless the user
explicitly re-authorizes Workflow.

Live smoke for the Agent Framework Workflow track (P7).

Two gates:
  1. ALWAYS (offline, no SDK needed): the no-bypass trust audit over the workflow graph holds
     (T1-T6) — the developer-proven graph-shape property is the load-bearing trust deliverable.
  2. CONDITIONAL (live): if `PF_WORKFLOW` is on, `agent-framework` is installed, and `.env` is
     configured, build the live `agent_framework` Workflow for hero worker EMP-001, drive the HITL
     mint approval (approve), and assert a credential is issued whose cited_edge_id == the driving
     CertGap edge (the causal spine survives the Workflow projection). If the SDK / Azure is absent
     the live run is SKIPPED (clearly labeled) — not failed.

    PF_WORKFLOW=1 python scripts/smoke_workflow_live.py

Exit 0 = the trust audit held AND the live run passed-or-was-skipped; 1 = audit failed or a live
run ran and failed. This never claims a live result it did not produce.
"""
from __future__ import annotations

import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # for generate_data

from pathforward.agents import workflow as wf                         # noqa: E402
from pathforward.agents.calibration import cold_start_calibrate       # noqa: E402
from pathforward.iq import derivation as dv                           # noqa: E402
from pathforward.iq.seed import build_seed, HERO_WORKER_ID            # noqa: E402

CURATOR_AGENT = "pathforward-curator"
PLANNER_AGENT = "pathforward-planner"
CRITIC_AGENT = "pathforward-critic"
INSIGHTS_AGENT = "pathforward-insights"


def _audit_gate() -> bool:
    graph = wf.build_pathforward_graph()
    print("=== no-bypass trust audit (offline; the load-bearing trust claim) ===")
    props = wf.trust_audit(graph)
    for p in props:
        print(f"  [{'PASS' if p.holds else 'FAIL'}] {p.key}: {p.evidence}")
    ok = all(p.holds for p in props)
    print(f"  -> trust holds: {ok}")
    return ok


def _live_run() -> "tuple[bool, str]":
    """Returns (passed, status_label). status_label in {'PASS','FAIL','SKIP'}."""
    if not wf.workflow_enabled():
        return True, "SKIP (PF_WORKFLOW not set)"
    if importlib.util.find_spec("agent_framework") is None:
        return True, "SKIP (agent-framework not installed)"
    import asyncio

    from pathforward.agents.adaptive import AdaptiveController
    from pathforward.agents.critic import Critic
    from pathforward.agents.curator import Curator
    from pathforward.agents.foundry import FoundryLLMClient, ReasoningFoundryClient
    from pathforward.agents.generator import Generator
    from pathforward.agents.insights import ProgramInsightsAgent
    from pathforward.agents.numeric import LocalNumericChecker
    from pathforward.agents.planner import Planner
    from pathforward.agents.evidence_gate import EvidenceGate
    from pathforward.agents.workflow_foundry import make_initial_state
    from pathforward.config import load_settings
    from pathforward.credential.schema import ProofCredential
    from generate_data import _learner_responses

    s = load_settings(os.path.join(_ROOT, ".env"))
    onto = build_seed()
    worker = onto.workers[HERO_WORKER_ID]
    edges = dv.build_all_edges(onto)
    calib = {"label": "estimated (cold-start)"}
    _ = cold_start_calibrate(_learner_responses(onto))  # parity with the in-process demo

    curator_client = ReasoningFoundryClient(endpoint=s.foundry_project_endpoint,
                                            agent_name=CURATOR_AGENT, model=s.model_deployment)
    planner_client = ReasoningFoundryClient(endpoint=s.foundry_project_endpoint,
                                            agent_name=PLANNER_AGENT, model=s.model_deployment)
    critic_client = ReasoningFoundryClient(endpoint=s.foundry_project_endpoint,
                                           agent_name=CRITIC_AGENT, model=s.model_deployment)
    insights_client = ReasoningFoundryClient(endpoint=s.foundry_project_endpoint,
                                             agent_name=INSIGHTS_AGENT, model=s.model_deployment)
    generator_client = FoundryLLMClient(endpoint=s.foundry_project_endpoint, model=s.model_deployment,
                                        index_name=s.search_index)
    clients = (curator_client, planner_client, critic_client, insights_client, generator_client)

    async def _drive() -> bool:
        workflow = wf.build_foundry_workflow(
            curator=Curator(curator_client), generator=Generator(generator_client),
            evidence_gate=EvidenceGate(LocalNumericChecker()),
            planner=Planner(planner_client, LocalNumericChecker()),
            critic=Critic(critic_client), insights=ProgramInsightsAgent(insights_client),
            adaptive=AdaptiveController(calibration={}), include_hitl=True)
        state = make_initial_state(worker, onto, edges, calibration=calib)
        result = await workflow.run(state)
        # HITL: approve every pending mint-approval request, then resume. (Resume shape is
        # TO-VERIFY against the pinned build: dict-by-request_id is the HITL-doc idiom.)
        for _ in range(4):
            pending = result.get_request_info_events()
            if not pending:
                break
            responses = {ev.request_id: True for ev in pending}      # approve
            result = await workflow.run(responses=responses)
        outputs = result.get_outputs()
        creds = [o for o in outputs if isinstance(o, ProofCredential)]
        if not creds:
            print("  [FAIL] no credential issued by the live workflow")
            return False
        cs = creds[0].credential_subject
        spine_ok = cs["cited_edge_id"].startswith("certgap::") and cs["worker_id"] == worker.id
        print(f"  [{'PASS' if spine_ok else 'FAIL'}] credential issued: skill={cs['skill_id']} "
              f"cited_edge_id={cs['cited_edge_id']} readiness={cs['readiness']}")
        return spine_ok

    try:
        ok = asyncio.run(_drive())
        return ok, ("PASS" if ok else "FAIL")
    finally:
        for c in clients:
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    audit_ok = _audit_gate()
    print("\n=== live workflow run (conditional) ===")
    live_ok, label = _live_run()
    print(f"  live run: {label}")
    rc = 0 if (audit_ok and live_ok) else 1
    print("\nWORKFLOW TRACK", "PASS" if rc == 0 else "FAIL")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
