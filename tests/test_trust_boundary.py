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
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "pathforward")


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


if __name__ == "__main__":
    unittest.main()
