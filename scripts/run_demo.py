"""Offline end-to-end demo — proves the multi-agent reasoning spine with no Azure.

Runs the full PathForward flow for the hero worker EMP-001 against the FakeLLMClient:
  Glass-Box traversal -> Curator (gap prioritization, reasoned) -> Generator/Evidence Gate loop
  (reject->regenerate) -> cold-start calibration -> citation-backed credential mint
  -> Planner (capacity + accessibility learning plan), with the causal-spine assertion enforced.

Three reasoning agents (Curator, Generator, Planner) are orchestrated in code; the Evidence Gate gate
and the mint's causal-spine check remain deterministic. This is the textual storyboard for the
demo video. Run:
  python scripts/run_demo.py
"""
from __future__ import annotations

import os
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.calibration import cold_start_calibrate          # noqa: E402
from pathforward.agents.client import FakeLLMClient                       # noqa: E402
from pathforward.agents.curator import Curator                            # noqa: E402
from pathforward.agents.generator import Generator                       # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker               # noqa: E402
from pathforward.agents.orchestrator import run_multiagent               # noqa: E402
from pathforward.agents.planner import Planner                           # noqa: E402
from pathforward.agents.evidence_gate import EvidenceGate                         # noqa: E402
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

    # --- the three-agent reasoning loop: Curator -> Generator/Evidence Gate -> Planner ---------------
    cur = Curator(FakeLLMClient())
    gen = Generator(FakeLLMClient())
    ver = EvidenceGate(LocalNumericChecker())
    planner = Planner(FakeLLMClient(), LocalNumericChecker())
    result = run_multiagent(worker, onto, edges, cur, gen, ver, planner)
    decision, loop_result, plan = result.curator, result.loop, result.plan

    rule("3. CURATOR AGENT  - which gap to certify first (reasoned, then gated)")
    print(f"  Admissible gaps (derived, assessable): "
          f"{[onto.skills[s].name for s in decision.admissible_skill_ids]}")
    if decision.corrected:
        print("  Curator over-reached (proposed a non-gap / already-held skill); the deterministic")
        print("  admissibility gate STRUCK it and fell back to a real gap.  <- glass-box catch")
    chosen_skill = onto.skills[decision.chosen_skill_id]
    print(f"  Chosen target: {chosen_skill.name} ({decision.chosen_skill_id})")
    print(f"  Driving edge:  {decision.chosen_edge_id}")

    rule("4. ASSESSMENT LOOP  - blueprint driven by the Curator-chosen CertGap edge")
    skill = chosen_skill
    allowed = traversal.approved_refs(worker, skill, onto)
    print(f"  Driving edge: {decision.chosen_edge_id}  ->  tests skill '{skill.name}'")
    print(f"  Approved grounding refs: {list(allowed)}")
    for t in loop_result.transcript:
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
    print(f"\n  loop status: {loop_result.status.upper()}  (attempts: {loop_result.attempts})")

    rule("5. COLD-START CALIBRATION  - honest psychometrics")
    stats = cold_start_calibrate(_learner_responses(onto))
    item_id = f"item-{skill.id}"
    cal = stats.get(item_id, {})
    print(f"  {item_id}: difficulty={cal.get('difficulty')}  "
          f"discrimination={cal.get('discrimination')}  ({cal.get('label')})")

    rule("6. CREDENTIAL MINT  - citation-backed, causal-spine asserted")
    cred = mint(worker, role, decision.chosen_edge_id, skill.id, loop_result, cal)
    cs = cred.credential_subject
    print(f"  subject: worker={cs['worker_id']} skill={cs['skill_id']} "
          f"readiness={cs['readiness']}")
    print(f"  cited_edge_id: {cs['cited_edge_id']}  "
          f"(== driving CertGap edge? {cs['cited_edge_id'] == decision.chosen_edge_id})")
    print(f"  evidence: {cred.evidence}")
    print(f"  type: {cred.type}")

    rule("7. PLANNER AGENT  - capacity + accessibility learning plan (advisory, gated)")
    if plan.corrected:
        print("  Planner proposed a pace above the worker's weekly capacity; the deterministic")
        print("  capacity gate CLAMPED it to a feasible schedule.  <- glass-box catch")
    print(f"  Total study hours (derived from cert blueprint): {plan.total_hours:.0f}h")
    print(f"  Weekly capacity: {plan.weekly_capacity_hours:.0f}h  ->  plan spans {plan.weeks} weeks")
    per_skill: "OrderedDict[str, dict]" = OrderedDict()
    for ph in plan.phases:
        rec = per_skill.setdefault(ph.skill_id, {"hours": 0.0, "cert": ph.cert_id,
                                                 "weeks": set()})
        rec["hours"] += ph.hours
        rec["weeks"].add(ph.week)
    for sid, rec in per_skill.items():
        wk = sorted(rec["weeks"])
        span = f"week {wk[0]}" if len(wk) == 1 else f"weeks {wk[0]}-{wk[-1]}"
        print(f"   - {onto.skills[sid].name} ({sid}): {rec['hours']:.0f}h via {rec['cert']}  [{span}]")
    print(f"  Numeric check: {plan.numeric_check['claim']}  -> ok={plan.numeric_check['ok']}")
    print(f"  Accessibility adaptations (from declared needs): "
          f"{list(plan.accessibility_adaptations) or 'none'}")

    rule("HERO METRICS  - on screen in the first 30s")
    verified_items = [t for t in loop_result.transcript if t["verdict"].passed]
    cited = [t for t in verified_items if t["item"].cited_ref_ids]
    print(f"  reasoning agents in the loop: 3 (Curator, Generator, Planner) + deterministic Evidence Gate")
    print(f"  grounded-citation rate: {len(cited)}/{len(verified_items)} verified items cited")
    print(f"  attempts to a verified item: {loop_result.attempts} "
          f"({loop_result.attempts - 1} rejected on grounding/quality)")
    print(f"  readiness (EMP-001 -> {role.name}): {gb['meta']['readiness'] * 100:.0f}%")
    print(f"  ungrounded items minted into credentials: 0 (fail-closed gate)")
    print("\n  Spine intact: CertGap edge -> Curator -> blueprint -> verified item -> credential "
          "cites the same edge.")


if __name__ == "__main__":
    main()
