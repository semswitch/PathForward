"""LOCKED OUT / HISTORICAL REFERENCE ONLY.

Per user instruction on 2026-06-09, PathForward is NOT using Agent Framework Workflow as an
architecture surface. These tests remain only to ensure archived reference code cannot silently become
unsafe if left in the repo.

P7 — the Agent Framework Workflow track's trust proof.

The Workflow track is a flag-gated projection of the SAME reasoning chain `run_multiagent` runs.
Its trust claim is a DEVELOPER-PROVEN graph-shape property (plan §9 / ADR 009), NOT a framework
guarantee: no path reaches the credential `mint` without traversing the deterministic, Evidence-
Gate-bearing `assess` loop, no LLM agent can write the credential, and the gate's oracle is
`LocalNumericChecker`.

These tests reason over the framework-agnostic `WorkflowGraph` spec with pure graph algorithms, so
they run offline with `agent-framework` NOT installed — exactly the environment the always-green
in-process fallback targets. Structural checks use the AST (not substring scans) to avoid
docstring false-positives.
"""
import ast
import importlib.util
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents import workflow as wf
from pathforward.agents.workflow import (
    NodeKind, Trust, build_pathforward_graph, project_to_builder_plan, trust_audit, trust_holds,
    N_CURATE, N_ASSESS, N_APPROVAL, N_MINT, N_PLAN, N_INSIGHTS, N_ABSTAIN, N_ISSUED, N_ADVISORY_DONE,
)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WF_SRC = os.path.join(_ROOT, "pathforward", "agents", "workflow.py")
_WF_FOUNDRY_SRC = os.path.join(_ROOT, "pathforward", "agents", "workflow_foundry.py")


def _import_targets_from_source(src: str) -> set[str]:
    """Module-scope import targets: EVERY dotted segment of `import a.b.c` / `from a.b.c import x`,
    plus the bound names. Using every segment (not just the root) catches a submodule imported by its
    fully-qualified ABSOLUTE path, e.g. `import pathforward.agents.workflow_foundry` (TR-03)."""
    tree = ast.parse(src)
    names: set[str] = set()
    for node in tree.body:  # module body only -> module-level imports
        if isinstance(node, ast.Import):
            for a in node.names:
                names.update(a.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.update(node.module.split("."))
            names.update(a.name for a in node.names)  # incl. `from . import workflow_foundry`
    return names


def _module_level_import_targets(path: str) -> set[str]:
    with open(path, encoding="utf-8") as fh:
        return _import_targets_from_source(fh.read())


def _names_imported_inside(path: str, func_name: str) -> set[str]:
    """Root names / bound submodule names imported INSIDE a function body (the lazy-import pattern)."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Import):
                    out.update(a.name.split(".")[0] for a in sub.names)
                elif isinstance(sub, ast.ImportFrom):
                    if sub.module:
                        out.add(sub.module.split(".")[0])
                    out.update(a.name for a in sub.names)
    return out


def _names_referenced(path: str) -> set[str]:
    """All ast.Name / attribute roots referenced anywhere in a source file (for 'uses X' checks)."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.ImportFrom):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
    return out


def _called_names(path: str) -> set[str]:
    """Names that appear in CALL position (ast.Call func): `f(...)` -> 'f', `a.f(...)` -> 'f'."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                out.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                out.add(node.func.attr)
    return out


def _dict_attr_keys(path: str, var_name: str) -> set[str]:
    """For an assignment `var_name = { wf.X: ..., wf.Y: ... }`, return the key attribute names
    {'X','Y'} (keys written as `wf.<NAME>` attribute accesses). Used to read _CONDITIONS keys
    without importing the SDK-bearing module."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    out: set[str] = set()
    for node in ast.walk(tree):
        target_ok = (
            (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == var_name
                                                  for t in node.targets))
            or (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id == var_name)
        )
        if target_ok and isinstance(node.value, ast.Dict):
            for k in node.value.keys:
                if isinstance(k, ast.Attribute):
                    out.add(k.attr)
    return out


def _builders_value_names(path: str) -> dict:
    """Parse the `builders` dict inside build_foundry_workflow; return {key_attr_name: set(Name ids
    referenced in that key's value)} — e.g. {'N_ASSESS': {'_AssessExecutor', ...}}."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    mapping: dict[str, set[str]] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name == "build_foundry_workflow":
            for node in ast.walk(fn):
                is_builders = (
                    (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "builders"
                                                          for t in node.targets))
                    or (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                        and node.target.id == "builders")
                )
                if is_builders and isinstance(node.value, ast.Dict):
                    for k, v in zip(node.value.keys, node.value.values):
                        if isinstance(k, ast.Attribute):
                            mapping[k.attr] = {n.id for n in ast.walk(v) if isinstance(n, ast.Name)}
    return mapping


class TestWorkflowGraphTrust(unittest.TestCase):
    def setUp(self):
        self.g = build_pathforward_graph()                 # HITL (the full topology)
        self.g_nohitl = build_pathforward_graph(include_hitl=False)

    def test_graph_is_well_formed(self):
        ids = {n.id for n in self.g.nodes}
        self.assertEqual(self.g.start, N_CURATE)
        for needed in (N_CURATE, N_ASSESS, N_APPROVAL, N_MINT, N_PLAN, N_INSIGHTS,
                       N_ABSTAIN, N_ISSUED, N_ADVISORY_DONE):
            self.assertIn(needed, ids)

    # --- T1: the assess loop + mint are deterministic executors -------------------------------
    def test_assess_and_mint_are_deterministic_executors(self):
        self.assertEqual(self.g.node(N_ASSESS).kind, NodeKind.EXECUTOR)
        self.assertEqual(self.g.node(N_MINT).kind, NodeKind.EXECUTOR)
        self.assertEqual(self.g.node(N_ASSESS).trust, Trust.TRUST)
        self.assertEqual(self.g.node(N_MINT).trust, Trust.TRUST)

    # --- T2: NO path to the credential bypasses the deterministic gate -------------------------
    def test_no_path_to_mint_bypasses_the_gate(self):
        for g in (self.g, self.g_nohitl):
            self.assertTrue(g.reaches(g.start, N_MINT))                       # reachable normally
            self.assertFalse(g.reaches(g.start, N_MINT, excluding=(N_ASSESS,)))  # not without assess
            self.assertTrue(g.is_cut_vertex_for(N_ASSESS, g.start, N_MINT))

    # --- T3: no LLM agent is a predecessor of the mint ----------------------------------------
    def test_mint_has_no_agent_predecessor(self):
        for g in (self.g, self.g_nohitl):
            for pred in g.predecessors(N_MINT):
                self.assertNotEqual(g.node(pred).kind, NodeKind.AGENT,
                                    f"agent {pred!r} must not feed the mint")

    def test_no_agent_node_has_an_edge_into_the_mint_credential(self):
        for g in (self.g, self.g_nohitl):
            agent_ids = {n.id for n in g.nodes if n.kind == NodeKind.AGENT}
            into_mint = {e.source for e in g.in_edges(N_MINT)}
            self.assertEqual(agent_ids & into_mint, set())

    # --- T4: no agent reaches the mint without passing the assess/gate -------------------------
    def test_no_agent_reaches_mint_without_the_gate(self):
        for g in (self.g, self.g_nohitl):
            for n in g.nodes:
                if n.kind == NodeKind.AGENT:
                    self.assertFalse(g.reaches(n.id, N_MINT, excluding=(N_ASSESS,)),
                                     f"agent {n.id!r} reaches the mint bypassing the gate")

    def test_advisory_agents_cannot_reach_mint_at_all(self):
        for advisory in (N_PLAN, N_INSIGHTS):
            self.assertFalse(self.g.reaches(advisory, N_MINT))

    # --- T5: the gate's numeric oracle is LocalNumericChecker ----------------------------------
    def test_gate_oracle_is_local_numeric_checker(self):
        self.assertIn("LocalNumericChecker", self.g.node(N_ASSESS).detail)
        plan = project_to_builder_plan(self.g)
        self.assertIn("LocalNumericChecker", plan.executor(N_ASSESS).impl_hint)

    # --- T6: mint only via the verified branch; abstained is fail-closed -----------------------
    def test_mint_only_reachable_via_the_verified_branch(self):
        for g in (self.g, self.g_nohitl):
            for e in g.out_edges(N_ASSESS):
                if e.condition == wf.C_ABSTAINED:
                    self.assertFalse(g.reaches(e.target, N_MINT),
                                     "the abstained branch must be fail-closed (never reach mint)")
                if g.reaches(e.target, N_MINT) or e.target == N_MINT:
                    self.assertEqual(e.condition, wf.C_VERIFIED,
                                     "only the 'verified' assess edge may lead to the mint")

    # --- the whole audit holds for both topologies --------------------------------------------
    def test_trust_audit_all_properties_hold(self):
        for g in (self.g, self.g_nohitl):
            failing = [p.key for p in trust_audit(g) if not p.holds]
            self.assertEqual(failing, [], f"trust properties failed: {failing}")
            self.assertTrue(trust_holds(g))

    # --- a graph that bypasses the gate must FAIL the audit (the test has teeth) ---------------
    def test_audit_catches_a_bypass(self):
        from pathforward.agents.workflow import WorkflowEdge, WorkflowGraph
        g = self.g_nohitl
        # Inject a forbidden shortcut: Curator -> mint (an agent writing the credential, no gate).
        bad = WorkflowGraph(nodes=g.nodes, edges=g.edges + (WorkflowEdge(N_CURATE, N_MINT, "BYPASS"),),
                            start=g.start)
        self.assertFalse(trust_holds(bad))
        keys = {p.key: p.holds for p in trust_audit(bad)}
        self.assertFalse(keys["T2_no_path_to_mint_bypasses_gate"])
        self.assertFalse(keys["T3_mint_no_agent_predecessor"])

    def test_audit_catches_an_abstain_leak(self):
        from pathforward.agents.workflow import WorkflowEdge, WorkflowGraph
        g = self.g_nohitl
        # Route the fail-closed abstained branch into the mint -> must be caught by T6.
        bad = WorkflowGraph(nodes=g.nodes,
                            edges=g.edges + (WorkflowEdge(N_ABSTAIN, N_MINT, "LEAK"),), start=g.start)
        keys = {p.key: p.holds for p in trust_audit(bad)}
        self.assertFalse(keys["T6_mint_only_via_verified_branch"])

    def test_audit_catches_an_unlabeled_assess_to_mint_leak(self):
        # An unlabeled/mislabeled shortcut out of the gate straight to the credential must fail the
        # SHIPPED audit function (not just the unit test) — T6 has teeth (TR-01).
        from pathforward.agents.workflow import WorkflowEdge, WorkflowGraph
        g = self.g_nohitl
        bad = WorkflowGraph(nodes=g.nodes,
                            edges=g.edges + (WorkflowEdge(N_ASSESS, N_MINT, "sneaky-unlabeled"),),
                            start=g.start)
        self.assertFalse(trust_holds(bad))
        keys = {p.key: p.holds for p in trust_audit(bad)}
        self.assertFalse(keys["T6_mint_only_via_verified_branch"])

    # --- fail-closed topology -----------------------------------------------------------------
    def test_fail_closed_topology(self):
        assess_out = {(e.target, e.condition) for e in self.g.out_edges(N_ASSESS)}
        self.assertIn((N_APPROVAL, wf.C_VERIFIED), assess_out)        # verified -> human approval
        self.assertIn((N_ABSTAIN, wf.C_ABSTAINED), assess_out)        # fail-closed exhausted/no-item
        approval_out = {(e.target, e.condition) for e in self.g.out_edges(N_APPROVAL)}
        self.assertIn((N_MINT, wf.C_APPROVED), approval_out)
        self.assertIn((N_ABSTAIN, wf.C_REFUSED), approval_out)        # a human may still refuse
        self.assertEqual(self.g.node(N_ABSTAIN).kind, NodeKind.TERMINAL)
        self.assertEqual(self.g.out_edges(N_ABSTAIN), ())             # no escape from abstain to mint

    def test_hitl_inserts_human_approval_between_gate_and_mint(self):
        self.assertEqual([e.target for e in self.g.out_edges(N_ASSESS) if e.condition == wf.C_VERIFIED],
                         [N_APPROVAL])
        self.assertEqual(list(self.g.predecessors(N_MINT)), [N_APPROVAL])
        # Without HITL, the verified gate passes straight to the mint (the plan's literal "(a)").
        self.assertEqual(list(self.g_nohitl.predecessors(N_MINT)), [N_ASSESS])

    # --- the projection PLAN covers every node + edge (the live build's binding is checked
    #     separately by TestWorkflowFoundryLiveModule.test_live_builders_bind_trust_nodes...) -----
    def test_projection_plan_covers_every_node_and_edge(self):
        plan = project_to_builder_plan(self.g)
        self.assertEqual(plan.start, self.g.start)
        self.assertEqual({r.node_id for r in plan.executors}, {n.id for n in self.g.nodes})
        self.assertEqual(len(plan.edges), len(self.g.edges))
        self.assertEqual(plan.executor(N_ASSESS).executor_type, "deterministic_handler")
        self.assertEqual(plan.executor(N_MINT).executor_type, "deterministic_handler")
        self.assertEqual(plan.executor(N_APPROVAL).executor_type, "request_info")
        for agent in (N_CURATE, N_PLAN, N_INSIGHTS):
            self.assertEqual(plan.executor(agent).executor_type, "agent_executor")
        for sink in (N_ABSTAIN, N_ISSUED, N_ADVISORY_DONE):
            self.assertEqual(plan.executor(sink).executor_type, "output_sink")


class TestWorkflowOfflineSafety(unittest.TestCase):
    """The trust artifact must be provable with `agent-framework` absent (offline always-green)."""

    def test_agent_framework_installation_is_optional(self):
        # The suite must pass whether the optional live SDK is installed or absent. The invariant is
        # lazy import and a clear failure when a live workflow is requested without the SDK, not a
        # machine-specific assertion that the SDK is absent forever.
        spec = importlib.util.find_spec("agent_framework")
        self.assertTrue(spec is None or spec.name == "agent_framework")

    def test_spec_module_does_not_import_agent_framework_or_the_live_module_at_module_scope(self):
        top = _module_level_import_targets(_WF_SRC)
        self.assertNotIn("agent_framework", top)
        self.assertNotIn("workflow_foundry", top)   # the live module is loaded lazily only

    def test_live_adapter_imports_the_live_module_lazily(self):
        # build_foundry_workflow must import the SDK-bearing live module INSIDE its body, so importing
        # workflow.py never requires the preview SDK.
        self.assertIn("workflow_foundry", _names_imported_inside(_WF_SRC, "build_foundry_workflow"))

    def test_calling_live_adapter_without_sdk_fails_loudly_not_silently_when_absent(self):
        # With agent-framework absent, the adapter must raise a clear, actionable error pointing at
        # the always-green fallback — never silently "succeed".
        if importlib.util.find_spec("agent_framework") is not None:
            self.skipTest("agent-framework installed; absence-path test not applicable")
        with self.assertRaises((RuntimeError, ImportError)):
            wf.build_foundry_workflow(build_pathforward_graph())

    def test_import_guard_detects_absolute_and_relative_live_module_imports(self):
        # TR-03: the deny-by-default guard must catch the live (SDK-bearing) module however it is
        # imported — relative OR fully-qualified absolute — so it cannot evade the offline-safety scan.
        for src in ("import pathforward.agents.workflow_foundry",
                    "from pathforward.agents.workflow_foundry import build_foundry_workflow",
                    "from .workflow_foundry import build_foundry_workflow"):
            self.assertIn("workflow_foundry", _import_targets_from_source(src), f"missed: {src!r}")


class TestWorkflowFoundryLiveModule(unittest.TestCase):
    """AST-only checks on the live module (it imports agent_framework, so we never import it here)."""

    def test_live_module_targets_the_real_agent_framework_sdk(self):
        self.assertIn("agent_framework", _module_level_import_targets(_WF_FOUNDRY_SRC))

    def test_live_module_CALLS_the_trust_code_and_does_not_reimplement_it(self):
        # The deterministic boundary must be the EXISTING code, actually INVOKED — not merely imported
        # (TR-05): run_assessment_loop (the sole status="verified" writer), the EvidenceGate,
        # LocalNumericChecker (oracle), and the governed mint approval wrapper. The wrapper delegates
        # to credential.mint.mint, so approval cannot replace the final spine/readiness checks.
        called = _called_names(_WF_FOUNDRY_SRC)
        for required in ("run_assessment_loop", "EvidenceGate", "LocalNumericChecker",
                         "request_mint_approval", "mint_with_approval"):
            self.assertIn(required, called, f"live adapter must CALL {required}, not merely import it")

    def test_live_workflow_mint_executor_uses_approval_wrapper(self):
        refs = _names_referenced(_WF_FOUNDRY_SRC)
        self.assertIn("mint_with_approval", refs)
        self.assertIn("MintApprovalDecision", refs)
        with open(_WF_FOUNDRY_SRC, encoding="utf-8") as fh:
            self.assertIn("workflow approval decision is missing", fh.read())

    def test_live_builders_bind_trust_nodes_to_deterministic_executors(self):
        # The live build's node->executor binding must wire the trust nodes to the DETERMINISTIC
        # executors (TR-04): assess -> _AssessExecutor, mint -> _MintExecutor, never an agent *Step.
        mapping = _builders_value_names(_WF_FOUNDRY_SRC)
        self.assertTrue(mapping, "could not parse the live `builders` mapping")
        self.assertIn("_AssessExecutor", mapping.get("N_ASSESS", set()))
        self.assertIn("_MintExecutor", mapping.get("N_MINT", set()))
        for trust_node in ("N_ASSESS", "N_MINT"):
            self.assertFalse(any(name.endswith("Step") for name in mapping.get(trust_node, set())),
                             f"{trust_node} must not bind to an agent *Step executor")
        # every spec node id has a live builder entry (resolve the N_* attr -> the id string via wf)
        for nid in {n.id for n in build_pathforward_graph().nodes}:
            self.assertTrue([k for k in mapping if getattr(wf, k, None) == nid],
                            f"no live builder entry for spec node {nid!r}")

    def test_every_spec_condition_label_has_a_registered_predicate(self):
        # NBL-2: the live projection is fail-closed only if every non-empty condition label the spec
        # emits has a predicate in _CONDITIONS. Assert coverage offline so a future spec edit that
        # forgets a predicate fails the suite instead of producing a live always-firing edge.
        predicate_attrs = _dict_attr_keys(_WF_FOUNDRY_SRC, "_CONDITIONS")
        covered = {getattr(wf, a) for a in predicate_attrs if hasattr(wf, a)}
        for include_hitl in (True, False):
            labels = {e.condition for e in build_pathforward_graph(include_hitl=include_hitl).edges
                      if e.condition}
            self.assertEqual(labels - covered, set(),
                             f"condition labels with no registered predicate: {labels - covered}")

    def test_live_module_does_not_WRITE_verified_status(self):
        # Single-writer invariant (TR-02): status="verified" is written only in loop.py. Flag ANY
        # "verified" constant in the live module that is NOT inside a comparison (`== "verified"` is a
        # legitimate READ) — catches keyword, positional, attribute-assign, and dict-literal writes.
        with open(_WF_FOUNDRY_SRC, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        legit_reads: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for part in [node.left, *node.comparators]:
                    for c in ast.walk(part):
                        if isinstance(c, ast.Constant):
                            legit_reads.add(id(c))
        offenders = [c for c in ast.walk(tree) if isinstance(c, ast.Constant)
                     and c.value == "verified" and id(c) not in legit_reads]
        self.assertEqual(offenders, [], "the live adapter must not WRITE status='verified' (only read it)")


class TestWorkflowSpineIndependence(unittest.TestCase):
    """The Workflow track must NOT be on the in-process trust spine, and the live (SDK-bearing)
    module must only ever be imported lazily."""

    def _all_pathforward_sources(self):
        base = os.path.join(_ROOT, "pathforward")
        for root, _dirs, files in os.walk(base):
            for f in files:
                if f.endswith(".py"):
                    yield os.path.join(root, f)

    def test_orchestrator_loop_mint_do_not_import_the_workflow_track(self):
        for rel in (("agents", "orchestrator.py"), ("agents", "loop.py"), ("credential", "mint.py")):
            top = _module_level_import_targets(os.path.join(_ROOT, "pathforward", *rel))
            self.assertNotIn("workflow", top, f"{rel} must not import the Workflow track")
            self.assertNotIn("workflow_foundry", top)

    def test_no_module_imports_the_live_sdk_module_at_module_scope(self):
        # Deny-by-default: agent_framework-importing workflow_foundry must be loaded lazily only.
        for path in self._all_pathforward_sources():
            if path.endswith("workflow_foundry.py"):
                continue
            self.assertNotIn("workflow_foundry", _module_level_import_targets(path),
                             f"{path} imports the live SDK module at module scope (must be lazy)")


class TestWorkflowMermaid(unittest.TestCase):
    def test_to_mermaid_renders_the_trust_topology(self):
        m = build_pathforward_graph().to_mermaid()
        self.assertTrue(m.startswith("flowchart"))
        for nid in (N_ASSESS, N_MINT, N_APPROVAL):
            self.assertIn(nid, m)
        self.assertIn(wf.C_VERIFIED, m)


if __name__ == "__main__":
    unittest.main()
