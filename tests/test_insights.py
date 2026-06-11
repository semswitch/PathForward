"""Program Insights agent + cohort layer: read-only, off the credential trust path, and unable to
fabricate a statistic. The agent NARRATES; deterministic code (iq/cohort.py over derivation.py) owns
every number. These tests pin: (1) the cohort aggregates reconcile to independently recomputed
derivation values; (2) the agent's numbers come from code, not the model, even when the model lies;
(3) the Insights agent/cohort layer import neither the Evidence Gate nor mint, and the agent is
constructed with only an LLMClient; (4) the orchestrator threads insights without touching the
trust chain."""
import ast
import inspect
import json
import os
import statistics
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "pathforward")

from pathforward.agents.client import LLMResponse
from tests.fakes import FakeLLMClient           # noqa: E402
from pathforward.agents.critic import Critic                               # noqa: E402
from pathforward.agents.curator import Curator                             # noqa: E402
from pathforward.agents.generator import Generator                        # noqa: E402
from pathforward.agents.insights import ProgramInsightsAgent              # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker               # noqa: E402
from tests.code_contract_flow import run_multiagent_code_contract               # noqa: E402
from pathforward.agents.planner import Planner                            # noqa: E402
from pathforward.agents.evidence_gate import EvidenceGate                 # noqa: E402
from pathforward.iq import cohort                                         # noqa: E402
from pathforward.iq import derivation as dv                              # noqa: E402
from pathforward.iq.seed import HERO_WORKER_ID, build_seed               # noqa: E402


def _read(rel: str) -> str:
    with open(os.path.join(PKG, rel), encoding="utf-8") as fh:
        return fh.read()


def _imported_targets(rel: str) -> set[str]:
    """Every module/name a file actually IMPORTS (AST, so docstrings/comments mentioning a name are
    not mistaken for a dependency). Returns dotted module paths and imported names."""
    tree = ast.parse(_read(rel))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            out.add(mod)
            for a in node.names:
                out.add(f"{mod}.{a.name}")
                out.add(a.name)
    return out


class _LyingInsightsClient:
    """A client that returns a fabricated narrative AND fabricated numbers. The agent must ignore the
    numbers (they come from code) and keep only the narrative — proving the model cannot fabricate a
    statistic."""
    def respond(self, instructions, input, *, previous_response_id=None, schema=None):
        return LLMResponse("r", "", {"narrative": "ALL WORKERS ARE 100% READY",
                                     "worker_readiness": 9.99, "cohort_mean_readiness": 9.99,
                                     "rank": 0, "n_cohort": 99999})


class TestCohortReconcilesToDerivation(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()

    def test_role_cohort_mean_matches_derivation(self):
        for role_id, role in self.onto.roles.items():
            rc = cohort.role_cohort(self.onto, role_id)
            members = [w for w in self.onto.workers.values() if w.target_role_id == role_id]
            expected = [dv.readiness_score(w, role) for w in members]
            self.assertEqual(rc.n_workers, len(members))
            if expected:
                self.assertAlmostEqual(rc.mean_readiness, round(statistics.mean(expected), 4))
                self.assertAlmostEqual(rc.median_readiness, round(statistics.median(expected), 4))

    def test_bottleneck_gap_counts_match_derivation(self):
        role_id = "R-CLOUD"
        role = self.onto.roles[role_id]
        rc = cohort.role_cohort(self.onto, role_id)
        members = [w for w in self.onto.workers.values() if w.target_role_id == role_id]
        for sg in rc.bottleneck_skills:
            expected = sum(1 for w in members if sg.skill_id in dv.cert_gap_skill_ids(w, role))
            self.assertEqual(sg.gap_count, expected, f"gap_count drift for {sg.skill_id}")
        # bottlenecks must be sorted by gap_count descending
        counts = [s.gap_count for s in rc.bottleneck_skills]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_worker_vs_cohort_matches_derivation(self):
        wc = cohort.worker_vs_cohort(self.onto, HERO_WORKER_ID)
        worker = self.onto.workers[HERO_WORKER_ID]
        role = self.onto.roles[worker.target_role_id]
        self.assertAlmostEqual(wc.worker_readiness, dv.readiness_score(worker, role))
        members = [w for w in self.onto.workers.values() if w.target_role_id == role.id]
        readiness = [dv.readiness_score(w, role) for w in members]
        self.assertEqual(wc.n_cohort, len(members))
        self.assertAlmostEqual(wc.cohort_mean_readiness, round(statistics.mean(readiness), 4))
        self.assertEqual(wc.rank, 1 + sum(1 for r in readiness if r > wc.worker_readiness))

    def test_program_unassessable_is_exactly_the_uncertified_gaps(self):
        # S09 (Containers) is required by R-DEVOPS but certified by NO certification -> the ONLY gap
        # that cannot be certified program-wide. (S10 Kubernetes is also uncertified but is required
        # by no role, so it never appears as a gap.) Assert the exact set, not just membership.
        prog = cohort.program_aggregates(self.onto)
        self.assertEqual(prog.unassessable_gap_skill_ids, ("S09",))
        # every "unassessable" skill genuinely has no certification corpus
        for sid in prog.unassessable_gap_skill_ids:
            self.assertEqual(self.onto.certs_for_skill(sid), [])
        self.assertEqual(prog.n_workers, len(self.onto.workers))

    def test_percentile_aligns_with_rank(self):
        # rank and percentile must tell a CONSISTENT story: the least-ready worker reads ~0th
        # percentile (not mid-pack) and carries the worst rank; percentile never decreases (and rank
        # never increases) as readiness rises across the cohort.
        role_id = "R-CLOUD"
        members = [w for w in self.onto.workers.values() if w.target_role_id == role_id]
        comps = [cohort.worker_vs_cohort(self.onto, w.id) for w in members]
        by_readiness = sorted(comps, key=lambda c: c.worker_readiness)
        least = by_readiness[0]
        self.assertEqual(least.percentile, 0.0)                       # nobody is strictly below it
        self.assertEqual(least.rank, max(c.rank for c in comps))      # ...and it ranks worst
        for a, b in zip(by_readiness, by_readiness[1:]):
            self.assertLessEqual(a.percentile, b.percentile)          # monotonic with readiness
            self.assertGreaterEqual(a.rank, b.rank)                   # rank is the mirror of it


class TestInsightsAgent(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.worker = self.onto.workers[HERO_WORKER_ID]
        self.role = self.onto.roles[self.worker.target_role_id]

    def test_agent_constructed_with_only_a_client_as_required_dependency(self):
        params = inspect.signature(ProgramInsightsAgent.__init__).parameters
        self.assertEqual(list(params)[:2], ["self", "client"])
        self.assertEqual(params["client"].default, inspect._empty)
        self.assertEqual(params["skill_instructions"].default, "")

    def test_insights_reconciles_to_derivation(self):
        ins = ProgramInsightsAgent(FakeLLMClient()).analyze(self.worker, self.role, self.onto)
        # the numbers carried in ProgramInsights equal independently recomputed derivation values
        self.assertAlmostEqual(ins.worker_comparison["worker_readiness"],
                               dv.readiness_score(self.worker, self.role))
        members = [w for w in self.onto.workers.values()
                   if w.target_role_id == self.role.id]
        self.assertEqual(ins.worker_comparison["n_cohort"], len(members))
        self.assertEqual(ins.role_cohort["role_id"], self.role.id)
        self.assertEqual(ins.source, "derivation-floor")
        self.assertTrue(ins.narrative)                       # the agent produced display prose
        json.dumps(ins.to_doc())                             # serializable end to end

    def test_model_cannot_fabricate_a_statistic(self):
        # Even with a client that returns fabricated numbers, every number stays code-derived; only
        # the (display-only) narrative is taken from the model.
        ins = ProgramInsightsAgent(_LyingInsightsClient()).analyze(self.worker, self.role, self.onto)
        self.assertAlmostEqual(ins.worker_comparison["worker_readiness"],
                               dv.readiness_score(self.worker, self.role))
        self.assertEqual(ins.worker_comparison["n_cohort"],
                         len([w for w in self.onto.workers.values()
                              if w.target_role_id == self.role.id]))
        self.assertNotEqual(ins.worker_comparison["worker_readiness"], 9.99)
        self.assertEqual(ins.narrative, "ALL WORKERS ARE 100% READY")   # narrative is display-only


class TestInsightsReadOnly(unittest.TestCase):
    """The Insights agent and the cohort layer are read-only and OFF the credential trust path. We
    check the AST import graph (not substrings) so docstrings mentioning a name don't false-positive."""

    def _assert_no_import(self, rel: str, *needles: str):
        targets = _imported_targets(rel)
        for needle in needles:
            offenders = [t for t in targets if needle in t]
            self.assertEqual(offenders, [], f"{rel} must not import anything matching '{needle}'")

    def test_cohort_layer_does_not_import_gate_or_mint(self):
        self._assert_no_import("iq/cohort.py", "evidence_gate", "credential", "mint", "verifier")

    def test_insights_agent_does_not_import_gate_or_mint(self):
        self._assert_no_import("agents/insights.py", "evidence_gate", "credential", "mint", "verifier")

    def test_mint_does_not_import_insights_or_cohort(self):
        self._assert_no_import("credential/mint.py", "insights", "cohort")

    def test_evidence_gate_does_not_import_insights_or_cohort(self):
        self._assert_no_import("agents/evidence_gate.py", "insights", "cohort")


class TestOrchestratorThreadsInsights(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.edges = dv.build_all_edges(self.onto)

    def _agents(self):
        return (Curator(FakeLLMClient()), Generator(FakeLLMClient()),
                EvidenceGate(LocalNumericChecker()),
                Planner(FakeLLMClient(), LocalNumericChecker()), Critic(FakeLLMClient()),
                ProgramInsightsAgent(FakeLLMClient()))

    def test_insights_populated_when_agent_wired(self):
        worker = self.onto.workers[HERO_WORKER_ID]
        cur, gen, gate, plan, critic, ins = self._agents()
        res = run_multiagent_code_contract(worker, self.onto, self.edges, cur, gen, gate, plan,
                             critic=critic, insights=ins)
        self.assertIsNotNone(res.insights)
        self.assertEqual(res.insights.worker_id, worker.id)
        self.assertEqual(res.insights.source, "derivation-floor")
        self.assertAlmostEqual(res.insights.worker_comparison["worker_readiness"],
                               dv.readiness_score(worker, self.onto.roles[worker.target_role_id]))
        self.assertIn("insights", res.to_doc())

    def test_insights_none_when_not_wired(self):
        worker = self.onto.workers[HERO_WORKER_ID]
        cur, gen, gate, plan, critic, _ = self._agents()
        res = run_multiagent_code_contract(worker, self.onto, self.edges, cur, gen, gate, plan, critic=critic)
        self.assertIsNone(res.insights)
        self.assertIsNone(res.to_doc()["insights"])


if __name__ == "__main__":
    unittest.main()
