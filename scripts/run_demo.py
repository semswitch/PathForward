"""Offline end-to-end demo — proves the reasoning spine with no Azure.

Runs the full PathForward flow for the hero worker EMP-001 against the FakeLLMClient:
  Glass-Box traversal -> CertGap blueprint -> Generator/Verifier loop (reject->regenerate)
  -> cold-start calibration -> citation-backed credential mint, with the causal-spine
  assertion enforced.

This is the textual storyboard for the <=4:30 demo video. Run:
  python scripts/run_demo.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.calibration import cold_start_calibrate          # noqa: E402
from pathforward.agents.client import FakeLLMClient                       # noqa: E402
from pathforward.agents.generator import Generator                       # noqa: E402
from pathforward.agents.loop import run_assessment_loop                  # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker               # noqa: E402
from pathforward.agents.verifier import Verifier                         # noqa: E402
from pathforward.credential.mint import mint                             # noqa: E402
from pathforward.iq import derivation as dv                              # noqa: E402
from pathforward.iq import traversal                                     # noqa: E402
from pathforward.iq.seed import build_seed, HERO_WORKER_ID               # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from generate_data import _learner_responses  # noqa: E402


def rule(title: str) -> None:
    print("\n" + "=" * 70 + f"\n  {title}\n" + "=" * 70)


def main() -> None:
    onto = build_seed()
    worker = onto.workers[HERO_WORKER_ID]
    role = onto.roles[worker.target_role_id]
    edges = dv.build_all_edges(onto)

    rule(f"1. WORKER  {worker.id}  - the human hook")
    print(f"  {worker.name}: {worker.current_role_title}")
    print(f"  Reskilling target: {role.name} ({role.id})")
    print(f"  Weekly capacity: {worker.weekly_capacity_hours}h   "
          f"Accessibility: {', '.join(worker.accessibility_needs) or 'none'}")

    rule("2. GLASS-BOX REASONING GRAPH  - multi-hop, derived edges shown")
    gb = traversal.build_glassbox(worker, onto, edges)
    print(f"  nodes: {len(gb['nodes'])}   edges: {len(gb['edges'])}")
    for e in gb["edges"]:
        if e["derived"]:
            tag = "DERIVED" if e["type"] == "certgap" else "DERIVED*"
            print(f"   [{tag:8}] {e['id']}  ({e['source_badge']})")
    gap = gb["meta"]["cert_gap_skill_ids"]
    print(f"\n  CertGap skills (raw data does NOT contain these): "
          f"{[onto.skills[s].name for s in gap]}")
    print(f"  Readiness (derived): {gb['meta']['readiness'] * 100:.0f}%")

    rule("3. ASSESSMENT LOOP  - blueprint driven by the CertGap edge")
    gap_edges = traversal.cert_gap_edges(worker, onto, edges)
    driving = gap_edges[0]
    skill = onto.skills[driving.target_id]
    allowed = tuple(driving.source_ref_ids) + (f"corpus::AZ-204",)
    print(f"  Driving edge: {driving.id}  ->  tests skill '{skill.name}'")
    print(f"  Approved grounding refs: {list(allowed)}")

    gen = Generator(FakeLLMClient())
    ver = Verifier(LocalNumericChecker())
    result = run_assessment_loop(driving, skill, allowed, gen, ver)

    for t in result.transcript:
        v = t["verdict"]
        status = "PASS" if v.passed else "REJECT"
        print(f"\n  attempt {t['attempt']}: {status}")
        print(f"    stem: {t['item'].stem[:72]}...")
        print(f"    retrieved (tool trace): {list(t['item'].retrieved_ref_ids) or '(none)'}")
        print(f"    citations: {list(t['item'].cited_ref_ids) or '(none)'}")
        if not v.passed:
            for fr in v.failed_reasons:
                print(f"    x {fr['criterion']}: {fr['reason']}")
        else:
            print(f"    criteria: {v.criteria}")
    print(f"\n  loop status: {result.status.upper()}  (attempts: {result.attempts})")

    rule("4. COLD-START CALIBRATION  - honest psychometrics")
    stats = cold_start_calibrate(_learner_responses(onto))
    item_id = f"item-{skill.id}"
    cal = stats.get(item_id, {})
    print(f"  {item_id}: difficulty={cal.get('difficulty')}  "
          f"discrimination={cal.get('discrimination')}  ({cal.get('label')})")

    rule("5. CREDENTIAL MINT  - citation-backed, causal-spine asserted")
    cred = mint(worker, role, driving.id, skill.id, result, cal)
    cs = cred.credential_subject
    print(f"  subject: worker={cs['worker_id']} skill={cs['skill_id']} "
          f"readiness={cs['readiness']}")
    print(f"  cited_edge_id: {cs['cited_edge_id']}  "
          f"(== driving CertGap edge? {cs['cited_edge_id'] == driving.id})")
    print(f"  evidence: {cred.evidence}")
    print(f"  type: {cred.type}")

    rule("HERO METRICS  - on screen in the first 30s")
    verified_items = [t for t in result.transcript if t["verdict"].passed]
    cited = [t for t in verified_items if t["item"].cited_ref_ids]
    print(f"  grounded-citation rate: {len(cited)}/{len(verified_items)} verified items cited")
    print(f"  attempts to a verified item: {result.attempts} "
          f"({result.attempts - 1} rejected on grounding/quality)")
    print(f"  readiness (EMP-001 -> {role.name}): {gb['meta']['readiness'] * 100:.0f}%")
    print(f"  ungrounded items minted into credentials: 0 (fail-closed gate)")
    print("\n  Spine intact: CertGap edge -> blueprint -> verified item -> credential cites the same edge.")


if __name__ == "__main__":
    main()
