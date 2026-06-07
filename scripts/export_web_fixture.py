"""Export a JSON fixture of the EMP-001 demo run for the web UI to render.

Writes data/generated/demo_fixture.json and web/src/lib/fixture.json so the Carbon
components have real Glass-Box / Arena / Trust-Console data before Azure is wired.

Run:  python scripts/export_web_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from pathforward.agents.calibration import cold_start_calibrate           # noqa: E402
from pathforward.agents.client import FakeLLMClient                        # noqa: E402
from pathforward.agents.generator import Generator                        # noqa: E402
from pathforward.agents.loop import run_assessment_loop                   # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker                # noqa: E402
from pathforward.agents.verifier import Verifier                          # noqa: E402
from pathforward.credential.mint import mint                              # noqa: E402
from pathforward.iq import derivation as dv                               # noqa: E402
from pathforward.iq import traversal                                      # noqa: E402
from pathforward.iq.seed import build_seed, HERO_WORKER_ID                # noqa: E402
from generate_data import _learner_responses                             # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_fixture() -> dict:
    onto = build_seed()
    worker = onto.workers[HERO_WORKER_ID]
    role = onto.roles[worker.target_role_id]
    edges = dv.build_all_edges(onto)

    gb = traversal.build_glassbox(worker, onto, edges)
    driving = traversal.cert_gap_edges(worker, onto, edges)[0]
    skill = onto.skills[driving.target_id]
    allowed = tuple(driving.source_ref_ids) + ("corpus::AZ-204",)
    result = run_assessment_loop(driving, skill, allowed,
                                 Generator(FakeLLMClient()), Verifier(LocalNumericChecker()))
    cal = cold_start_calibrate(_learner_responses(onto)).get(f"item-{skill.id}", {})
    cred = mint(worker, role, driving.id, skill.id, result, cal)

    verified = [t for t in result.transcript if t["verdict"].passed]
    return {
        "worker": {
            "id": worker.id, "name": worker.name,
            "current_role_title": worker.current_role_title,
            "target_role": role.name,
            "weekly_capacity_hours": worker.weekly_capacity_hours,
            "accessibility_needs": list(worker.accessibility_needs),
        },
        "glassbox": gb,
        "driving_edge_id": driving.id,
        "targeted_skill": skill.name,
        "loop": result.to_doc(),
        "calibration": cal,
        "credential": cred.to_doc(),
        "metrics": {
            "grounded_citation_rate": f"{len(verified)}/{len(verified)}",
            "attempts_to_verified": result.attempts,
            "rejected_before_pass": result.attempts - 1,
            "readiness_pct": round(gb["meta"]["readiness"] * 100),
            "ungrounded_credentials": 0,
        },
    }


def main() -> None:
    fixture = build_fixture()
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
