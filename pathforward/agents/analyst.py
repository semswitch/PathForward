"""Code Interpreter analyst — a NON-GATING, advisory second opinion / explainability surface.

Why this exists, and why it is deliberately NOT a `NumericChecker`:
the Foundry Code Interpreter tool has the agent's MODEL *write and run* Python in a sandbox. That is
non-deterministic by construction (the model authors the code), so it can **never** be the credential
gate's numeric oracle — letting the model write its own grading logic would defeat "code notarizes."
`LocalNumericChecker` (`numeric.py`) stays the SOLE oracle the Evidence Gate trusts.

So the analyst is given a DIFFERENT method shape than `NumericChecker` (no `check(expr)->NumericResult`):
it returns an `AnalystReport` (advisory). A `NumericChecker` is therefore not assignable as an Analyst
and an Analyst is not assignable as the gate oracle — the non-gating boundary is structural, not a
naming convention. (This replaces the retired `CodeInterpreterChecker` stub, which conformed to
`NumericChecker` and was a latent footgun.)

Two honest roles (the arithmetic "second opinion" on the gate's trivial `a + b == c` claims is
ceremony — `LocalNumericChecker` settles those exactly; the real value is explainability):
  1. `second_opinion(numeric_claim)` — an INDEPENDENT recompute, advisory. A disagreement with the
     gate's oracle is a review FLAG, never a verdict change.
  2. `calibration_report(stats)` — turn the cold-start calibration into an explainable artifact
     (a chart, live; a deterministic ASCII chart, offline).

Offline: `LocalAnalyst` (deterministic, for the demo + tests). Live: `CodeInterpreterAnalyst` (a
Foundry prompt agent with the `CodeInterpreterTool`; the model writes-and-runs Python). Both behind
the same `Analyst` seam — the same Fake-vs-Foundry pattern as `LLMClient`/`NumericChecker`.

Foundry facts verified via the Microsoft Learn MCP (2026-06-08, full-page fetch of
`learn.microsoft.com/azure/foundry/agents/how-to/tools/code-interpreter`):
  - Prompt-agent attach: `PromptAgentDefinition(tools=[CodeInterpreterTool(container=
    AutoCodeInterpreterToolParam(file_ids=[...]))])`, consumed via `responses.create(... agent_reference)`
    — the SAME shape `FoundryLLMClient`/`ReasoningFoundryClient` use.
  - Generated files come back as `container_file_citation` annotations (container_id + file_id),
    downloaded via `openai.containers.files.content.retrieve(file_id=, container_id=)`.
  - Sandbox: same Azure region as the project, NO outbound network, fixed packages, 1h/30m-idle
    sessions, billed per session. Region-gated (eastus2 confirmed for this project's region).
  - TO-VERIFY: that `CodeInterpreterTool` / `AutoCodeInterpreterToolParam` exist in our pinned
    `azure-ai-projects` (2.2.0; the doc says "use the latest SDK") — same caveat as the Fabric preview
    classes. The live analyst is wired and ready; it is not on the offline/test path.
"""
from __future__ import annotations

import ast
import operator
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

# An independent copy of the safe arithmetic primitive (a genuine second opinion is independent code,
# not a call into the gate's own LocalNumericChecker).
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos, ast.FloorDiv: operator.floordiv,
}


def _safe_eval(text: str) -> float:
    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError(f"disallowed node: {type(node).__name__}")
    return ev(ast.parse(text.strip(), mode="eval"))


@dataclass
class AnalystReport:
    """Advisory output of the analyst. Deliberately NOT a `NumericResult` — nothing here is read by
    the Evidence Gate or mint. `agrees` is the analyst's (advisory) opinion vs. the gate's oracle for
    a numeric second opinion; None for non-numeric reports. `figures` are ASCII artifacts (offline) or
    downloaded file paths (live)."""
    kind: str                          # "numeric_second_opinion" | "calibration"
    summary: str
    agrees: Optional[bool] = None
    figures: tuple[str, ...] = ()
    detail: dict = field(default_factory=dict)

    def to_doc(self) -> dict:
        return {"kind": self.kind, "summary": self.summary, "agrees": self.agrees,
                "figures": list(self.figures), "detail": dict(self.detail)}


@runtime_checkable
class Analyst(Protocol):
    """The non-gating analyst seam. Note the method shape is INTENTIONALLY different from
    `NumericChecker.check(expression) -> NumericResult`, so an Analyst can never be passed where the
    Evidence Gate expects its numeric oracle (and vice versa)."""
    def second_opinion(self, numeric_claim: str) -> AnalystReport: ...
    def calibration_report(self, stats: dict) -> AnalystReport: ...


def _ascii_bar(value: float, width: int = 20, lo: float = 0.0, hi: float = 1.0) -> str:
    """A deterministic ASCII bar for a value in [lo, hi]."""
    if hi <= lo:
        return ""
    frac = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    filled = int(round(frac * width))
    return "#" * filled + "." * (width - filled)


class LocalAnalyst:
    """Deterministic offline analyst — drives the demo and the tests. Genuinely independent of the
    gate's oracle (its own arithmetic + its own ASCII charting), so it is an honest second opinion."""

    def second_opinion(self, numeric_claim: str) -> AnalystReport:
        claim = (numeric_claim or "").strip()
        try:
            if "==" in claim:
                lhs, rhs = claim.split("==", 1)
                lv, rv = _safe_eval(lhs), _safe_eval(rhs)
                agrees = abs(lv - rv) < 1e-9
                summary = (f"independent recompute: {lhs.strip()} = {lv:g}, {rhs.strip()} = {rv:g} "
                           f"-> {'agree' if agrees else 'DISAGREE'}")
                return AnalystReport(kind="numeric_second_opinion", summary=summary, agrees=agrees,
                                     detail={"claim": claim, "lhs": lv, "rhs": rv})
            v = _safe_eval(claim)
            return AnalystReport(kind="numeric_second_opinion",
                                 summary=f"independent recompute: {claim} = {v:g}", agrees=None,
                                 detail={"claim": claim, "value": v})
        except Exception as exc:  # noqa: BLE001 - an unparseable claim is reported, never raised
            return AnalystReport(kind="numeric_second_opinion",
                                 summary=f"could not evaluate '{claim}': {exc}", agrees=None,
                                 detail={"claim": claim, "error": str(exc)})

    def calibration_report(self, stats: dict) -> AnalystReport:
        """Turn cold-start calibration into an explainable ASCII chart (difficulty 0..1 per item) +
        a one-line interpretation. Deterministic over a sorted view of the items."""
        items = sorted((stats or {}).items())
        lines: list[str] = []
        difficulties: list[float] = []
        for item_id, s in items:
            d = float(s.get("difficulty", 0.0))
            disc = s.get("discrimination")
            difficulties.append(d)
            lines.append(f"{item_id:<14} diff {d:>4.2f} |{_ascii_bar(d)}|  disc "
                         f"{('%+.2f' % disc) if isinstance(disc, (int, float)) else '  n/a'}")
        chart = "\n".join(lines)
        n = len(difficulties)
        mean_d = round(sum(difficulties) / n, 4) if n else 0.0
        easy = [i for i, s in items if float(s.get("difficulty", 0.0)) > 0.85]
        hard = [i for i, s in items if float(s.get("difficulty", 0.0)) < 0.15]
        summary = (f"{n} item(s); mean difficulty {mean_d}"
                   + (f"; flagged easy (>0.85): {easy}" if easy else "")
                   + (f"; flagged hard (<0.15): {hard}" if hard else ""))
        return AnalystReport(kind="calibration", summary=summary, agrees=None, figures=(chart,),
                             detail={"n": n, "mean_difficulty": mean_d, "easy": easy, "hard": hard,
                                     "label": "estimated (cold-start)"})


_RATE_LIMIT_RETRIES = 6


def _is_content_filter(exc: Exception) -> bool:
    if getattr(exc, "code", None) == "content_filter":
        return True
    s = str(exc).lower()
    return "content_filter" in s or "content management policy" in s


@dataclass
class CodeInterpreterAnalyst:
    """Live analyst backed by a Foundry prompt agent with the Code Interpreter tool. The MODEL writes
    and runs Python in a sandbox — non-deterministic, so this is ADVISORY ONLY and never the gate
    oracle. Lazily creates one agent version on first use; call close() to delete it. Keyless via
    DefaultAzureCredential. Output files (charts) are downloaded to `out_dir`.

    This is the live swap-in for `LocalAnalyst` behind the `Analyst` seam; it is not exercised by the
    offline tests (the model's code is non-deterministic by design)."""
    endpoint: str
    model: str = "reasoning"
    agent_name: str = "pathforward-analyst"
    out_dir: str = "."
    _project: object = field(default=None, repr=False)
    _openai: object = field(default=None, repr=False)
    _agent: object = field(default=None, repr=False)

    _INSTRUCTIONS = (
        "You are a non-gating data analyst. You write and run Python with the Code Interpreter tool to "
        "(a) independently verify arithmetic and (b) produce explainable calibration charts. Your "
        "output is ADVISORY ONLY — you never decide whether a credential is issued."
    )

    def _ensure(self) -> None:
        if self._agent is not None:
            return
        from azure.ai.projects import AIProjectClient
        from azure.ai.projects.models import (
            AutoCodeInterpreterToolParam, CodeInterpreterTool, PromptAgentDefinition,
        )
        from azure.identity import DefaultAzureCredential

        self._project = AIProjectClient(endpoint=self.endpoint, credential=DefaultAzureCredential())
        self._openai = self._project.get_openai_client()
        # No uploaded files: the analyst charts inline data passed in the prompt (file_ids empty).
        tool = CodeInterpreterTool(container=AutoCodeInterpreterToolParam(file_ids=[]))
        self._agent = self._project.agents.create_version(
            agent_name=self.agent_name,
            definition=PromptAgentDefinition(model=self.model, instructions=self._INSTRUCTIONS,
                                             tools=[tool]),
            description="PathForward non-gating Code Interpreter analyst (advisory).",
        )

    def _respond(self, prompt: str):
        last: Optional[Exception] = None
        for attempt in range(_RATE_LIMIT_RETRIES):
            try:
                return self._openai.responses.create(
                    input=prompt,
                    extra_body={"agent_reference": {"name": self._agent.name,
                                                    "type": "agent_reference"}})
            except Exception as exc:  # noqa: BLE001
                status = getattr(exc, "status_code", None) or getattr(
                    getattr(exc, "response", None), "status_code", None)
                if status == 429 or "rate limit" in str(exc).lower():
                    last = exc
                    time.sleep(8 * (attempt + 1))
                    continue
                raise
        raise last  # type: ignore[misc]

    def second_opinion(self, numeric_claim: str) -> AnalystReport:
        self._ensure()
        prompt = (f"Independently verify this arithmetic by writing and running Python. "
                  f"Reply with exactly one line 'AGREES: true' or 'AGREES: false', then a one-line "
                  f"explanation. Claim: {numeric_claim}")
        try:
            resp = self._respond(prompt)
        except Exception as exc:  # noqa: BLE001
            if _is_content_filter(exc):
                return AnalystReport(kind="numeric_second_opinion",
                                     summary="content filtered", agrees=None,
                                     detail={"claim": numeric_claim, "content_filtered": True})
            raise
        text = getattr(resp, "output_text", "") or ""
        # Tolerant parse: accept 'AGREES: true', 'agrees=false', '**AGREES - true**', etc. None is the
        # safe fallback (the deterministic LocalNumericChecker is the real oracle, not this opinion).
        m = re.search(r"agrees\s*[:=\-]?\s*(true|false)", text, re.IGNORECASE)
        agrees: Optional[bool] = (m.group(1).lower() == "true") if m else None
        return AnalystReport(kind="numeric_second_opinion", summary=text.strip()[:240], agrees=agrees,
                             detail={"claim": numeric_claim, "raw": text})

    def calibration_report(self, stats: dict) -> AnalystReport:
        self._ensure()
        rows = "; ".join(f"{k}: difficulty={v.get('difficulty')}, discrimination={v.get('discrimination')}"
                         for k, v in sorted((stats or {}).items()))
        prompt = (f"Using Python (matplotlib), create a labeled bar chart of item difficulty and "
                  f"discrimination from this cold-start calibration data, then give a one-sentence "
                  f"interpretation. Save the chart as a PNG file. Data: {rows}")
        try:
            resp = self._respond(prompt)
        except Exception as exc:  # noqa: BLE001
            if _is_content_filter(exc):
                return AnalystReport(kind="calibration", summary="content filtered",
                                     detail={"content_filtered": True})
            raise
        figures = tuple(self._download_files(resp))
        return AnalystReport(kind="calibration", summary=(getattr(resp, "output_text", "") or "")[:300],
                             figures=figures, detail={"n": len(stats or {}),
                                                      "label": "estimated (cold-start)"})

    def _download_files(self, resp) -> list[str]:
        """Download any container_file_citation files the model generated (charts) to out_dir."""
        import os
        out: list[str] = []
        seen: set[tuple] = set()
        for item in (getattr(resp, "output", None) or []):
            if getattr(item, "type", None) != "message":
                continue
            for content in (getattr(item, "content", None) or []):
                for ann in (getattr(content, "annotations", None) or []):
                    if getattr(ann, "type", None) != "container_file_citation":
                        continue
                    key = (ann.container_id, ann.file_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        data = self._openai.containers.files.content.retrieve(
                            file_id=ann.file_id, container_id=ann.container_id)
                        # Unique on-disk name (prefix the file_id) so two same-basename charts in one
                        # response don't clobber each other; guard a missing filename.
                        base = os.path.basename(ann.filename) if getattr(ann, "filename", None) \
                            else f"{ann.file_id}.bin"
                        path = os.path.join(self.out_dir, f"{ann.file_id}-{base}")
                        with open(path, "wb") as f:
                            f.write(data.read())
                        out.append(path)
                    except Exception:  # noqa: BLE001 - a failed download is non-fatal (advisory)
                        pass
        return out

    def close(self) -> None:
        if self._agent is not None and self._project is not None:
            try:
                self._project.agents.delete_version(agent_name=self._agent.name,
                                                    agent_version=self._agent.version)
            except Exception:  # noqa: BLE001
                pass
            self._agent = None
