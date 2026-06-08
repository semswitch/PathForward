"""PathForward as a Microsoft Agent Framework Workflow (P7) — the reasoning chain expressed as an
explicit graph, with the trust boundary (the deterministic **assessment loop / Evidence Gate** and
the credential **mint**) as code executor nodes that every credential-bearing path MUST traverse.

Two layers are deliberately separated so the trust proof never depends on a preview SDK:

1. A framework-AGNOSTIC declarative spec (`WorkflowGraph`) — the single source of truth for the
   topology. Pure stdlib; imports with no third-party dependency. The "no agent can route to the
   credential without passing the deterministic gate" property is a **graph-shape invariant** over
   this spec, proven offline by `tests/test_workflow_graph.py`. Per the plan (§9) and ADR 009 this
   is a *developer-graph property, proven by a graph-shape test* — NOT a framework guarantee
   (`WorkflowBuilder.build()` validates type-compatibility/connectivity, not our trust invariant).

2. A live ADOPT-LATER adapter (`build_foundry_workflow`, in `workflow_foundry.py`) that PROJECTS
   that exact spec onto `agent_framework.WorkflowBuilder` — the assessment loop and the mint as
   deterministic `Executor`/`@handler` nodes, the reasoning steps as executors that delegate to our
   existing agents through the `LLMClient` seam, and the mint approval as a human-in-the-loop
   `ctx.request_info()` step. `agent_framework` is imported LAZILY (the live module is only loaded
   from inside `build_foundry_workflow`), so THIS module imports — and the offline suite stays
   green — even though `agent-framework` is not installed here.

`run_multiagent` (`orchestrator.py`) remains the always-green in-process spine; this Workflow track
is a parallel, flag-gated (`PF_WORKFLOW`) projection of the SAME chain, never a replacement.

Microsoft Agent Framework facts verified via the Learn MCP (2026-06-08):
  - The Python package is **GA at 1.0.0** (released 2026-04-02); `pip install agent-framework`
    (no `--pre`), import `agent_framework`. Core is `agent-framework-core`; the Foundry provider is
    `agent-framework-foundry` (`agent_framework.foundry`; the old `agent-framework-azure-ai` was
    removed in 1.0.0). So the deferral is NOT "preview/not-GA" — it is that the SDK is not
    provisioned in THIS environment AND that, by design, the credential trust spine must not
    hard-depend on the orchestrator (we keep `run_multiagent` canonical). See ADR 009.
  - Execution is a deterministic Pregel/BSP superstep model ("given the same input, the workflow
    always executes in the same order") — compatible with a code-notarized trust gate.
    Source: learn.microsoft.com/agent-framework/workflows/workflows.

Trust invariants this module makes structural (proven over the spec by the test, see `trust_audit`):
  T1  the `assess` and `mint` nodes are deterministic EXECUTOR nodes — never agents.
  T2  `assess` is a cut vertex on every start->`mint` path (remove it and `mint` is unreachable):
      there is NO path to the credential that bypasses the deterministic assessment/Evidence Gate.
  T3  `mint` has no AGENT predecessor — no LLM node can write the credential.
  T4  no AGENT node reaches `mint` without passing `assess` (the Curator reaches the credential only
      via the gate; the advisory `plan`/`insights` cannot reach it at all).
  T5  the assess executor's numeric oracle is `LocalNumericChecker` (code), never a model-backed
      analyst (additionally enforced at construction by `EvidenceGate.__init__`, ADR 008).
  T6  `mint` is reachable out of `assess` ONLY on the `verified` branch; the `abstained` branch is
      fail-closed (routes to ABSTAIN, never the credential).

Honest design note (ADR 009): the assessment loop is ONE deterministic executor that delegates to
the existing `run_assessment_loop`, rather than decomposing generate/critic/gate into separate
nodes. That decomposition was the plan's (§9) letter, but it would create a SECOND writer of
`status="verified"` (the workflow gate executor + the `LoopResult` `mint` requires), breaking the
single-writer invariant. When the plan's letter conflicts with a prime invariant, the invariant
wins: `status="verified"` stays written in exactly one place (`loop.py`), and the Workflow reuses it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

PF_WORKFLOW_ENV = "PF_WORKFLOW"


def workflow_enabled() -> bool:
    """True iff the ADOPT-LATER Agent Framework Workflow track is explicitly switched on. Off by
    default: the in-process `run_multiagent` is the always-green path; this flag opts a live run into
    the GA-but-not-provisioned Workflow projection."""
    return os.environ.get(PF_WORKFLOW_ENV, "").strip().lower() in ("1", "true", "yes", "on")


# --------------------------------------------------------------------------------------------------
# Layer 1 — the framework-agnostic declarative spec (single source of truth for the topology)
# --------------------------------------------------------------------------------------------------

class NodeKind(str, Enum):
    AGENT = "agent"                # an LLM reasoning step — proposes; structurally cannot notarize
    EXECUTOR = "executor"          # deterministic code — the trust boundary (assess loop, mint)
    REQUEST_INFO = "request_info"  # human-in-the-loop (the mint approval; require_approval: always)
    TERMINAL = "terminal"          # a workflow output sink (yields the final value)


class Trust(str, Enum):
    TRUST = "trust"                # on the credential trust path (assess, approval, mint)
    ADVISORY = "advisory"          # reasons, but never on the credential path
    SINK = "sink"                  # a terminal output


@dataclass(frozen=True)
class WorkflowNode:
    id: str
    kind: NodeKind
    title: str
    trust: Trust = Trust.ADVISORY
    detail: str = ""               # audit note (e.g. the deterministic impl behind an EXECUTOR)

    def to_doc(self) -> dict:
        return {"id": self.id, "kind": self.kind.value, "title": self.title,
                "trust": self.trust.value, "detail": self.detail}


@dataclass(frozen=True)
class WorkflowEdge:
    source: str
    target: str
    condition: str = ""            # "" == a direct edge; otherwise a labeled condition
    note: str = ""

    def to_doc(self) -> dict:
        return {"source": self.source, "target": self.target,
                "condition": self.condition, "note": self.note}


class WorkflowGraphError(ValueError):
    """Raised when a WorkflowGraph is structurally malformed (dangling edge, unknown start)."""


@dataclass
class WorkflowGraph:
    """A directed graph of reasoning + deterministic nodes. Pure data + pure graph algorithms — no
    dependency on `agent_framework`. The no-bypass trust proof lives here."""
    nodes: tuple[WorkflowNode, ...]
    edges: tuple[WorkflowEdge, ...]
    start: str

    def __post_init__(self) -> None:
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise WorkflowGraphError(f"duplicate node id(s): {dupes}")
        idset = set(ids)
        if self.start not in idset:
            raise WorkflowGraphError(f"start node {self.start!r} is not a node")
        for e in self.edges:
            if e.source not in idset or e.target not in idset:
                raise WorkflowGraphError(f"edge references unknown node: {e.source!r}->{e.target!r}")

    # --- introspection (used by the no-bypass test and the live projection) ---
    def node(self, nid: str) -> WorkflowNode:
        for n in self.nodes:
            if n.id == nid:
                return n
        raise KeyError(nid)

    def out_edges(self, nid: str) -> tuple[WorkflowEdge, ...]:
        return tuple(e for e in self.edges if e.source == nid)

    def in_edges(self, nid: str) -> tuple[WorkflowEdge, ...]:
        return tuple(e for e in self.edges if e.target == nid)

    def successors(self, nid: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(e.target for e in self.out_edges(nid)))

    def predecessors(self, nid: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(e.source for e in self.in_edges(nid)))

    def nodes_of_kind(self, kind: NodeKind) -> tuple[WorkflowNode, ...]:
        return tuple(n for n in self.nodes if n.kind == kind)

    def reachable_from(self, src: str, *, excluding: tuple[str, ...] = ()) -> frozenset[str]:
        """Nodes reachable from `src` (cycle-safe), optionally treating `excluding` nodes as removed
        (used to prove a node is a cut vertex)."""
        block = set(excluding)
        if src in block:
            return frozenset()
        seen: set[str] = {src}
        stack = [src]
        while stack:
            cur = stack.pop()
            for e in self.out_edges(cur):
                if e.target in block or e.target in seen:
                    continue
                seen.add(e.target)
                stack.append(e.target)
        return frozenset(seen)

    def reaches(self, src: str, dst: str, *, excluding: tuple[str, ...] = ()) -> bool:
        return dst in self.reachable_from(src, excluding=excluding)

    def is_cut_vertex_for(self, cut: str, src: str, dst: str) -> bool:
        """True iff every path from `src` to `dst` passes through `cut` — i.e. `dst` is reachable
        from `src` normally, but NOT once `cut` is removed. Cycle-safe (no path enumeration)."""
        return self.reaches(src, dst) and not self.reaches(src, dst, excluding=(cut,))

    def to_doc(self) -> dict:
        return {"start": self.start,
                "nodes": [n.to_doc() for n in self.nodes],
                "edges": [e.to_doc() for e in self.edges]}

    def to_mermaid(self) -> str:
        """A Mermaid flowchart of the graph — node shape by kind, edge label by condition. Used by
        the demo render and the architecture diagram (the Workflows-track artifact)."""
        shape = {
            NodeKind.AGENT: ("([", "])"),          # stadium — a reasoning agent
            NodeKind.EXECUTOR: ("[", "]"),         # rectangle — deterministic code (assess/mint)
            NodeKind.REQUEST_INFO: ("{{", "}}"),   # hexagon — human-in-the-loop
            NodeKind.TERMINAL: ("((", "))"),       # circle — an output sink
        }
        lines = ["flowchart TD"]
        for n in self.nodes:
            o, c = shape[n.kind]
            lock = " [TRUST]" if n.trust == Trust.TRUST else ""
            lines.append(f"    {n.id}{o}\"{n.title}{lock}\"{c}")
        for e in self.edges:
            arrow = f"-- {e.condition} -->" if e.condition else "-->"
            lines.append(f"    {e.source} {arrow} {e.target}")
        return "\n".join(lines)


# --------------------------------------------------------------------------------------------------
# The canonical PathForward graph (the SAME chain run_multiagent runs, drawn as a graph)
# --------------------------------------------------------------------------------------------------

# Node ids (stable; referenced by the trust test and the live projection).
N_CURATE = "curate"
N_ASSESS = "assess"        # the deterministic assessment loop (owns the Evidence Gate)
N_APPROVAL = "approval"
N_MINT = "mint"
N_PLAN = "plan"
N_INSIGHTS = "insights"
N_ABSTAIN = "abstain"
N_ISSUED = "issued"
N_ADVISORY_DONE = "advisory_done"

# Edge condition labels (symbolic; the deterministic executors own the real predicates + the N=3
# attempt cap inside run_assessment_loop). The trust test reasons over the labeled topology.
C_HAS_GAP = "assessable gap"
C_NO_GAP = "no assessable gap"
C_VERIFIED = "assess: verified"
C_ABSTAINED = "assess: abstained (fail-closed)"
C_APPROVED = "human: approve"
C_REFUSED = "human: refuse"


def build_pathforward_graph(*, include_hitl: bool = True) -> WorkflowGraph:
    """Build the canonical PathForward workflow graph.

    Curator selects the target (or fails closed on no assessable gap); the deterministic assessment
    loop (`run_assessment_loop`: generate -> Critic -> Evidence Gate, capped N=3, fail-closed; the
    SOLE writer of status="verified") either verifies an item or abstains; on a verified result an
    optional human-in-the-loop approval precedes the deterministic mint. The Planner and Program
    Insights agents are advisory fan-out siblings off the Curator — they run regardless and never
    reach the mint. `include_hitl=False` collapses approval (assess -> mint directly); the no-bypass
    property (T2/T3) holds either way.
    """
    nodes: list[WorkflowNode] = [
        WorkflowNode(N_CURATE, NodeKind.AGENT, "Curator", Trust.ADVISORY,
                     "ranks the gap; choice gated to the derivation's assessable CertGap set"),
        WorkflowNode(N_ASSESS, NodeKind.EXECUTOR, "Assessment loop · Evidence Gate", Trust.TRUST,
                     "deterministic fail-closed loop (generate->Critic->Evidence Gate, capped N=3); "
                     "the SOLE writer of status='verified'; gate oracle = LocalNumericChecker (code)"),
        WorkflowNode(N_MINT, NodeKind.EXECUTOR, "Credential mint", Trust.TRUST,
                     "re-derives readiness, re-checks the causal spine; fail-closed"),
        WorkflowNode(N_PLAN, NodeKind.AGENT, "Planner", Trust.ADVISORY,
                     "advisory capacity/accessibility plan; hours+math code-owned; off mint path"),
        WorkflowNode(N_INSIGHTS, NodeKind.AGENT, "Program Insights", Trust.ADVISORY,
                     "read-only cohort narration over code-computed aggregates; off mint path"),
        WorkflowNode(N_ABSTAIN, NodeKind.TERMINAL, "ABSTAIN / escalate", Trust.SINK,
                     "fail-closed: no credential"),
        WorkflowNode(N_ISSUED, NodeKind.TERMINAL, "Credential issued", Trust.SINK,
                     "citation-backed; cites the driving CertGap edge"),
        WorkflowNode(N_ADVISORY_DONE, NodeKind.TERMINAL, "Advisory output", Trust.SINK,
                     "plan + insights (never gates the credential)"),
    ]
    edges: list[WorkflowEdge] = [
        WorkflowEdge(N_CURATE, N_ASSESS, C_HAS_GAP),
        WorkflowEdge(N_CURATE, N_ABSTAIN, C_NO_GAP, "stricter fail-closed than the loop"),
        WorkflowEdge(N_CURATE, N_PLAN, "", "advisory fan-out; runs regardless of the gate"),
        WorkflowEdge(N_ASSESS, N_ABSTAIN, C_ABSTAINED, "N=3 exhausted or no assessable item"),
        WorkflowEdge(N_MINT, N_ISSUED, ""),
        WorkflowEdge(N_PLAN, N_INSIGHTS, ""),
        WorkflowEdge(N_INSIGHTS, N_ADVISORY_DONE, ""),
    ]
    if include_hitl:
        nodes.append(WorkflowNode(N_APPROVAL, NodeKind.REQUEST_INFO, "Human approval", Trust.TRUST,
                                  "require_approval: always; ctx.request_info() (HITL)"))
        edges.append(WorkflowEdge(N_ASSESS, N_APPROVAL, C_VERIFIED))
        edges.append(WorkflowEdge(N_APPROVAL, N_MINT, C_APPROVED))
        edges.append(WorkflowEdge(N_APPROVAL, N_ABSTAIN, C_REFUSED, "a human may still refuse"))
    else:
        edges.append(WorkflowEdge(N_ASSESS, N_MINT, C_VERIFIED))
    return WorkflowGraph(nodes=tuple(nodes), edges=tuple(edges), start=N_CURATE)


# --------------------------------------------------------------------------------------------------
# The no-bypass trust audit (pure graph algorithms; the test asserts every property is True)
# --------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class TrustProperty:
    key: str
    holds: bool
    evidence: str


def trust_audit(graph: WorkflowGraph) -> tuple[TrustProperty, ...]:
    """Evaluate the no-bypass trust properties (T1-T6) over the spec. Returns one TrustProperty per
    invariant; `tests/test_workflow_graph.py` asserts all `.holds`. This is the developer-proven
    graph-shape property the plan (§9) names as the trust claim — re-checkable, not asserted."""
    try:
        assess, mint = graph.node(N_ASSESS), graph.node(N_MINT)
    except KeyError as e:  # a graph without an assess/mint node can never be trusted
        return (TrustProperty("nodes_present", False, f"missing trust node: {e}"),)
    props: list[TrustProperty] = []

    # T1 — assess and mint are deterministic EXECUTOR nodes.
    t1 = assess.kind == NodeKind.EXECUTOR and mint.kind == NodeKind.EXECUTOR
    props.append(TrustProperty("T1_assess_mint_deterministic", t1,
                               f"assess={assess.kind.value}, mint={mint.kind.value}"))

    # T2 — assess is a cut vertex on every start->mint path (remove it => mint unreachable).
    t2 = graph.is_cut_vertex_for(N_ASSESS, graph.start, N_MINT)
    props.append(TrustProperty("T2_no_path_to_mint_bypasses_gate", t2,
                               "mint reachable normally and UNreachable once assess is removed"
                               if t2 else "FAIL: mint is reachable without the assess/gate"))

    # T3 — mint has no AGENT predecessor (no LLM node writes the credential).
    agent_preds = [p for p in graph.predecessors(N_MINT) if graph.node(p).kind == NodeKind.AGENT]
    props.append(TrustProperty("T3_mint_no_agent_predecessor", not agent_preds,
                               "mint predecessors: " + (", ".join(graph.predecessors(N_MINT)) or "(none)")))

    # T4 — no AGENT node can reach the mint WITHOUT passing through assess.
    agent_ids = [n.id for n in graph.nodes if n.kind == NodeKind.AGENT]
    leakers = [a for a in agent_ids if graph.reaches(a, N_MINT, excluding=(N_ASSESS,))]
    props.append(TrustProperty("T4_no_agent_reaches_mint_without_gate", not leakers,
                               "no agent reaches the mint bypassing the gate" if not leakers
                               else f"FAIL: {leakers} reach mint without the gate"))

    # T5 — the assess executor's numeric oracle is LocalNumericChecker (named in the spec + enforced
    #      structurally by EvidenceGate.__init__; the projection wires exactly this — see test).
    t5 = "LocalNumericChecker" in assess.detail
    props.append(TrustProperty("T5_gate_oracle_is_local_numeric_checker", t5, assess.detail))

    # T6 — EVERY assess out-edge that can reach the mint must be the 'verified' branch (and at least
    #      one does); any other label that reaches the credential (e.g. an abstained or unlabeled
    #      shortcut) fails. This mirrors `test_mint_only_reachable_via_the_verified_branch` exactly so
    #      the SHIPPED audit (the demo/smoke trust gate) is as strong as the unit test — not weaker.
    mint_bound = [e for e in graph.out_edges(N_ASSESS)
                  if e.target == N_MINT or graph.reaches(e.target, N_MINT)]
    mislabeled = [e for e in mint_bound if e.condition != C_VERIFIED]
    t6 = bool(mint_bound) and not mislabeled
    props.append(TrustProperty("T6_mint_only_via_verified_branch", t6,
                               "every assess->mint path is the 'verified' branch (abstained is fail-closed)"
                               if t6 else "FAIL: non-'verified' assess edge(s) reach the mint: "
                                          f"{[(e.target, e.condition) for e in mislabeled]}"))
    return tuple(props)


def trust_holds(graph: WorkflowGraph) -> bool:
    return all(p.holds for p in trust_audit(graph))


# --------------------------------------------------------------------------------------------------
# Layer 2a — the projection plan (the live adapter's contract, testable offline WITHOUT the SDK)
# --------------------------------------------------------------------------------------------------

# How each node kind is realized as an Agent Framework executor. The assess loop + mint are ALWAYS
# deterministic `Executor`/`@handler` nodes — that is the non-negotiable trust boundary.
EXECUTOR_TYPE = {
    NodeKind.AGENT: "agent_executor",            # delegates to our agent via the LLMClient seam
    NodeKind.EXECUTOR: "deterministic_handler",  # pure code Executor (the trust boundary)
    NodeKind.REQUEST_INFO: "request_info",       # ctx.request_info() + @response_handler (HITL)
    NodeKind.TERMINAL: "output_sink",            # ctx.yield_output()
}

# The deterministic implementation behind each EXECUTOR/REQUEST_INFO node (audited by the test so
# the live build can never silently substitute a model where code must decide).
IMPL_HINT = {
    N_ASSESS: "run_assessment_loop + EvidenceGate(LocalNumericChecker) — sole status='verified' writer",
    N_MINT: "credential.mint.mint (re-derives readiness, re-checks spine)",
    N_APPROVAL: "ctx.request_info() — human approval (require_approval: always)",
}


@dataclass(frozen=True)
class ExecutorRegistration:
    node_id: str
    executor_type: str
    impl_hint: str


@dataclass(frozen=True)
class EdgeRegistration:
    source: str
    target: str
    condition: str


@dataclass(frozen=True)
class ProjectionPlan:
    """A pure description of the `WorkflowBuilder` calls the live adapter will make: one executor
    per node, one edge per edge, plus the start. Computing this WITHOUT `agent_framework` lets the
    offline test assert the live build covers every node + edge (the gate can never be dropped)."""
    start: str
    executors: tuple[ExecutorRegistration, ...]
    edges: tuple[EdgeRegistration, ...]

    def executor(self, node_id: str) -> ExecutorRegistration:
        for r in self.executors:
            if r.node_id == node_id:
                return r
        raise KeyError(node_id)


def project_to_builder_plan(graph: WorkflowGraph) -> ProjectionPlan:
    """Project the spec into the live adapter's build contract (pure; no SDK)."""
    executors = tuple(
        ExecutorRegistration(n.id, EXECUTOR_TYPE[n.kind],
                             IMPL_HINT.get(n.id, n.detail or n.title))
        for n in graph.nodes
    )
    edges = tuple(EdgeRegistration(e.source, e.target, e.condition) for e in graph.edges)
    return ProjectionPlan(start=graph.start, executors=executors, edges=edges)


# --------------------------------------------------------------------------------------------------
# Layer 2b — the live ADOPT-LATER adapter (agent_framework imported lazily; offline-safe)
# --------------------------------------------------------------------------------------------------

def build_foundry_workflow(graph: "WorkflowGraph | None" = None, **kwargs):
    """Project the graph onto a live `agent_framework` Workflow (the ADOPT-LATER track).

    Delegates to `pathforward.agents.workflow_foundry`, which is imported LAZILY here so this module
    (and the offline suite) never require `agent-framework`. If the SDK is absent, a clear,
    actionable RuntimeError is raised pointing at the always-green in-process fallback. Keyword args
    (worker, onto, edges, curator, generator, evidence_gate, planner, critic, insights, adaptive,
    include_hitl) are forwarded — see `workflow_foundry.build_foundry_workflow`.
    """
    if graph is None:
        graph = build_pathforward_graph(include_hitl=kwargs.get("include_hitl", True))
    try:
        from . import workflow_foundry
    except ImportError as exc:  # agent-framework not installed in this environment
        raise RuntimeError(
            "The Agent Framework Workflow track requires `agent-framework` (GA 1.0.0): "
            "`pip install agent-framework`. It is not installed here; the in-process "
            "`run_multiagent` (orchestrator.py) is the always-green fallback."
        ) from exc
    return workflow_foundry.build_foundry_workflow(graph, **kwargs)
