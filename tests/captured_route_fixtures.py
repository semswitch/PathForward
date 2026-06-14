"""Shared fixtures for the captured-route evaluator + normalizer tests.

Not named ``test_*`` so neither unittest discovery nor pytest collects it as a test module.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_DIR = ROOT / "eval" / "evaluators"

REASONING_EXPECTED_ROUTE = [
    "pathforward-route",
    "pathforward-a2a-curator",
    "pathforward-a2a-generator",
    "pathforward-a2a-critic",
    "pathforward-gate",
    "pathforward-a2a-planner",
    "pathforward-a2a-insights",
]
INSIGHTS_OUTPUT = (
    "source=fabric-live\ncohort_size: 11\naverage_readiness: 0.5909\n"
    "selected_skill_bottleneck_count: 3\nworker_readiness: 0.5"
)


def load_evaluator(name: str):
    path = EVALUATOR_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def ev(itype, label, *, status="completed", output="", text="", name="", server_label=""):
    return {
        "index": 0, "type": itype, "label": label, "name": name or label,
        "server_label": server_label, "status": status, "id": "x", "call_id": "",
        "output": output, "text": text, "role": "assistant" if itype == "message" else "",
    }


def reasoning_events(*, insights_output=INSIGHTS_OUTPUT, insights_status="completed"):
    """The 7-step reasoning route (no mint): route -> curator -> ... -> insights -> final message."""
    return [
        ev("mcp_call", "pathforward-route", server_label="pathforward-route", name="resolve_route_facts"),
        ev("a2a_preview_call", "pathforward-a2a-curator"),
        ev("a2a_preview_call_output", "pathforward-a2a-curator", output="curator ok"),
        ev("a2a_preview_call", "pathforward-a2a-generator"),
        ev("a2a_preview_call_output", "pathforward-a2a-generator", output="item drafted"),
        ev("a2a_preview_call", "pathforward-a2a-critic"),
        ev("a2a_preview_call_output", "pathforward-a2a-critic", output="pass"),
        ev("mcp_call", "pathforward-gate", server_label="pathforward-gate",
           name="verify_assessment_and_issue_mint_request"),
        ev("a2a_preview_call", "pathforward-a2a-planner"),
        ev("a2a_preview_call_output", "pathforward-a2a-planner", output="advisory"),
        ev("a2a_preview_call", "pathforward-a2a-insights", status=insights_status),
        ev("a2a_preview_call_output", "pathforward-a2a-insights", output=insights_output,
           status=insights_status),
        ev("message", "", text="assessment_summary: gate verified; minting requires approval."),
    ]


def full_route_events(*, insights_output=INSIGHTS_OUTPUT):
    """Reasoning route + the approval + mint hops (the full governed mint route)."""
    events = reasoning_events(insights_output=insights_output)
    events += [
        ev("mcp_approval_request", "pathforward-mint", server_label="pathforward-mint"),
        ev("mcp_call", "pathforward-mint", server_label="pathforward-mint",
           name="pathforward_mint_credential", output='{"mint_state":"minted"}'),
        ev("message", "", text='{"mint_state":"minted"}'),
    ]
    return events


def reasoning_item(events, **over):
    """A reasoning-route suite row (Fabric-scoped, no mint) carrying captured_events."""
    row = {
        "expected_route": list(REASONING_EXPECTED_ROUTE),
        "must_emit": [*REASONING_EXPECTED_ROUTE, "source=fabric-live", "approval required"],
        "feature_area": "prompt_orchestrator_reasoning_route_fabric",
        "risk_category": "captured_route",
        "expected_outcome": "verified_assessment_with_mint_approval_required",
    }
    row.update(over)
    return {**row, "captured_events": events, "sample": {"captured_events": events}}
