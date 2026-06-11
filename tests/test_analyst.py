"""Code Interpreter analyst: NON-GATING and advisory. These tests pin the load-bearing boundary that
the analyst can never become the credential gate's numeric oracle (structurally, by method shape, not
by naming), that the Evidence Gate / loop never import it, and that a disagreeing analyst cannot
change a Verdict."""
import ast
import glob
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "pathforward")

from pathforward.agents.analyst import Analyst, AnalystReport, LocalAnalyst   # noqa: E402
from tests.fakes import FakeLLMClient  # noqa: E402
from pathforward.agents.evidence_gate import EvidenceGate                     # noqa: E402
from pathforward.agents.generator import Generator                          # noqa: E402
from pathforward.agents.loop import run_assessment_loop                       # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker, NumericChecker    # noqa: E402
from pathforward.iq import derivation as dv                                   # noqa: E402
from pathforward.iq import traversal                                          # noqa: E402
from pathforward.iq.seed import HERO_WORKER_ID, build_seed                    # noqa: E402


def _read(rel: str) -> str:
    with open(os.path.join(PKG, rel), encoding="utf-8") as fh:
        return fh.read()


def _imported_targets(rel: str) -> set[str]:
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


class _AlwaysDisagreeAnalyst:
    """A hostile analyst that always disagrees — used to prove it can't move the gate's verdict."""
    def second_opinion(self, numeric_claim: str) -> AnalystReport:
        return AnalystReport(kind="numeric_second_opinion", summary="nope", agrees=False)

    def calibration_report(self, stats: dict) -> AnalystReport:
        return AnalystReport(kind="calibration", summary="", agrees=None)


class TestAnalystIsStructurallyNonGating(unittest.TestCase):
    def test_analyst_is_not_a_numeric_checker_and_vice_versa(self):
        # The structural boundary: an Analyst cannot be passed where the gate expects its oracle,
        # and the oracle cannot be passed where an Analyst is expected. Different method shapes.
        self.assertFalse(isinstance(LocalAnalyst(), NumericChecker))   # no .check(expr)
        self.assertTrue(isinstance(LocalAnalyst(), Analyst))
        self.assertFalse(isinstance(LocalNumericChecker(), Analyst))   # no .second_opinion/.calibration_report
        self.assertTrue(isinstance(LocalNumericChecker(), NumericChecker))
        self.assertFalse(hasattr(LocalAnalyst, "check"))

    def test_code_interpreter_gate_oracle_was_retired(self):
        # The old CodeInterpreterChecker class (which conformed to NumericChecker) must be gone.
        # AST check (a docstring/comment may still NAME it when explaining the retirement).
        tree = ast.parse(_read("agents/numeric.py"))
        classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
        self.assertNotIn("CodeInterpreterChecker", classes)
        self.assertIn("LocalNumericChecker", classes)

    def test_no_pathforward_module_imports_the_analyst(self):
        # Deny-by-default: NOTHING under pathforward/ (except analyst.py itself) may import the
        # analyst. Harder to defeat than an allow-list of gate/loop/mint — a regression that imported
        # it into scorer.py / calibration.py / orchestrator.py would be caught here too.
        offenders = []
        for path in glob.glob(os.path.join(PKG, "**", "*.py"), recursive=True):
            rel = os.path.relpath(path, PKG).replace("\\", "/")
            if rel == "agents/analyst.py":
                continue
            if any("analyst" in t.lower() for t in _imported_targets(rel)):
                offenders.append(rel)
        self.assertEqual(offenders, [], f"these modules import the analyst (must not): {offenders}")

    def test_gate_rejects_a_non_numericchecker_oracle(self):
        # The "structural" claim made literal: the gate refuses a non-NumericChecker oracle at
        # construction (so a non-gating analyst can never be installed, even for non-numeric items).
        EvidenceGate(LocalNumericChecker())                       # the real oracle is accepted
        with self.assertRaises(TypeError):
            EvidenceGate(LocalAnalyst())                          # the analyst is rejected

    def test_verify_signature_has_no_analyst(self):
        params = list(inspect.signature(EvidenceGate.verify).parameters)
        self.assertEqual(params, ["self", "item", "allowed_ref_ids"])


class TestSecondOpinionAdvisory(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        worker = self.onto.workers[HERO_WORKER_ID]
        edges = dv.build_all_edges(self.onto)
        self.driving = traversal.cert_gap_edges(worker, self.onto, edges)[0]
        self.skill = self.onto.skills[self.driving.target_id]
        self.allowed = traversal.approved_refs(worker, self.skill, self.onto)

    def _verified_item(self):
        res = run_assessment_loop(self.driving, self.skill, self.allowed,
                                  Generator(FakeLLMClient()), EvidenceGate(LocalNumericChecker()))
        self.assertEqual(res.status, "verified")
        passed = [t for t in res.transcript if t["verdict"].passed][-1]
        return passed["item"], passed["verdict"]

    def test_verdict_is_deterministic_and_analyst_is_out_of_band(self):
        # A behavioral illustration of "advisory": even a hostile always-disagree analyst is out of
        # band — verify() takes no analyst (proven by test_verify_signature_has_no_analyst) and the
        # analyst can't even be installed as the oracle (test_gate_rejects_a_non_numericchecker_oracle),
        # so a fresh verify over the same evidence yields the same pass regardless of the analyst.
        item, verdict = self._verified_item()
        self.assertTrue(verdict.passed)
        rep = _AlwaysDisagreeAnalyst().second_opinion(item.numeric_claim or "1 == 2")
        self.assertFalse(rep.agrees)
        again = EvidenceGate(LocalNumericChecker()).verify(item, self.allowed)
        self.assertEqual(again.passed, verdict.passed)
        self.assertTrue(again.passed)

    def test_local_analyst_agrees_with_the_gate_on_a_real_item(self):
        # The maker-checker concord: on the gate's verified item, the independent recompute agrees.
        item, verdict = self._verified_item()
        self.assertTrue(item.numeric_claim)                       # the code-test item carries one
        rep = LocalAnalyst().second_opinion(item.numeric_claim)
        self.assertTrue(rep.agrees)
        self.assertTrue(verdict.criteria.get("numeric_valid", True))


class TestLocalAnalyst(unittest.TestCase):
    def test_second_opinion_arithmetic(self):
        a = LocalAnalyst()
        self.assertTrue(a.second_opinion("18 + 6 == 24").agrees)
        self.assertFalse(a.second_opinion("18 + 6 == 25").agrees)
        self.assertIsNone(a.second_opinion("18 + 6").agrees)       # no equality -> opinion is None
        self.assertIsNone(a.second_opinion("not math").agrees)     # unparseable -> reported, not raised

    def test_calibration_report_is_deterministic_and_explainable(self):
        stats = {"item-S01": {"n": 30, "difficulty": 0.6, "discrimination": 0.3,
                              "label": "estimated (cold-start)"},
                 "item-S02": {"n": 30, "difficulty": 0.92, "discrimination": 0.1,
                              "label": "estimated (cold-start)"}}
        a = LocalAnalyst()
        r1 = a.calibration_report(stats)
        r2 = a.calibration_report(stats)
        self.assertEqual(r1.to_doc(), r2.to_doc())                 # deterministic
        self.assertEqual(r1.kind, "calibration")
        self.assertTrue(r1.figures and "item-S01" in r1.figures[0])   # an ASCII chart naming the items
        self.assertIn("S02", str(r1.detail["easy"]))              # 0.92 > 0.85 flagged easy
        self.assertEqual(r1.detail["mean_difficulty"], 0.76)

    def test_calibration_report_hard_flag_and_empty_stats(self):
        a = LocalAnalyst()
        # the 'hard' branch: difficulty < 0.15 is flagged hard
        hard = a.calibration_report({"item-S01": {"n": 10, "difficulty": 0.08, "discrimination": 0.2}})
        self.assertIn("S01", str(hard.detail["hard"]))
        self.assertEqual(hard.detail["easy"], [])
        # the empty-stats chart path: one empty figure, no error
        empty = a.calibration_report({})
        self.assertEqual(empty.kind, "calibration")
        self.assertEqual(len(empty.figures), 1)
        self.assertEqual(empty.detail["mean_difficulty"], 0.0)


if __name__ == "__main__":
    unittest.main()
