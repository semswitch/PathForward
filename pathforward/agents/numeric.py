"""Numeric checker — the Evidence Gate routes every numeric/threshold claim here.

`LocalNumericChecker` (a safe AST arithmetic evaluator: no `eval`, no names, no calls) is the
**sole** numeric oracle the Evidence Gate trusts, offline AND live. The gate never trusts a model
for arithmetic — code answers what code can answer.

NOTE (re-scope, ADR 008): the Foundry Code Interpreter tool is deliberately NOT a swap-in here.
Code Interpreter has the model *write and run* the Python, which is non-deterministic, so it can
never be the credential gate's oracle. It lives instead as a distinct, NON-GATING advisory analyst
(`agents/analyst.py` -> `CodeInterpreterAnalyst`) with a different method shape, so it cannot be
passed where the gate expects a `NumericChecker`. The old `CodeInterpreterChecker` stub (which
wrongly conformed to `NumericChecker`) was retired for that reason.
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

# The former `CodeInterpreterChecker` stub was retired (ADR 008): Code Interpreter is non-deterministic
# (the model writes the code) and must never be the gate oracle. It now lives as a NON-GATING analyst
# with a distinct interface — see `agents/analyst.py` (`CodeInterpreterAnalyst` / `LocalAnalyst`).
