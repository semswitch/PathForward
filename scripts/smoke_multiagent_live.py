"""Live multi-agent smoke: the full Curator -> Generator/Evidence Gate loop -> Planner reasoning loop
on live Azure for the hero worker EMP-001.

  - Curator + Planner run on TOOL-LESS Foundry reasoning agents (ReasoningFoundryClient).
  - Generator runs on the search-grounded FoundryLLMClient (gpt-5.5 + Azure AI Search).
  - Evidence Gate stays deterministic (LocalNumericChecker).

Proves the multi-agent orchestrator works end to end on live Azure with the trust boundary intact:
  - the Curator's chosen skill is an ADMISSIBLE (derived, assessable) gap — the model cannot invent one,
  - the loop verifies a grounded item and mints a credential whose cited_edge_id == the driving edge,
  - the Planner's plan respects the worker's weekly capacity and uses real certification hours.

NOTE: unlike the offline demo (which pins S01 for determinism), the LIVE Curator may pick any
admissible gap — that is genuine reasoning — so this script does NOT assert S01.

    python scripts/smoke_multiagent_live.py

Exit 0 = the live three-agent loop ran, verified, minted with the spine intact, and produced a
capacity-respecting plan.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # for generate_data

from pathforward.agents.adaptive import AdaptiveController            # noqa: E402
from pathforward.agents.calibration import cold_start_calibrate       # noqa: E402
from pathforward.agents.critic import Critic                          # noqa: E402
from pathforward.agents.curator import Curator                        # noqa: E402
from pathforward.agents.foundry import FoundryLLMClient, ReasoningFoundryClient  # noqa: E402
from pathforward.agents.generator import Generator                    # noqa: E402
from pathforward.agents.insights import ProgramInsightsAgent          # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker            # noqa: E402
from pathforward.agents.orchestrator import run_multiagent            # noqa: E402
from pathforward.agents.planner import Planner                        # noqa: E402
from pathforward.agents.evidence_gate import EvidenceGate                      # noqa: E402
from pathforward.config import load_settings                          # noqa: E402
from pathforward.credential.mint import mint                          # noqa: E402
from pathforward.iq import derivation as dv                           # noqa: E402
from pathforward.iq import traversal                                  # noqa: E402
from pathforward.iq.seed import build_seed, HERO_WORKER_ID            # noqa: E402
from generate_data import _learner_responses                         # noqa: E402

CURATOR_AGENT = "pathforward-curator"
PLANNER_AGENT = "pathforward-planner"
CRITIC_AGENT = "pathforward-critic"
INSIGHTS_AGENT = "pathforward-insights"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    s = load_settings(os.path.join(_ROOT, ".env"))

    onto = build_seed()
    worker = onto.workers[HERO_WORKER_ID]
    role = onto.roles[worker.target_role_id]
    edges = dv.build_all_edges(onto)

    # Curator + Planner + Critic: tool-less live reasoning agents. Generator: search-grounded agent.
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
    adaptive = AdaptiveController(calibration=cold_start_calibrate(_learner_responses(onto)))
    print(f"worker={worker.id} target={role.name} (rai: {s.rai_policy or 'default'})")

    rc = 1
    try:
        result = run_multiagent(
            worker, onto, edges,
            Curator(curator_client), Generator(generator_client),
            EvidenceGate(LocalNumericChecker()), Planner(planner_client, LocalNumericChecker()),
            critic=Critic(critic_client), adaptive=adaptive,
            insights=ProgramInsightsAgent(insights_client),
        )
        d, loop, plan, ins = result.curator, result.loop, result.plan, result.insights

        # --- Curator (live reasoning, deterministically gated) ---
        admissible = [s_ for s_ in dv.cert_gap_skill_ids(worker, role)
                      if traversal.is_assessable(s_, onto)]
        print("\n[CURATOR]")
        print(f"  admissible gaps: {[onto.skills[x].name for x in d.admissible_skill_ids]}")
        print(f"  live ranking:    {list(d.ranking)}  corrected={d.corrected}")
        chosen_ok = bool(d.chosen_skill_id) and d.chosen_skill_id in admissible
        print(f"  chosen: {d.chosen_skill_id} "
              f"('{onto.skills[d.chosen_skill_id].name if d.chosen_skill_id else '-'}')  "
              f"admissible? {chosen_ok}")

        # --- Generator/Evidence Gate loop (live grounded) ---
        print("\n[LOOP]")
        print(f"  status: {loop.status.upper()}  attempts: {loop.attempts}")
        for t in loop.transcript:
            it, v, cr = t["item"], t["verdict"], t.get("critic")
            crline = (f" | Critic(advisory): {cr.recommendation}" if cr else "")
            print(f"   attempt {t['attempt']}: gate {'PASS' if v.passed else 'REJECT'}{crline} | "
                  f"retrieved {len(it.retrieved_ref_ids)} cited {list(it.cited_ref_ids)}")
            if not v.passed:
                print(f"     failed: {[f['criterion'] for f in v.failed_reasons]}")

        spine_ok = False
        if loop.status == "verified":
            cred = mint(worker, role, d.chosen_edge_id, d.chosen_skill_id, loop)
            cs = cred.credential_subject
            spine_ok = cs["cited_edge_id"] == d.chosen_edge_id == loop.driving_edge_id
            print(f"\n[MINT] worker={cs['worker_id']} skill={cs['skill_id']} "
                  f"readiness={cs['readiness']} cited_edge_id={cs['cited_edge_id']}")
            print(f"  spine intact: {spine_ok}")

        # --- Planner (live reasoning, deterministically gated) ---
        print("\n[PLANNER]")
        print(f"  total {plan.total_hours:.0f}h over {plan.weeks} weeks @ "
              f"{plan.weekly_capacity_hours:.0f}h/wk  corrected={plan.corrected}")
        print(f"  numeric check: {plan.numeric_check.get('claim')} -> ok={plan.numeric_check.get('ok')}")
        print(f"  accessibility: {list(plan.accessibility_adaptations) or 'none'}")
        weekly: dict[int, float] = {}
        for ph in plan.phases:
            weekly[ph.week] = weekly.get(ph.week, 0.0) + ph.hours
        capacity_ok = plan.capacity_respected and all(
            load <= plan.weekly_capacity_hours + 1e-6 for load in weekly.values())

        # --- Program Insights (live reasoning over code-computed cohort aggregates, read-only) ---
        print("\n[INSIGHTS]")
        wc, rc = ins.worker_comparison, ins.role_cohort
        print(f"  source tier: {ins.source}")
        print(f"  worker rank {wc['rank']}/{wc['n_cohort']} in the {rc['role_name']} cohort  "
              f"(readiness {wc['worker_readiness']} vs cohort mean {wc['cohort_mean_readiness']})")
        print(f"  narrative (display-only): {ins.narrative[:100]}")
        # Guardrail: the agent must NARRATE the code-computed number, not fabricate one. The live
        # readiness it reports must equal the derivation recompute (floor reconciles by construction).
        insights_ok = abs(wc["worker_readiness"] - dv.readiness_score(worker, role)) < 1e-9

        checks = {
            "curator chose an admissible gap": chosen_ok,
            "loop verified a grounded item": loop.status == "verified",
            "credential spine intact": spine_ok,
            "plan respects weekly capacity": capacity_ok,
            "plan numeric check passed": bool(plan.numeric_check.get("ok")),
            "insights reconcile to derivation": insights_ok,
        }
        print("\n=== checks ===")
        for name, ok in checks.items():
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        rc = 0 if all(checks.values()) else 1
        print("\nLIVE MULTI-AGENT", "PASS" if rc == 0 else "FAIL")
    finally:
        for c in (curator_client, planner_client, critic_client, insights_client, generator_client):
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
        print("agents deleted")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
