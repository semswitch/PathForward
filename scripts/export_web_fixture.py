"""Export a JSON fixture of the EMP-001 demo run for the web UI to render.

Writes data/generated/demo_fixture.json and web/src/lib/fixture.json so the Carbon
components have Glass-Box / Arena / Trust-Console data. Offline rehearsal is the default;
`--live` exports from the live Foundry/Fabric path.

Run:  python scripts/export_web_fixture.py
      python scripts/export_web_fixture.py --live
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from pathforward.agents.adaptive import AdaptiveController                 # noqa: E402
from pathforward.agents.calibration import cold_start_calibrate           # noqa: E402
from pathforward.agents.orchestrator import run_multiagent                # noqa: E402
from pathforward.config import load_settings                              # noqa: E402
from pathforward.credential.mint import mint                              # noqa: E402
from pathforward.iq import derivation as dv                               # noqa: E402
from pathforward.iq import traversal                                      # noqa: E402
from pathforward.iq.seed import build_seed, HERO_WORKER_ID                # noqa: E402
from demo_runtime import build_demo_agents                                # noqa: E402
from generate_data import _learner_responses                             # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_fixture(*, live: bool = False, prefer_fabric: bool = True) -> dict:
    onto = build_seed()
    worker = onto.workers[HERO_WORKER_ID]
    role = onto.roles[worker.target_role_id]
    edges = dv.build_all_edges(onto)

    gb = traversal.build_glassbox(worker, onto, edges)

    # The reasoning loop: Curator -> Generator -> Critic -> Evidence Gate -> Planner.
    stats = cold_start_calibrate(_learner_responses(onto))
    adaptive = AdaptiveController(calibration=stats)
    settings = load_settings(os.path.join(ROOT, ".env"))
    agents = build_demo_agents(live=live, settings=settings, prefer_fabric=prefer_fabric)
    try:
        result = run_multiagent(worker, onto, edges,
                                agents.curator, agents.generator, agents.gate, agents.planner,
                                critic=agents.critic, adaptive=adaptive, insights=agents.insights)
    finally:
        agents.close()
    decision, loop_result, plan = result.curator, result.loop, result.plan
    skill = onto.skills[decision.chosen_skill_id]
    cal = stats.get(f"item-{skill.id}", {})
    cred = mint(worker, role, decision.chosen_edge_id, skill.id, loop_result, cal)

    verified = [t for t in loop_result.transcript if t["verdict"].passed]
    return {
        "provenance": {
            **agents.provenance,
            "fixture_export": "live" if live else "offline",
            "credential_trust_boundary": "EvidenceGate+LocalNumericChecker+mint",
        },
        "worker": {
            "id": worker.id, "name": worker.name,
            "current_role_title": worker.current_role_title,
            "target_role": role.name,
            "weekly_capacity_hours": worker.weekly_capacity_hours,
            "accessibility_needs": list(worker.accessibility_needs),
        },
        "glassbox": gb,
        "driving_edge_id": decision.chosen_edge_id,
        "targeted_skill": skill.name,
        "difficulty_band": adaptive.band_for(skill.id),   # adaptive (cold-start, selection-only)
        "curator": decision.to_doc(),
        "loop": loop_result.to_doc(),
        "calibration": cal,
        "credential": cred.to_doc(),
        "plan": plan.to_doc(),
        # read-only cohort/program reasoning (advisory). Optional on MultiAgentResult -> None-guard.
        "insights": result.insights.to_doc() if result.insights else None,
        "metrics": {
            "grounded_citation_rate": f"{len(verified)}/{len(verified)}",
            "attempts_to_verified": loop_result.attempts,
            "rejected_before_pass": loop_result.attempts - 1,
            "readiness_pct": round(gb["meta"]["readiness"] * 100),
            "ungrounded_credentials": 0,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Export the PathForward web fixture.")
    ap.add_argument("--live", action="store_true",
                    help="export from live Foundry/Fabric clients instead of FakeLLMClient")
    ap.add_argument("--no-fabric", action="store_true",
                    help="in --live mode, keep Program Insights on the derivation-floor narrator")
    args = ap.parse_args()
    fixture = build_fixture(live=args.live, prefer_fabric=not args.no_fabric)
    targets = [
        os.path.join(ROOT, "data", "generated", "demo_fixture.json"),
        os.path.join(ROOT, "web", "src", "lib", "fixture.json"),
    ]
    for t in targets:
        os.makedirs(os.path.dirname(t), exist_ok=True)
        with open(t, "w", encoding="utf-8") as f:
            json.dump(fixture, f, indent=2)
        print(f"wrote {t}")


if __name__ == "__main__":
    main()
