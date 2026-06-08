"""Structural trust-boundary invariants for the agents-forward system ("agents reason, code
notarizes"). These are source-level guards, not behavioural tests: they lock the properties the
plan depends on so a later refactor cannot silently erode them.

P0 invariant (this file): the deterministic Evidence Gate is the SOLE authority that can mark a
loop result `verified`, and that write exists in exactly ONE place. `mint()` trusts
`loop_result.status` + citations and re-derives readiness/spine itself, so the only producer of a
`"verified"` status MUST be the loop, gated by `EvidenceGate.verify(...) -> passed=True`.
Later phases extend this file (Critic-cannot-override, reflection anti-leak, adaptive-not-in-mint).

We parse the AST (not regex) so docstrings/comments mentioning `status="verified"` are not
mistaken for an actual write — only real keyword-args and assignments count."""
import ast
import glob
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "pathforward")
sys.path.insert(0, ROOT)

from pathforward.agents.evidence_gate import EvidenceGate          # noqa: E402
from pathforward.agents.types import AssessmentItem, LoopResult, Verdict  # noqa: E402
from pathforward.credential.mint import mint                       # noqa: E402
from pathforward.credential.schema import CredentialIntegrityError  # noqa: E402
from pathforward.iq.seed import build_seed                         # noqa: E402


def _read(rel: str) -> str:
    with open(os.path.join(PKG, rel), encoding="utf-8") as fh:
        return fh.read()


def _verified_status_writes(tree: ast.AST) -> list[int]:
    """Line numbers where the code actually WRITES status == 'verified' — i.e. a call keyword
    `Foo(status="verified")` or an assignment `status = "verified"` / `x.status = "verified"`.
    Docstring/comment mentions and comparisons (`!= "verified"`) are ignored."""
    hits: list[int] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.keyword) and node.arg == "status"
                and isinstance(node.value, ast.Constant) and node.value.value == "verified"):
            hits.append(node.lineno)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and node.value.value == "verified":
            for tgt in node.targets:
                name = (tgt.id if isinstance(tgt, ast.Name)
                        else tgt.attr if isinstance(tgt, ast.Attribute) else None)
                if name == "status":
                    hits.append(node.lineno)
    return hits


class TestSingleWriter(unittest.TestCase):
    def test_status_verified_set_in_exactly_one_place(self):
        all_hits = []
        for path in glob.glob(os.path.join(PKG, "**", "*.py"), recursive=True):
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            for ln in _verified_status_writes(tree):
                all_hits.append((os.path.relpath(path, ROOT).replace("\\", "/"), ln))
        self.assertEqual(len(all_hits), 1,
                         f'status="verified" must be WRITTEN in exactly one place; found {all_hits}')
        self.assertTrue(all_hits[0][0].endswith("agents/loop.py"),
                        f'the sole "verified" writer must be agents/loop.py, got {all_hits[0][0]}')


class TestGateIndependentOfCritic(unittest.TestCase):
    """The deterministic Evidence Gate (and mint) must have NO code dependency on the Critic — the
    Critic recommends, the gate decides, and nothing the Critic returns is read by the verdict."""

    def test_verify_signature_takes_no_critic_input(self):
        params = list(inspect.signature(EvidenceGate.verify).parameters)
        self.assertEqual(params, ["self", "item", "allowed_ref_ids"])

    def test_evidence_gate_does_not_import_or_read_the_critic(self):
        src = _read("agents/evidence_gate.py")
        self.assertNotIn("from .critic", src)
        self.assertNotIn("import critic", src)
        self.assertNotIn("CriticReview", src)   # the gate never reads a Critic verdict

    def test_mint_does_not_read_the_critic(self):
        src = _read("credential/mint.py")
        self.assertNotIn("CriticReview", src)
        self.assertNotIn("critic", src.lower())

    def test_difficulty_band_never_reaches_the_gate_or_mint(self):
        # Adaptive difficulty is selection-only: neither the gate's verdict nor mint() may read it.
        self.assertNotIn("difficulty_band", _read("agents/evidence_gate.py"))
        self.assertNotIn("difficulty_band", _read("credential/mint.py"))


class TestMintReDerivesNotTrusts(unittest.TestCase):
    """mint() trusts loop_result.status + citations but RE-CHECKS the causal spine itself, so a
    forged 'verified' result whose edge/worker/skill do not reconcile still fails closed."""

    def test_forged_cross_worker_verified_still_fails_mint(self):
        onto = build_seed()
        worker = onto.workers["EMP-001"]
        role = onto.roles[worker.target_role_id]
        # A hand-forged "verified" result citing ANOTHER worker's CertGap edge.
        forged_edge = "certgap::EMP-999::S01"
        item = AssessmentItem(id="x", targeted_skill_id="S01", driving_edge_id=forged_edge,
                              stem="s", options=("a", "b"), answer_index=0,
                              cited_ref_ids=(forged_edge,))
        verdict = Verdict(passed=True, criteria={}, failed_reasons=[])
        forged = LoopResult(status="verified", driving_edge_id=forged_edge, targeted_skill_id="S01",
                            attempts=1, item=item, verdict=verdict, transcript=[],
                            citations=(forged_edge,))
        with self.assertRaises(CredentialIntegrityError):
            mint(worker, role, forged_edge, "S01", forged)


if __name__ == "__main__":
    unittest.main()
