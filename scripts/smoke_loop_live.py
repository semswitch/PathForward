"""Live full-loop smoke: run the REAL assessment loop against the Foundry agent for EMP-001's
first CertGap.

Proves end to end on live Azure: gpt-5.5 autonomously retrieves, produces a grounded structured
item that passes the Evidence Gate's corpus-INTERSECT-retrieved gate, and mints a citation-backed
credential whose cited_edge_id is the driving CertGap edge. The offline core (FakeLLMClient) is
untouched; this is the Azure swap-in.

    python scripts/smoke_loop_live.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.agents.foundry import FoundryLLMClient        # noqa: E402
from pathforward.agents.generator import Generator             # noqa: E402
from pathforward.agents.loop import run_assessment_loop        # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker     # noqa: E402
from pathforward.agents.evidence_gate import EvidenceGate               # noqa: E402
from pathforward.config import load_settings                   # noqa: E402
from pathforward.credential.mint import mint                   # noqa: E402
from pathforward.iq import derivation as dv                    # noqa: E402
from pathforward.iq import traversal                           # noqa: E402
from pathforward.iq.seed import build_seed, HERO_WORKER_ID     # noqa: E402


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
    driving = traversal.cert_gap_edges(worker, onto, edges)[0]
    skill = onto.skills[driving.target_id]
    allowed = traversal.approved_refs(worker, skill, onto)
    print(f"worker={worker.id} driving={driving.id} skill='{skill.name}'")
    print(f"approved grounding refs: {list(allowed)}")

    client = FoundryLLMClient(endpoint=s.foundry_project_endpoint, model=s.model_deployment,
                              index_name=s.search_index)
    print(f"rai: enforced at deployment + declared on toolbox (policy '{s.rai_policy or 'default'}')")
    rc = 1
    try:
        result = run_assessment_loop(driving, skill, allowed, Generator(client),
                                     EvidenceGate(LocalNumericChecker()))
        print(f"\nloop status: {result.status.upper()}  attempts: {result.attempts}")
        for t in result.transcript:
            it, v = t["item"], t["verdict"]
            print(f"  attempt {t['attempt']}: {'PASS' if v.passed else 'REJECT'}")
            print(f"    stem: {it.stem[:90]}")
            print(f"    retrieved {len(it.retrieved_ref_ids)} | cited {list(it.cited_ref_ids)}")
            if not v.passed:
                print(f"    failed: {[f['criterion'] for f in v.failed_reasons]}")

        if result.status == "verified":
            cred = mint(worker, role, driving.id, skill.id, result)
            cs = cred.credential_subject
            print(f"\nMINTED credential: worker={cs['worker_id']} skill={cs['skill_id']} "
                  f"readiness={cs['readiness']} cited_edge_id={cs['cited_edge_id']}")
            print(f"evidence: {cred.evidence}")
            print(f"spine intact: cited_edge_id == driving? {cs['cited_edge_id'] == driving.id}")
            print("\nLIVE LOOP PASS")
            rc = 0
        else:
            print("\nLIVE LOOP: abstained (no grounded item within attempts)")
    finally:
        client.close()
        print("agent deleted")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
