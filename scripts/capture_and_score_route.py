"""Deterministic capture-then-score for the live Prompt Orchestrator route.

This scores a CAPTURED live run against the SAME versioned PathForward code evaluators used by the
Foundry eval, with NO agent re-invocation. It is the AUTHORITATIVE proof surface for this A2A-routed
architecture -- the Foundry cloud eval (``azure_ai_target_completions``) under-captures
``a2a_preview_call`` rows in ``sample.output``, so it cannot see the Curator/Generator/Critic/Planner/
Insights hops and is no longer trusted for route/Fabric grading.

Two live capture sources, both normalized into the project's canonical ``captured_events`` schema
(``pathforward/captured_route.py``):

* ``--capture`` -- a canonical ``captured-route-*.json`` produced by
  ``scripts/probe_orchestrator_stream.py`` (single-shot streamed reasoning route).
* ``--evidence`` -- a staged ``integrated-live-*.json`` proof produced by
  ``scripts/smoke_integrated_orchestrator_live.py`` (multi-turn full route incl. approval + mint).

With neither flag we auto-pick the most recent of the two. The evaluators read the explicit
``captured_events`` list (route grading + Fabric grounding); the un-migrated evaluators read a legacy
``output_items``/``output_text`` surface reconstructed FROM the same ``captured_events`` -- one source
of truth for every check.

It is NOT a fake-agent test: the route it scores genuinely executed against the live versioned Foundry
agent. Only the grading is local + deterministic.
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

from pathforward import captured_route as cr  # noqa: E402

# Tool/route event types that count toward the executed ordered route (the A2A *_output rows and
# plain messages are excluded -- only the call itself is a route step).
_ORDERED_ROUTE_TYPES = {"mcp_call", "a2a_preview_call", "mcp_approval_request"}


def _load_grader(local_uri: str) -> Callable[[dict, dict], float]:
    """Import a code evaluator's grade() from its manifest local_uri (the file Foundry registers)."""
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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _latest(pattern: str) -> Path | None:
    candidates = sorted(
        glob.glob(str(ROOT / ".agents" / "evidence" / pattern)),
        key=os.path.getmtime,
        reverse=True,
    )
    return Path(candidates[0]) if candidates else None


def _capture_from_canonical(path: Path) -> dict[str, Any]:
    data = cr.load_capture(path)
    return {
        "events": data["captured_events"],
        "agent": data.get("agent", ""),
        "response_id": data.get("response_id", ""),
        "mode": data.get("source", "stream"),
        "query": data.get("query", ""),
        "status": data.get("status", ""),
        "schema_version": data.get("schema_version", ""),
        "default_suite": "eval/suites/captured_route_reasoning.jsonl",
    }


def _capture_from_staged(path: Path) -> dict[str, Any]:
    proof = json.loads(path.read_text(encoding="utf-8"))
    rows = proof.get("rows") or []
    if not rows:
        raise ValueError(f"captured proof {path} has no rows")
    return {
        "events": cr.events_from_staged_rows(rows),
        "agent": proof.get("agent", ""),
        "response_id": proof.get("first_response_id", ""),
        "mode": proof.get("mode", "staged"),
        "query": "",
        "status": proof.get("first_response_status", ""),
        "schema_version": cr.SCHEMA_VERSION,
        "default_suite": "eval/suites/captured_route_full.jsonl",
    }


def _resolve_source(args: argparse.Namespace) -> tuple[Path, Callable[[Path], dict[str, Any]]]:
    if args.capture:
        return (ROOT / args.capture if not Path(args.capture).is_absolute() else Path(args.capture),
                _capture_from_canonical)
    if args.evidence:
        return (ROOT / args.evidence if not Path(args.evidence).is_absolute() else Path(args.evidence),
                _capture_from_staged)
    canonical = _latest("captured-route-*.json")
    staged = _latest("integrated-live-*.json")
    if canonical and (not staged or os.path.getmtime(canonical) >= os.path.getmtime(staged)):
        return canonical, _capture_from_canonical
    if staged:
        return staged, _capture_from_staged
    raise FileNotFoundError(
        "no captured-route-*.json or integrated-live-*.json under .agents/evidence "
        "(run scripts/probe_orchestrator_stream.py or scripts/smoke_integrated_orchestrator_live.py)"
    )


def _expected_route(row: dict[str, Any]) -> list[str]:
    explicit = row.get("expected_route")
    if explicit:
        return [str(value).lower() for value in explicit]
    return [
        str(value).lower()
        for value in (row.get("must_emit") or [])
        if str(value).lower().startswith("pathforward-") or str(value).lower() == "mcp_approval_request"
    ]


def _actual_route(events: list[dict[str, Any]]) -> list[str]:
    sequence: list[str] = []
    for event in events:
        kind = str(event.get("type", "")).lower()
        if kind not in _ORDERED_ROUTE_TYPES:
            continue
        if str(event.get("status", "")).lower() != "completed":
            continue
        if kind == "mcp_approval_request":
            sequence.append("mcp_approval_request")
            continue
        label = str(event.get("label", "")).lower()
        if label:
            sequence.append(label)
    return sequence


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
    parser.add_argument("--capture", default="",
                        help="Canonical captured-route-*.json from the streamed probe (default: latest).")
    parser.add_argument("--evidence", default="",
                        help="Staged integrated-live-*.json proof (full mint route).")
    parser.add_argument("--suite", default="",
                        help="Dataset suite (default: per-source -- reasoning for --capture, full for --evidence).")
    parser.add_argument("--row-index", type=int, default=0)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    try:
        source_path, loader = _resolve_source(args)
        capture = loader(source_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1

    events = capture["events"]
    if not events:
        print(f"FAIL: captured source {source_path} produced no canonical events")
        return 1

    suite = args.suite or capture["default_suite"]
    suite_rows = _load_jsonl(ROOT / suite)
    if args.row_index >= len(suite_rows):
        print(f"FAIL: --row-index {args.row_index} out of range for {suite} ({len(suite_rows)} rows)")
        return 1
    row = suite_rows[args.row_index]

    # ONE source of truth: captured_events for the structured evaluators, a legacy surface derived from
    # the SAME events for the un-migrated evaluators.
    surface = cr.reconstruct_legacy_surface(events)
    sample = {**surface, "captured_events": events}
    item = {**row, "sample": sample, "captured_events": events}

    manifest = json.loads((ROOT / "eval" / "evaluators" / "manifest.json").read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    for entry in manifest["evaluators"]:
        grade = _load_grader(entry["local_uri"])
        score = float(grade(sample, item))
        results.append({"evaluator": entry["name"], "score": score, "passed": score >= 1.0})

    route = _in_order_match(_expected_route(row), _actual_route(events))
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
        "evidence": str(source_path.relative_to(ROOT)) if source_path.is_relative_to(ROOT) else str(source_path),
        "captured_agent": capture["agent"],
        "captured_response_id": capture["response_id"],
        "captured_mode": capture["mode"],
        "schema_version": capture["schema_version"],
        "captured_events": len(events),
        "suite": suite,
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
        stamp = source_path.stem.replace("integrated-live-", "").replace("captured-route-", "")
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
