"""Numeric checker — the Verifier routes every numeric/threshold claim here.

Offline: a safe AST arithmetic evaluator (no `eval`, no names, no calls). On Azure
this is replaced by the GA Code Interpreter tool (batch all checks into one billed
session). The Verifier never trusts the model for arithmetic — code answers what
code can answer.
"""
from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos, ast.FloorDiv: operator.floordiv,
}


@dataclass
class NumericResult:
    ok: bool
    value: Optional[float]
    detail: str


@runtime_checkable
class NumericChecker(Protocol):
    def check(self, expression: str) -> NumericResult: ...


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("non-numeric constant")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError(f"disallowed expression node: {type(node).__name__}")


class LocalNumericChecker:
    """Evaluates arithmetic safely. Supports an optional '==' assertion form."""

    def check(self, expression: str) -> NumericResult:
        expr = expression.strip()
        try:
            if "==" in expr:
                lhs, rhs = expr.split("==", 1)
                lv, rv = self._value(lhs), self._value(rhs)
                ok = abs(lv - rv) < 1e-9
                return NumericResult(ok, lv, f"{lhs.strip()} == {rhs.strip()} -> {ok}")
            v = self._value(expr)
            return NumericResult(True, v, f"{expr} = {v}")
        except Exception as exc:  # noqa: BLE001 - report any parse/eval failure as not-ok
            return NumericResult(False, None, f"could not evaluate '{expression}': {exc}")

    @staticmethod
    def _value(text: str) -> float:
        tree = ast.parse(text.strip(), mode="eval")
        return _eval(tree)


class CodeInterpreterChecker:
    """Azure stub — wire to the GA Code Interpreter tool on Day 4.

    Batch all of a verification round's numeric checks into a single session
    (Code Interpreter is billed per session; no outbound network; fixed packages).
    """

    def check(self, expression: str) -> NumericResult:  # pragma: no cover - Azure-only
        raise NotImplementedError(
            "Wire to the Foundry Code Interpreter tool on Day 4 (see 03-Build-Plan.md §3.3)."
        )
