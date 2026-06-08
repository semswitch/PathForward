"""Live ADOPT-LATER adapter: project the PathForward workflow graph onto a Microsoft Agent Framework
`Workflow`. This module hard-imports `agent_framework` and is therefore loaded LAZILY (only from
`workflow.build_foundry_workflow`); the offline core never imports it, so the suite stays green
without `agent-framework` installed.

It is wired against the GA API (`agent-framework` 1.0.0, verified via the Microsoft Learn MCP on
2026-06-08) but is NOT run in this environment (the SDK is not provisioned). Its status mirrors
`foundry.py`'s live clients: correct-by-construction against the verified surface, exercised live by
`scripts/smoke_workflow_live.py`, never on the offline/test path.

Design (see ADR 009 + `workflow.py`):
  - The trust boundary is two DETERMINISTIC executors. `_AssessExecutor` delegates to the existing
    `run_assessment_loop` — so `status="verified"` is still written in exactly one place (`loop.py`)
    and the `corpus ∩ retrieved` anti-bluff intersection is NOT duplicated. `_MintExecutor`
    delegates to the existing `credential.mint.mint` (re-derives readiness, re-checks the spine).
  - The reasoning steps (`curate`/`plan`/`insights`) are executors that delegate to OUR agents
    through the `LLMClient` seam — this keeps the code-owned gates in `curator.py`/`planner.py` as
    the trust boundary (rather than re-expressing them as native Agent Framework agents, which would
    move gating logic out of our deterministic code). The Generator + Critic run INSIDE the
    deterministic assess loop, exactly as in-process.
  - HITL mint approval is `ctx.request_info()` + `@response_handler` (the GA Python surface; the old
    `RequestInfoExecutor`/`RequestInfoMessage`/`RequestResponse` were removed in 1.0.0b251104).

Verified GA facts (Learn MCP, 2026-06-08) load-bearing here:
  - Executors subclass `Executor`; `@handler async def h(self, msg, ctx: WorkflowContext[...]) -> None`;
    `ctx.send_message(...)` routes downstream; `ctx.yield_output(...)` emits a workflow output.
    (learn.microsoft.com/agent-framework/workflows/executors)
  - `WorkflowBuilder(start_executor=...).add_edge(src, tgt, condition=Callable[[Any], bool]).build()`
    — instances (not strings); start is a constructor arg; conditional/back edges supported; loops
    bounded by `max_iterations`. (workflows/workflows + 2026 upgrade guide PR #3693/#3781)
  - HITL: `await ctx.request_info(request_data, response_type)` + `@response_handler`; resume via
    `workflow.run(responses=...)`. (support/upgrade/requests-and-responses-upgrade-guide-python)
  - The search-grounded Generator, if expressed as a NATIVE agent, must be
    `Agent(client=FoundryChatClient(...), tools=[FoundryChatClient.get_azure_ai_search_tool(...)])`
    — NOT `FoundryAgent` (that is for portal-defined service-managed agents).
    (agent-framework/agents/providers/microsoft-foundry)

TO-VERIFY against the pinned build before a live run (the API churned across the beta cycle and the
auto-generated API-reference pages lag the conceptual docs + upgrade guide):
  - `WorkflowBuilder(start_executor=...)` constructor kwarg vs the legacy `.set_start_executor(...)`
    (we try the constructor and fall back — see `_build`).
  - `response_handler` import path and the exact `@response_handler` signature.
  - `run(responses=...)` resume shape (dict-by-request_id vs list) and `event.type` discrimination.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

# Hard SDK import — this is what makes the module live-only (loaded lazily by workflow.py).
from agent_framework import (  # type: ignore[import-not-found]  (verified GA symbols, agent-framework 1.0.0)
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)
from typing_extensions import Never

from ..credential.mint import mint
from ..credential.schema import ProofCredential
from ..iq import traversal
from ..iq.models import Edge, Ontology, Role, Worker
from .adaptive import AdaptiveController
from .critic import Critic
from .curator import Curator
from .evidence_gate import EvidenceGate
from .generator import Generator
from .insights import ProgramInsightsAgent
from .loop import run_assessment_loop
from .numeric import LocalNumericChecker
from .planner import Planner
from .types import CuratorDecision, LearningPlan, LoopResult, ProgramInsights
from . import workflow as wf


# --------------------------------------------------------------------------------------------------
# The message that flows along the graph edges (the BSP superstep payload)
# --------------------------------------------------------------------------------------------------

@dataclass
class WorkflowState:
    """The single carrier message threaded through the workflow (the orchestrator-owns-payload
    pattern, expressed as one typed message so edge conditions can route on it)."""
    worker: Worker
    role: Role
    onto: Ontology
    edges: list[Edge]
    calibration: Optional[dict] = None
    decision: Optional[CuratorDecision] = None
    skill_id: str = ""
    driving_edge_id: str = ""
    loop_result: Optional[LoopResult] = None
    plan: Optional[LearningPlan] = None
    insights: Optional[ProgramInsights] = None
    approved: Optional[bool] = None
    credential: Optional[ProofCredential] = None


def make_initial_state(worker: Worker, onto: Ontology, edges: list[Edge],
                       calibration: Optional[dict] = None) -> WorkflowState:
    return WorkflowState(worker=worker, role=onto.roles[worker.target_role_id], onto=onto,
                         edges=list(edges), calibration=calibration)


@dataclass
class MintApprovalRequest:
    """HITL payload emitted by the approval node via `ctx.request_info(...)`. Carries the state so
    the `@response_handler` can resume the credential path after a human decides."""
    worker_id: str
    skill_id: str
    driving_edge_id: str
    state: WorkflowState


# --------------------------------------------------------------------------------------------------
# Reasoning-step executors (delegate to OUR agents via the LLMClient seam; never notarize)
# --------------------------------------------------------------------------------------------------

class _CuratorStep(Executor):
    def __init__(self, curator: Curator, id: str = wf.N_CURATE):
        super().__init__(id=id)
        self._curator = curator

    @handler
    async def run(self, state: WorkflowState, ctx: WorkflowContext[WorkflowState]) -> None:
        state.decision = self._curator.curate(state.worker, state.role, state.onto)
        await ctx.send_message(state)


class _PlannerStep(Executor):
    def __init__(self, planner: Planner, id: str = wf.N_PLAN):
        super().__init__(id=id)
        self._planner = planner

    @handler
    async def run(self, state: WorkflowState, ctx: WorkflowContext[WorkflowState]) -> None:
        ranking = state.decision.ranking if state.decision else ()
        state.plan = self._planner.plan(state.worker, ranking, state.onto)
        await ctx.send_message(state)


class _InsightsStep(Executor):
    def __init__(self, insights: ProgramInsightsAgent, id: str = wf.N_INSIGHTS):
        super().__init__(id=id)
        self._insights = insights

    @handler
    async def run(self, state: WorkflowState, ctx: WorkflowContext[WorkflowState]) -> None:
        state.insights = self._insights.analyze(state.worker, state.role, state.onto)
        await ctx.send_message(state)


# --------------------------------------------------------------------------------------------------
# DETERMINISTIC trust executors (the notary boundary — pure code, no model judges itself)
# --------------------------------------------------------------------------------------------------

class _AssessExecutor(Executor):
    """The deterministic assessment loop. Delegates to the EXISTING `run_assessment_loop` so that:
      * `status="verified"` is written in exactly ONE place (loop.py) — single-writer preserved;
      * the `corpus ∩ retrieved` anti-bluff intersection is reused, not duplicated;
      * the Evidence Gate's oracle stays `LocalNumericChecker` (deterministic code).
    No LLM judges its own grounding here — the Generator/Critic agents run INSIDE the loop and the
    gate decides in code."""

    def __init__(self, generator: Generator, evidence_gate: EvidenceGate,
                 critic: Optional[Critic] = None, adaptive: Optional[AdaptiveController] = None,
                 id: str = wf.N_ASSESS):
        super().__init__(id=id)
        self._generator = generator
        self._evidence_gate = evidence_gate
        self._critic = critic
        self._adaptive = adaptive

    @handler
    async def run(self, state: WorkflowState, ctx: WorkflowContext[WorkflowState]) -> None:
        decision = state.decision
        if decision is None or not decision.chosen_skill_id:
            # Stricter fail-closed: no assessable gap -> abstained (never a verified result here).
            state.loop_result = LoopResult(status="abstained", driving_edge_id="",
                                           targeted_skill_id="", attempts=0, item=None,
                                           verdict=None, transcript=[], citations=())
            await ctx.send_message(state)
            return
        skill = state.onto.skills[decision.chosen_skill_id]
        driving = next(e for e in traversal.cert_gap_edges(state.worker, state.onto, state.edges)
                       if e.id == decision.chosen_edge_id)
        allowed = traversal.approved_refs(state.worker, skill, state.onto)
        # The SOLE writer of status="verified" — reused, not re-implemented.
        state.loop_result = run_assessment_loop(driving, skill, allowed, self._generator,
                                                self._evidence_gate, critic=self._critic,
                                                adaptive=self._adaptive)
        state.skill_id = skill.id
        state.driving_edge_id = driving.id
        await ctx.send_message(state)


class _MintExecutor(Executor):
    """The deterministic credential mint. Delegates to the existing `credential.mint.mint`, which
    re-derives readiness from the ontology and re-checks the causal spine; fail-closed on a
    non-verified loop result. Emits the credential to the `issued` sink."""

    def __init__(self, id: str = wf.N_MINT):
        super().__init__(id=id)

    @handler
    async def run(self, state: WorkflowState, ctx: WorkflowContext[ProofCredential]) -> None:
        # mint() itself raises CredentialIntegrityError unless the loop verified + spine matches.
        state.credential = mint(state.worker, state.role, state.driving_edge_id, state.skill_id,
                                state.loop_result, state.calibration)
        await ctx.send_message(state.credential)


class _ApprovalStep(Executor):
    """Human-in-the-loop mint approval (require_approval: always). Suspends the workflow via
    `ctx.request_info(...)`; on resume the `@response_handler` routes to the mint (approve) or to
    ABSTAIN (refuse). GA Python HITL surface — no RequestInfoExecutor node."""

    def __init__(self, id: str = wf.N_APPROVAL):
        super().__init__(id=id)

    @handler
    async def run(self, state: WorkflowState, ctx: WorkflowContext[WorkflowState]) -> None:
        request = MintApprovalRequest(worker_id=state.worker.id, skill_id=state.skill_id,
                                      driving_edge_id=state.driving_edge_id, state=state)
        await ctx.request_info(request_data=request, response_type=bool)

    @response_handler
    async def on_decision(self, request: MintApprovalRequest, approved: bool,
                          ctx: WorkflowContext[WorkflowState]) -> None:
        state = request.state
        state.approved = bool(approved)
        await ctx.send_message(state)


# --------------------------------------------------------------------------------------------------
# Terminal sinks (yield the workflow outputs)
# --------------------------------------------------------------------------------------------------

class _IssuedSink(Executor):
    def __init__(self, id: str = wf.N_ISSUED):
        super().__init__(id=id)

    @handler
    async def run(self, credential: ProofCredential, ctx: WorkflowContext[Never, ProofCredential]) -> None:
        await ctx.yield_output(credential)


class _AbstainSink(Executor):
    def __init__(self, id: str = wf.N_ABSTAIN):
        super().__init__(id=id)

    @handler
    async def run(self, state: WorkflowState, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(f"ABSTAIN::{state.worker.id}")


class _AdvisorySink(Executor):
    def __init__(self, id: str = wf.N_ADVISORY_DONE):
        super().__init__(id=id)

    @handler
    async def run(self, state: WorkflowState, ctx: WorkflowContext[Never, WorkflowState]) -> None:
        await ctx.yield_output(state)


# --------------------------------------------------------------------------------------------------
# Edge-condition predicates (over the WorkflowState message) keyed by the spec's condition labels
# --------------------------------------------------------------------------------------------------

def _has_gap(s: WorkflowState) -> bool:
    return bool(s.decision and s.decision.chosen_skill_id)


def _verified(s: WorkflowState) -> bool:
    return s.loop_result is not None and s.loop_result.status == "verified"


# Map each spec condition label to a deterministic predicate. The empty label "" is a direct edge.
_CONDITIONS: dict[str, Callable[[Any], bool]] = {
    wf.C_HAS_GAP: _has_gap,
    wf.C_NO_GAP: lambda s: not _has_gap(s),
    wf.C_VERIFIED: _verified,
    wf.C_ABSTAINED: lambda s: not _verified(s),
    wf.C_APPROVED: lambda s: s.approved is True,
    wf.C_REFUSED: lambda s: s.approved is not True,
}


# --------------------------------------------------------------------------------------------------
# Build the live Workflow from the spec (a faithful projection of the tested topology)
# --------------------------------------------------------------------------------------------------

def _build(start_exec: Executor, edges: list[tuple], max_iterations: int, final_output_from: list):
    """Construct + build the Workflow, defensive to the GA-vs-stale builder drift (constructor
    `start_executor=` / `final_output_from=` are GA — PR #3693 moved the fluent setters into the
    constructor; `.set_start_executor(...)` is the legacy/stale-doc shape). `final_output_from`
    designates the terminal sinks so `WorkflowRunResult.get_outputs()` surfaces their `yield_output`
    (per the GA Executors doc, undesignated yields are discarded). TO-VERIFY against the pinned build."""
    try:
        builder = WorkflowBuilder(start_executor=start_exec, max_iterations=max_iterations,
                                  final_output_from=final_output_from)
    except TypeError:  # older/stale build: fall back to the fluent start setter (no final_output_from)
        builder = WorkflowBuilder(max_iterations=max_iterations).set_start_executor(start_exec)
    for src, tgt, cond in edges:
        builder = builder.add_edge(src, tgt, condition=cond) if cond else builder.add_edge(src, tgt)
    return builder.build()


def build_foundry_workflow(graph: Optional["wf.WorkflowGraph"] = None, *,
                           curator: Optional[Curator] = None,
                           generator: Optional[Generator] = None,
                           evidence_gate: Optional[EvidenceGate] = None,
                           planner: Optional[Planner] = None,
                           critic: Optional[Critic] = None,
                           insights: Optional[ProgramInsightsAgent] = None,
                           adaptive: Optional[AdaptiveController] = None,
                           include_hitl: bool = True,
                           max_iterations: int = 16):
    """Project the PathForward graph spec onto a live `agent_framework.Workflow`.

    The Evidence-Gate-bearing assessment loop and the mint are deterministic `Executor` nodes; the
    reasoning steps delegate to the supplied agents. Defaults construct the offline fakes' live
    counterparts where omitted — the gate ALWAYS uses `EvidenceGate(LocalNumericChecker())` so the
    numeric oracle is deterministic code (ADR 008). Returns the built `Workflow`; run it with
    `workflow.run(make_initial_state(worker, onto, edges))` (see `scripts/smoke_workflow_live.py`).
    """
    if graph is None:
        graph = wf.build_pathforward_graph(include_hitl=include_hitl)
    if evidence_gate is None:
        # The trust oracle is deterministic code — never a model-backed analyst (ADR 008).
        evidence_gate = EvidenceGate(LocalNumericChecker())

    # One executor instance per spec node (the projection plan asserts full coverage offline).
    builders: dict[str, Callable[[], Executor]] = {
        wf.N_CURATE: lambda: _CuratorStep(curator) if curator else _missing("curator"),
        wf.N_ASSESS: lambda: _AssessExecutor(generator or _missing("generator"), evidence_gate,
                                             critic=critic, adaptive=adaptive),
        wf.N_PLAN: lambda: _PlannerStep(planner) if planner else _missing("planner"),
        wf.N_INSIGHTS: lambda: _InsightsStep(insights) if insights else _missing("insights"),
        wf.N_APPROVAL: _ApprovalStep,
        wf.N_MINT: _MintExecutor,
        wf.N_ISSUED: _IssuedSink,
        wf.N_ABSTAIN: _AbstainSink,
        wf.N_ADVISORY_DONE: _AdvisorySink,
    }
    execs: dict[str, Executor] = {n.id: builders[n.id]() for n in graph.nodes}

    # Fail-CLOSED projection: a non-empty condition label with no registered predicate must NOT
    # silently become an unconditional (always-firing) edge — that would be the live mirror of the
    # abstain/bypass leak the spec-side graph-shape audit forbids. Require a predicate for every
    # labeled edge (an empty label is a legitimate direct edge).
    edge_specs: list[tuple] = []
    for e in graph.edges:
        if e.condition and e.condition not in _CONDITIONS:
            raise ValueError(
                f"workflow edge {e.source}->{e.target} carries condition label {e.condition!r} with "
                f"no registered predicate in _CONDITIONS — refusing to project it as an unconditional "
                f"edge (fail-closed). Register a predicate before projecting this graph.")
        edge_specs.append((execs[e.source], execs[e.target], _CONDITIONS.get(e.condition)))

    # Designate the terminal sinks so get_outputs() surfaces their yield_output (LC-1 / ADR 009).
    final_output_from = [execs[wf.N_ISSUED], execs[wf.N_ABSTAIN], execs[wf.N_ADVISORY_DONE]]
    return _build(execs[graph.start], edge_specs, max_iterations, final_output_from)


def _missing(name: str) -> Executor:
    raise ValueError(f"build_foundry_workflow requires a `{name}` agent for the {name} node")
