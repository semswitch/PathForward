"""Deterministic capture-then-score for the live Prompt Orchestrator route.

This scores a CAPTURED live run (an `.agents/evidence/integrated-live-*.json` proof produced by
`scripts/smoke_integrated_orchestrator_live.py`) against the SAME versioned PathForward code
evaluators used by the Foundry eval, with NO agent re-invocation.

Why this exists: the Foundry cloud eval (`scripts/run_prompt_orchestrator_eval.py`) re-invokes the
agent live via `azure_ai_target_completions` with no retry, so the 5+ tool route intermittently
aborts server-side (`tool_user_error` / "Agent task ... failed" / empty output). Capturing a real
live run once (which already passes -- BASELINE_PASS) and scoring the snapshot deterministically
keeps the live proof of the run while making the *scoring* replay-free and reproducible. See
`.agents/audits/foundry-eval-optimization-2026-06-13.md`.

It is NOT a fake-agent test: the route it scores genuinely executed against the live versioned
Foundry agent. Only the grading is local + deterministic.
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Output-item types that represent an actual tool/route step (vs reasoning/output/message/discovery).
ROUTE_CALL_TYPES = {"mcp_call", "a2a_preview_call", "mcp_approval_request"}
DISCOVERY_TYPES = {"mcp_list_tools", "tool_definitions"}


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_grader(local_uri: str) -> Callable[[dict, dict], float]:
    """Import a code evaluator's grade() from its manifest local_uri (the same file Foundry registers)."""
    path = ROOT / local_uri
    spec = importlib.util.spec_from_file_location(f"pf_eval_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load evaluator from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    grade = getattr(module, "grade", None)
    if not callable(grade):
        raise RuntimeError(f"{path} does not expose a callable grade()")
    return grade


def _latest_evidence() -> Path:
    candidates = sorted(
        glob.glob(str(ROOT / ".agents" / "evidence" / "integrated-live-*.json")),
        key=os.path.getmtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("no integrated-live-*.json captured runs under .agents/evidence")
    return Path(candidates[0])


def _reconstruct_sample(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Turn the captured proof rows into the {output_items, output, output_text} shape the
    evaluators read (data_mapping maps output_items <- {{sample.output}}).

    Message rows store their text under `message_preview`; several evaluators read `entry["content"]`,
    so we surface the text as `content` (and join it into `output_text`) without dropping any field.
    """
    items: list[dict[str, Any]] = []
    for row in rows:
        entry = dict(row)
        if str(row.get("type", "")).lower() == "message":
            entry.setdefault("role", "assistant")
            entry["content"] = row.get("message_preview", "")
        items.append(entry)
    output_text = "\n".join(
        str(row.get("message_preview", ""))
        for row in rows
        if str(row.get("type", "")).lower() == "message" and row.get("message_preview")
    )
    return {"output_items": items, "output": items, "output_text": output_text}


def _actual_route(items: list[dict[str, Any]]) -> list[str]:
    sequence: list[str] = []
    for entry in items:
        kind = str(entry.get("type", "")).lower()
        if kind in DISCOVERY_TYPES or kind not in ROUTE_CALL_TYPES:
            continue
        if kind == "mcp_approval_request":
            sequence.append("mcp_approval_request")
            continue
        ident = str(entry.get("server_label") or entry.get("name") or "").lower()
        if ident:
            sequence.append(ident)
    return sequence


def _expected_route(row: dict[str, Any]) -> list[str]:
    explicit = row.get("expected_route")
    if explicit:
        return [str(value).lower() for value in explicit]
    return [
        str(value).lower()
        for value in (row.get("must_emit") or [])
        if str(value).lower().startswith("pathforward-") or str(value).lower() == "mcp_approval_request"
    ]


def _in_order_match(expected: list[str], actual: list[str]) -> dict[str, Any]:
    """task_navigation_efficiency-style in_order_match: expected is a subsequence of actual."""
    pos = 0
    for ident in actual:
        if pos < len(expected) and ident == expected[pos]:
            pos += 1
    matched = pos
    total = len(expected)
    return {
        "expected": expected,
        "actual": actual,
        "matched": matched,
        "expected_count": total,
        "in_order": matched == total and total > 0,
        "recall": round(matched / total, 4) if total else 1.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", default="", help="Captured integrated-live-*.json (default: latest).")
    parser.add_argument("--suite", default="eval/suites/captured_route_full.jsonl",
                        help="Dataset suite whose row describes the captured run's expected behavior.")
    parser.add_argument("--row-index", type=int, default=0)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    evidence_path = Path(args.evidence) if args.evidence else _latest_evidence()
    if not evidence_path.is_absolute():
        evidence_path = ROOT / evidence_path
    proof = json.loads(evidence_path.read_text(encoding="utf-8"))
    rows = proof.get("rows") or []
    if not rows:
        print(f"FAIL: captured proof {evidence_path} has no rows")
        return 1

    suite_rows = _load_jsonl(ROOT / args.suite)
    if args.row_index >= len(suite_rows):
        print(f"FAIL: --row-index {args.row_index} out of range for {args.suite} ({len(suite_rows)} rows)")
        return 1
    row = suite_rows[args.row_index]

    sample = _reconstruct_sample(rows)
    item = {**row, "sample": sample}

    manifest = _load_manifest(ROOT / "eval" / "evaluators" / "manifest.json")
    results: list[dict[str, Any]] = []
    for entry in manifest["evaluators"]:
        grade = _load_grader(entry["local_uri"])
        score = float(grade(sample, item))
        results.append({
            "evaluator": entry["name"],
            "score": score,
            "passed": score >= 1.0,
        })

    route = _in_order_match(_expected_route(row), _actual_route(sample["output_items"]))
    results.append({
        "evaluator": "ordered_route_in_order_match",
        "score": 1.0 if route["in_order"] else 0.0,
        "passed": bool(route["in_order"]),
        "detail": route,
    })

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    all_pass = passed == total
    report = {
        "status": "PASS" if all_pass else "FAIL",
        "evidence": str(evidence_path.relative_to(ROOT)) if evidence_path.is_relative_to(ROOT) else str(evidence_path),
        "captured_agent": proof.get("agent"),
        "captured_response_id": proof.get("first_response_id"),
        "captured_mode": proof.get("mode"),
        "suite": args.suite,
        "row_index": args.row_index,
        "passed": passed,
        "total": total,
        "results": results,
    }

    if args.out:
        out_path = Path(args.out)
    else:
        evidence_dir = ROOT / ".agents" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        stamp = evidence_path.stem.replace("integrated-live-", "")
        out_path = evidence_dir / f"captured-route-score-{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2, sort_keys=True))
    for result in results:
        mark = "PASS" if result["passed"] else "FAIL"
        print(f"  [{mark}] {result['evaluator']} = {result['score']}")
    print(f"scorecard={out_path}")
    print(report["status"] + f": {passed}/{total} checks green (deterministic, no agent re-invocation)")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
