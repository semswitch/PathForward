"""Grade the required PathForward route as an ordered, structured event sequence.

AUTHORITATIVE path -- the row carries ``captured_events`` (the project's canonical captured-route
schema; see ``pathforward/captured_route.py`` + ``scripts/capture_and_score_route.py``). We grade the
COMPLETED route as an ordered subsequence: each required ``(type, label)`` step must appear, in order,
among the completed captured events. This is unambiguous -- every Curator/Generator/Critic/Planner/
Insights A2A hop is a first-class, status-bearing event.

    REQUIRED (canonical reasoning spine, when a row asks for the full route):
        ("mcp_call",          "pathforward-route")
        ("a2a_preview_call",  "pathforward-a2a-curator")
        ("a2a_preview_call",  "pathforward-a2a-generator")
        ("a2a_preview_call",  "pathforward-a2a-critic")
        ("mcp_call",          "pathforward-gate")
        ("a2a_preview_call",  "pathforward-a2a-planner")
        ("a2a_preview_call",  "pathforward-a2a-insights")

The actual required sequence is DATA-DRIVEN from the row's ``expected_route`` (preferred) or
``must_emit`` so the same evaluator serves the reasoning route, the full mint route
(adds ``mcp_approval_request`` + ``pathforward-mint``), and ABSTAIN rows (which require little/none).

FAIL-CLOSED for A2A routes -- when ``captured_events`` is absent (ONLY the
``azure_ai_target_completions`` cloud path, which UNDER-captures ``a2a_preview_call`` rows in
``sample.output``), a required A2A route CANNOT be confirmed, so we return 0.0 rather than vacuously
pass on a text scan. A non-A2A requirement (route/gate only) still uses the legacy text-presence check
so the cloud registration does not hard-break. The structured ``captured_events`` path
(capture-then-score) is the only way an A2A route passes.
"""

from __future__ import annotations

import json

# Documentation reference: the canonical full reasoning route. The live requirement is taken from the
# row (expected_route / must_emit), which encodes exactly this for the reasoning-route suite.
CANONICAL_REASONING_ROUTE = [
    ("mcp_call", "pathforward-route"),
    ("a2a_preview_call", "pathforward-a2a-curator"),
    ("a2a_preview_call", "pathforward-a2a-generator"),
    ("a2a_preview_call", "pathforward-a2a-critic"),
    ("mcp_call", "pathforward-gate"),
    ("a2a_preview_call", "pathforward-a2a-planner"),
    ("a2a_preview_call", "pathforward-a2a-insights"),
]

_MCP_TOOL_IDS = {"pathforward-route", "pathforward-gate", "pathforward-mint"}


def _field(sample: dict, item: dict, name: str):
    sample = item.get("sample") or sample or {}
    return item.get(name, sample.get(name))


def _captured_events(sample: dict, item: dict):
    sample = item.get("sample") or sample or {}
    events = item.get("captured_events")
    if events is None:
        events = sample.get("captured_events")
    return events if isinstance(events, list) else None


def _step_for(token: str):
    """Map a route token (from expected_route / must_emit) to a required (type, label) pair."""
    text = str(token).strip().lower()
    if not text:
        return None
    if text == "mcp_approval_request":
        return ("mcp_approval_request", "")  # label varies (pathforward-mint); match on type only
    if text.startswith("pathforward-a2a-"):
        return ("a2a_preview_call", text)
    if text in _MCP_TOOL_IDS or text.startswith("pathforward-"):
        return ("mcp_call", text)
    return None  # non-tool tokens ("approval required", "source=fabric-live", ...)


def _required_sequence(sample: dict, item: dict) -> list[tuple[str, str]]:
    explicit = _field(sample, item, "expected_route")
    tokens = explicit if explicit else (_field(sample, item, "must_emit") or [])
    steps: list[tuple[str, str]] = []
    for token in tokens:
        step = _step_for(token)
        if step is not None:
            steps.append(step)
    return steps


def _grade_structured(events: list, required: list[tuple[str, str]]) -> float:
    if not required:
        return 1.0
    completed = [
        (str(e.get("type", "")).lower(), str(e.get("label", "")).lower())
        for e in events
        if isinstance(e, dict) and str(e.get("status", "")).lower() == "completed"
    ]
    pos = 0
    for rtype, rlabel in required:
        found = False
        while pos < len(completed):
            ctype, clabel = completed[pos]
            pos += 1
            if ctype == rtype and (not rlabel or clabel == rlabel):
                found = True
                break
        if not found:
            return 0.0
    return 1.0


# --- legacy text-surface fallback (demoted cloud path only) ---------------------------------------

def _items_surface(sample: dict, item: dict) -> str:
    sample = item.get("sample") or sample or {}
    value = sample.get("output_items") or item.get("output_items") or []
    if isinstance(value, list):
        value = [
            entry for entry in value
            if not (
                isinstance(entry, dict)
                and str(entry.get("type", "")).lower() in {"mcp_list_tools", "tool_definitions"}
            )
        ]
    try:
        return json.dumps(value, sort_keys=True).lower()
    except Exception:  # noqa: BLE001
        return str(value).lower()


def _legacy_required(sample: dict, item: dict) -> list[str]:
    must_emit = _field(sample, item, "must_emit") or []
    required = []
    for value in must_emit:
        text = str(value).strip()
        if text.startswith("pathforward-") or text == "mcp_approval_request":
            required.append(text.lower())
    return required


def _grade_legacy(sample: dict, item: dict) -> float:
    required = _legacy_required(sample, item)
    if not required:
        return 1.0
    surface = _items_surface(sample, item)
    return 1.0 if all(tool in surface for tool in required) else 0.0


def grade(sample: dict, item: dict) -> float:
    try:
        required = _required_sequence(sample, item)
        events = _captured_events(sample, item)
        if events is not None:
            return _grade_structured(events, required)
        # captured_events ABSENT -> demoted cloud path (under-captures a2a_preview_call rows). A required
        # A2A route cannot be confirmed here, so fail closed instead of vacuously passing a text scan.
        if any(rtype == "a2a_preview_call" for rtype, _ in required):
            return 0.0
        return _grade_legacy(sample, item)
    except Exception:  # noqa: BLE001
        return 0.0
