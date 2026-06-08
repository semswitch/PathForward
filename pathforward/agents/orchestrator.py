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
from ..iq.models import Edge, Ontology, Worker
from ..obs import tracing
from .critic import Critic
from .curator import Curator
from .generator import Generator
from .loop import run_assessment_loop
from .planner import Planner
from .types import LoopResult, MultiAgentResult
from .evidence_gate import EvidenceGate


def run_multiagent(worker: Worker, onto: Ontology, edges: list[Edge],
                   curator: Curator, generator: Generator, evidence_gate: EvidenceGate,
                   planner: Planner, critic: Critic | None = None) -> MultiAgentResult:
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
            return MultiAgentResult(curator=decision, loop=loop, plan=plan)

        skill = onto.skills[decision.chosen_skill_id]
        driving = next(e for e in traversal.cert_gap_edges(worker, onto, edges)
                       if e.id == decision.chosen_edge_id)
        # The production grounding neighborhood for THIS skill (certgap + requires + certifies +
        # corpus cards) — replaces the demo's old hardcoded `corpus::AZ-204` shortcut.
        allowed = traversal.approved_refs(worker, skill, onto)

        loop = run_assessment_loop(driving, skill, allowed, generator, evidence_gate, critic=critic)
        root.set(**{"pf.status": loop.status, "pf.attempts": loop.attempts})

        with tracing.span("plan", **{"pf.worker": worker.id,
                                     "pf.gap_skills": len(decision.ranking)}) as plan_span:
            plan = planner.plan(worker, decision.ranking, onto)
            plan_span.set(**{"pf.weeks": plan.weeks, "pf.total_hours": plan.total_hours,
                             "pf.corrected": plan.corrected})

        return MultiAgentResult(curator=decision, loop=loop, plan=plan)
