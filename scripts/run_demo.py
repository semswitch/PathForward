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

from pathforward.agents.adaptive import AdaptiveController                # noqa: E402
from pathforward.agents.analyst import LocalAnalyst                        # noqa: E402
from pathforward.agents.calibration import cold_start_calibrate          # noqa: E402
from pathforward.agents.client import FakeLLMClient                       # noqa: E402
from pathforward.agents.critic import Critic                              # noqa: E402
from pathforward.agents.curator import Curator                            # noqa: E402
from pathforward.agents.generator import Generator                       # noqa: E402
from pathforward.agents.insights import ProgramInsightsAgent             # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker               # noqa: E402
from pathforward.agents.orchestrator import run_multiagent               # noqa: E402
from pathforward.agents.planner import Planner                           # noqa: E402
from pathforward.agents import workflow as wf                            # noqa: E402
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

    # --- the reasoning loop: Curator -> Generator -> Critic -> Evidence Gate -> Planner ----------
    stats = cold_start_calibrate(_learner_responses(onto))      # cold-start item calibration
    adaptive = AdaptiveController(calibration=stats)            # pure-code difficulty selection
    cur = Curator(FakeLLMClient())
    gen = Generator(FakeLLMClient())
    critic = Critic(FakeLLMClient())
    gate = EvidenceGate(LocalNumericChecker())
    planner = Planner(FakeLLMClient(), LocalNumericChecker())
    insights = ProgramInsightsAgent(FakeLLMClient())          # read-only cohort/program reasoning
    result = run_multiagent(worker, onto, edges, cur, gen, gate, planner,
                            critic=critic, adaptive=adaptive, insights=insights)
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

    rule("4. ASSESSMENT LOOP  - Generator -> Critic (agent) -> Evidence Gate (code)")
    skill = chosen_skill
    allowed = traversal.approved_refs(worker, skill, onto)
    print(f"  Driving edge: {decision.chosen_edge_id}  ->  tests skill '{skill.name}'")
    print(f"  Approved grounding refs: {list(allowed)}")
    _bcal = stats.get(f"item-{skill.id}", {})
    print(f"  Adaptive difficulty (pure code, cold-start, selection-only): band "
          f"'{adaptive.band_for(skill.id)}' from difficulty={_bcal.get('difficulty')} "
          f"(hint to the Generator; never an input to the gate or mint)")
    for t in loop_result.transcript:
        v = t["verdict"]
        gate_status = "PASS" if v.passed else "REJECT"
        cr = t.get("critic")
        print(f"\n  attempt {t['attempt']}:")
        print(f"    stem: {t['item'].stem[:72]}...")
        print(f"    retrieved (tool trace): {list(t['item'].retrieved_ref_ids) or '(none)'}")
        print(f"    citations: {list(t['item'].cited_ref_ids) or '(none)'}")
        if cr:
            concerns = ", ".join(f"{c.criterion_name}({c.severity})" for c in cr.concerns) or "none"
            print(f"    Critic agent (advisory) : {cr.recommendation.upper():6}  concerns: {concerns}")
        print(f"    Evidence Gate (decides) : {gate_status}")
        if not v.passed:
            for fr in v.failed_reasons:
                print(f"      x {fr['criterion']}: {fr['reason']}")
        else:
            print(f"      criteria: {v.criteria}")
    # The maker-checker beat: on the PASSING item the Critic still raised a quality concern the
    # deterministic gate cannot compute — agents reason, code notarizes.
    passed = [t for t in loop_result.transcript if t["verdict"].passed]
    if passed and passed[-1].get("critic") and passed[-1]["critic"].concerns:
        print("\n  ^ note: the Critic agent flagged a quality dimension (ambiguity) the deterministic")
        print("    gate cannot compute, on an item the gate still PASSED -- advisory, never overriding.")
    print(f"\n  loop status: {loop_result.status.upper()}  (attempts: {loop_result.attempts})")

    rule("5. COLD-START CALIBRATION  - honest psychometrics (drives the adaptive band above)")
    item_id = f"item-{skill.id}"
    cal = stats.get(item_id, {})
    print(f"  {item_id}: difficulty={cal.get('difficulty')}  "
          f"discrimination={cal.get('discrimination')}  ({cal.get('label')})")

    # Code Interpreter analyst (offline: LocalAnalyst; live: CodeInterpreterAnalyst) -- ADVISORY and
    # NON-GATING. Two roles: an independent numeric second opinion, and calibration explainability.
    analyst = LocalAnalyst()
    print(f"\n  Code Interpreter analyst (advisory, NON-GATING; the gate's oracle stays LocalNumericChecker):")
    _passed = [t for t in loop_result.transcript if t["verdict"].passed]
    if _passed:                                          # guard the abstain path (no verified item)
        verified_item = _passed[-1]["item"]
        so = analyst.second_opinion(verified_item.numeric_claim or "")
        verdict_label = "AGREES" if so.agrees else ("n/a" if so.agrees is None else "DISAGREES")
        print(f"    numeric second opinion on '{verified_item.numeric_claim}': {verdict_label} "
              f"-> {so.summary}")
    else:
        print("    (loop abstained -> no verified item, so no numeric claim to second-opinion)")
    analyst_cal = analyst.calibration_report({k: v for k, v in stats.items() if k.startswith("item-")})
    print(f"    calibration ({analyst_cal.summary}):")
    for line in analyst_cal.figures[0].splitlines()[:6]:
        print(f"      {line}")
    print("    ^ the model writes-and-runs this Python live (non-deterministic) -> never the gate.")

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

    rule("8. PROGRAM INSIGHTS AGENT  - read-only cohort reasoning (off the credential path)")
    ins = result.insights
    if ins is not None:
        wc, rc, prog = ins.worker_comparison, ins.role_cohort, ins.program
        print(f"  Source tier: {ins.source}  (derivation floor; Fabric-ready live tier is a swap-in seam)")
        print(f"  This worker vs cohort: rank {wc['rank']}/{wc['n_cohort']} targeting {rc['role_name']}  "
              f"(readiness {wc['worker_readiness']} vs cohort mean {wc['cohort_mean_readiness']})")
        top = rc["bottleneck_skills"][0] if rc["bottleneck_skills"] else None
        if top:
            print(f"  Cohort's biggest bottleneck: {top['name']} ({top['skill_id']}) "
                  f"- missing for {top['gap_count']}/{rc['n_workers']} in the cohort")
        print(f"  Program-wide: {prog['n_workers']} workers, mean readiness "
              f"{prog['overall_mean_readiness']}; un-certifiable gap skills: "
              f"{list(prog['unassessable_gap_skill_ids']) or 'none'}")
        print(f"  Agent narrative (display-only): {ins.narrative[:96]}...")
        print("  ^ every number above is recomputed by code from the SAME derivation as the credential;")
        print("    the agent only NARRATES it (cannot fabricate a statistic), and never touches the mint.")

    rule("9. WORKFLOW TOPOLOGY  - the SAME chain as an Agent Framework graph (ADOPT-LATER)")
    graph = wf.build_pathforward_graph()
    print("  The in-process run_multiagent above IS the executed path (always-green). The Microsoft")
    print("  Agent Framework Workflow track projects that SAME chain onto a graph, with the Evidence")
    print(f"  Gate + mint as deterministic code executors. Flag: {wf.PF_WORKFLOW_ENV}="
          f"{'on' if wf.workflow_enabled() else 'off'} (off -> in-process).")
    trust_label = {wf.Trust.TRUST: "TRUST   ", wf.Trust.ADVISORY: "advisory", wf.Trust.SINK: "sink    "}
    kind_label = {wf.NodeKind.AGENT: "agent       ", wf.NodeKind.EXECUTOR: "CODE EXEC   ",
                  wf.NodeKind.REQUEST_INFO: "human (HITL)", wf.NodeKind.TERMINAL: "output sink "}
    print("\n  nodes:")
    for n in graph.nodes:
        print(f"    [{trust_label[n.trust]}] {kind_label[n.kind]} {n.id}")
    print("\n  no-bypass trust audit (developer-proven graph-shape property; plan §9 / ADR 009):")
    for p in wf.trust_audit(graph):
        print(f"    {'PASS' if p.holds else 'FAIL'}  {p.key}")
    print(f"    -> all hold: {wf.trust_holds(graph)}  "
          f"(no path reaches the credential without the deterministic gate)")
    print("  ^ Agent Framework Python is GA (1.0.0, 2026-04-02) but is not provisioned in this env;")
    print("    by design the credential trust spine never hard-depends on the orchestrator, so the")
    print("    in-process loop stays canonical and this is a flag-gated projection of the same chain.")

    rule("HERO METRICS  - on screen in the first 30s")
    verified_items = [t for t in loop_result.transcript if t["verdict"].passed]
    cited = [t for t in verified_items if t["item"].cited_ref_ids]
    print(f"  reasoning agents: 5 (Curator, Generator, Critic, Planner, Program Insights) "
          f"+ deterministic Evidence Gate")
    print(f"  grounded-citation rate: {len(cited)}/{len(verified_items)} verified items cited")
    print(f"  attempts to a verified item: {loop_result.attempts} "
          f"({loop_result.attempts - 1} rejected on grounding/quality)")
    print(f"  readiness (EMP-001 -> {role.name}): {gb['meta']['readiness'] * 100:.0f}%")
    print(f"  ungrounded items minted into credentials: 0 (fail-closed gate)")
    print("\n  Spine intact: CertGap edge -> Curator -> blueprint -> verified item -> credential "
          "cites the same edge.")


if __name__ == "__main__":
    main()
