"""The multi-agent reasoning loop: Curator -> Generator -> Critic -> Evidence Gate -> Planner, in code.

The Curator reasons over the worker's gaps and selects the assessment target; the Generator authors a
grounded competency item; an advisory Critic AGENT reviews item quality; the deterministic Evidence
Gate decides whether it passes; the Planner reasons an advisory, capacity- and accessibility-aware
learning plan around the full gap. Agents reason; code notarizes.

The trust boundary is unchanged: the loop's `corpus ∩ retrieved` gate, the N=3 fail-closed
ABSTAIN, and the credential's causal-spine assertion all stay exactly as they were. The Curator
adds a STRICTER fail-closed path (no assessable gap -> no loop, no mint), and the Planner is
advisory — it never feeds the mint. Each agent step is an OpenTelemetry span (no-op unless
configured) so the whole reasoning chain is one observable trace.
"""
from __future__ import annotations

from ..iq import traversal
from ..iq import derivation as dv
from ..iq.models import Edge, Ontology, Role, Worker
from ..obs import tracing
from .adaptive import AdaptiveController
from .conductor import Orchestrator
from .critic import Critic
from .curator import Curator
from .generator import Generator
from .insights import ProgramInsightsAgent
from .loop import run_assessment_loop
from .planner import Planner
from .types import LoopResult, MultiAgentResult, ProgramInsights
from .evidence_gate import EvidenceGate


def _run_insights(insights: ProgramInsightsAgent | None, worker: Worker, role: Role,
                  onto: Ontology) -> ProgramInsights | None:
    """Run the read-only Program Insights agent (advisory, OFF the mint path). Nothing it returns is
    passed to mint or the Evidence Gate; it is a sibling of the Planner, not part of the trust chain."""
    if insights is None:
        return None
    with tracing.span("insights", **{"pf.worker": worker.id}) as ins_span:
        program_insights = insights.analyze(worker, role, onto)
        ins_span.set(**{"pf.cohort_n": program_insights.worker_comparison.get("n_cohort"),
                        "pf.source": program_insights.source})
    return program_insights


def run_multiagent(worker: Worker, onto: Ontology, edges: list[Edge],
                   curator: Curator, generator: Generator, evidence_gate: EvidenceGate,
                   planner: Planner, critic: Critic | None = None,
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
            # No assessable gap -> nothing to certify. Fail closed: no loop, no mint.
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
        # The production grounding neighborhood for THIS skill (certgap + requires + certifies +
        # corpus cards) — replaces the demo's old hardcoded `corpus::AZ-204` shortcut.
        allowed = traversal.approved_refs(worker, skill, onto)

        loop = run_assessment_loop(driving, skill, allowed, generator, evidence_gate,
                                   critic=critic, adaptive=adaptive)
        root.set(**{"pf.status": loop.status, "pf.attempts": loop.attempts})

        with tracing.span("plan", **{"pf.worker": worker.id,
                                     "pf.gap_skills": len(decision.ranking)}) as plan_span:
            plan = planner.plan(worker, decision.ranking, onto)
            plan_span.set(**{"pf.weeks": plan.weeks, "pf.total_hours": plan.total_hours,
                             "pf.corrected": plan.corrected})

        # Program Insights: read-only cohort/program reasoning, advisory and OFF the mint trust path.
        program_insights = _run_insights(insights, worker, role, onto)

        return MultiAgentResult(curator=decision, loop=loop, plan=plan, insights=program_insights)


def run_orchestrated_multiagent(worker: Worker, onto: Ontology, edges: list[Edge],
                                orchestrator: Orchestrator,
                                curator: Curator, generator: Generator,
                                evidence_gate: EvidenceGate, planner: Planner,
                                critic: Critic | None = None,
                                adaptive: AdaptiveController | None = None,
                                insights: ProgramInsightsAgent | None = None) -> MultiAgentResult:
    """Orchestrator-agent-driven route with deterministic validation.

    The Orchestrator reasons over the route/target; code validates and executes. The Evidence Gate
    and mint trust boundary is unchanged: `run_assessment_loop` remains the only producer of
    `status="verified"`, and this function never mints.
    """
    role = onto.roles[worker.target_role_id]
    with tracing.span("orchestrated_multiagent",
                      **{"pf.worker": worker.id, "pf.target_role": role.id}) as root:
        with tracing.span("orchestrator.initial", **{"pf.worker": worker.id}) as orch_span:
            initial_plan = orchestrator.plan(worker, role, onto)
            orch_span.set(**{"pf.steps": len(initial_plan.steps),
                             "pf.corrected": initial_plan.corrected})

        with tracing.span("curate", **{"pf.worker": worker.id}) as cur_span:
            decision = curator.curate(worker, role, onto)
            cur_span.set(**{"pf.admissible": len(decision.admissible_skill_ids),
                            "pf.chosen": decision.chosen_skill_id or "(none)",
                            "pf.corrected": decision.corrected})

        with tracing.span("orchestrator.route", **{"pf.worker": worker.id}) as route_span:
            route_plan = orchestrator.plan(worker, role, onto,
                                           curator_chosen_skill_id=decision.chosen_skill_id)
            target_skill_id = route_plan.first_target_skill_id()
            route_span.set(**{"pf.steps": len(route_plan.steps),
                              "pf.target_skill": target_skill_id or "(none)",
                              "pf.corrected": route_plan.corrected})

        if not decision.chosen_skill_id or not target_skill_id:
            root.set(**{"pf.status": "abstained", "pf.reason": "orchestrator_no_assessment"})
            root.event("abstained.orchestrator_no_assessment")
            loop = LoopResult(status="abstained", driving_edge_id="", targeted_skill_id="",
                              attempts=0, item=None, verdict=None, transcript=[], citations=())
            with tracing.span("plan", **{"pf.worker": worker.id}):
                plan = planner.plan(worker, decision.ranking, onto)
            program_insights = _run_insights(insights, worker, role, onto)
            return MultiAgentResult(curator=decision, loop=loop, plan=plan,
                                    insights=program_insights,
                                    orchestrator={
                                        "initial": initial_plan.to_doc(),
                                        "route": route_plan.to_doc(),
                                        "selected_target_skill_id": target_skill_id,
                                    })

        skill = onto.skills[target_skill_id]
        driving_edge_id = dv.certgap_edge_id(worker.id, target_skill_id)
        driving = next(e for e in traversal.cert_gap_edges(worker, onto, edges)
                       if e.id == driving_edge_id)
        allowed = traversal.approved_refs(worker, skill, onto)

        loop = run_assessment_loop(driving, skill, allowed, generator, evidence_gate,
                                   critic=critic, adaptive=adaptive)
        root.set(**{"pf.status": loop.status, "pf.attempts": loop.attempts,
                    "pf.orchestrator_target": target_skill_id})

        with tracing.span("plan", **{"pf.worker": worker.id,
                                     "pf.gap_skills": len(decision.ranking)}) as plan_span:
            plan = planner.plan(worker, decision.ranking, onto)
            plan_span.set(**{"pf.weeks": plan.weeks, "pf.total_hours": plan.total_hours,
                             "pf.corrected": plan.corrected})

        program_insights = _run_insights(insights, worker, role, onto)
        return MultiAgentResult(curator=decision, loop=loop, plan=plan, insights=program_insights,
                                orchestrator={
                                    "initial": initial_plan.to_doc(),
                                    "route": route_plan.to_doc(),
                                    "selected_target_skill_id": target_skill_id,
                                })
