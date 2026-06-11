"""Code-contract-only multi-agent flow helper."""
from __future__ import annotations

from pathforward.agents.adaptive import AdaptiveController
from pathforward.agents.critic import Critic
from pathforward.agents.curator import Curator
from pathforward.agents.evidence_gate import EvidenceGate
from pathforward.agents.generator import Generator
from pathforward.agents.insights import ProgramInsightsAgent
from pathforward.agents.loop import run_assessment_loop
from pathforward.agents.orchestrator import _run_insights
from pathforward.agents.planner import Planner
from pathforward.agents.types import LoopResult, MultiAgentResult
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.models import Edge, Ontology, Worker
from pathforward.obs import tracing


def run_multiagent_code_contract(worker: Worker, onto: Ontology, edges: list[Edge],
                                 curator: Curator, generator: Generator,
                                 evidence_gate: EvidenceGate, planner: Planner,
                                 critic: Critic | None = None,
                                 adaptive: AdaptiveController | None = None,
                                 insights: ProgramInsightsAgent | None = None) -> MultiAgentResult:
    role = onto.roles[worker.target_role_id]
    with tracing.span("multiagent", **{"pf.worker": worker.id, "pf.target_role": role.id}) as root:
        with tracing.span("curate", **{"pf.worker": worker.id}) as cur_span:
            decision = curator.curate(worker, role, onto)
            cur_span.set(**{"pf.admissible": len(decision.admissible_skill_ids),
                            "pf.chosen": decision.chosen_skill_id or "(none)",
                            "pf.corrected": decision.corrected})

        if not decision.chosen_skill_id:
            root.set(**{"pf.status": "abstained", "pf.reason": "no_assessable_gap"})
            root.event("abstained.no_assessable_gap")
            loop = LoopResult(status="abstained", driving_edge_id="", targeted_skill_id="",
                              attempts=0, item=None, verdict=None, transcript=[], citations=())
            with tracing.span("plan", **{"pf.worker": worker.id}):
                plan = planner.plan(worker, decision.ranking, onto)
            program_insights = _run_insights(insights, worker, role, onto)
            return MultiAgentResult(curator=decision, loop=loop, plan=plan,
                                    insights=program_insights)

        skill = onto.skills[decision.chosen_skill_id]
        driving = next(e for e in traversal.cert_gap_edges(worker, onto, edges)
                       if e.id == decision.chosen_edge_id)
        allowed = traversal.approved_refs(worker, skill, onto)

        loop = run_assessment_loop(driving, skill, allowed, generator, evidence_gate,
                                   critic=critic, adaptive=adaptive)
        root.set(**{"pf.status": loop.status, "pf.attempts": loop.attempts})

        with tracing.span("plan", **{"pf.worker": worker.id,
                                     "pf.gap_skills": len(decision.ranking)}) as plan_span:
            plan = planner.plan(worker, decision.ranking, onto)
            plan_span.set(**{"pf.weeks": plan.weeks, "pf.total_hours": plan.total_hours,
                             "pf.corrected": plan.corrected})

        program_insights = _run_insights(insights, worker, role, onto)
        return MultiAgentResult(curator=decision, loop=loop, plan=plan, insights=program_insights)
