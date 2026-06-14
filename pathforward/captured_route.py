"""Canonical captured-route schema for the PathForward Prompt Orchestrator proof.

This turns a live Prompt Orchestrator run into ONE explicit, structured event list -- the project's
OWN schema, not the Foundry eval SDK's flattened ``sample.output``. It is the authoritative input for
the capture-then-score evaluators (see ``scripts/capture_and_score_route.py``).

Two live sources normalize into the same ``captured_events`` list:

* **streamed probe** -- ``response.output_item.done`` item dicts from
  ``scripts/probe_orchestrator_stream.py`` (single-shot Responses API stream).
* **staged proof** -- the redacted ``rows`` of an ``integrated-live-*.json`` proof from
  ``scripts/smoke_integrated_orchestrator_live.py`` (multi-turn, includes the approval + mint hops).

Why this exists: the Foundry cloud eval (``azure_ai_target_completions``) captures only the MCP tool
calls in ``sample.output`` and OMITS the ``a2a_preview_call`` rows, so a genuine full A2A route reads
as ``route -> gate`` with seemingly fabricated specialist summaries. Grading an explicit
``captured_events`` list removes that ambiguity: every Curator/Generator/Critic/Planner/Insights hop
is a first-class, status-bearing event with the sub-agent's own output attached.

Canonical event (one per real route step; ``reasoning`` and tool-discovery items are dropped)::

    {
      "index": int,          # 1-based position in the executed route
      "type": str,           # mcp_call | a2a_preview_call | a2a_preview_call_output
                             #   | mcp_approval_request | message
      "label": str,          # canonical id: server_label or name
                             #   ("pathforward-route", "pathforward-a2a-curator"); "" for messages
      "name": str,           # raw tool/function or A2A link name
      "server_label": str,   # raw MCP server label ("" for A2A)
      "status": str,         # "completed" | ... (milestone-only items default to "completed")
      "id": str,             # output-item id (mcp_..., fc_..., msg_...)
      "call_id": str,        # A2A call correlation id ("" otherwise)
      "output": str,         # tool / sub-agent output text, redacted (mcp_call, *_output)
      "text": str,           # assistant message text, redacted (message)
      "role": str,           # message role ("" otherwise)
    }

The evaluators that consume ``captured_events`` (``required_tool_calls``, ``fabric_live_source``) stay
self-contained stdlib code so Foundry can register them standalone -- they only READ this structure,
they never import this module. The producers (probe + capture_and_score) build it via this module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "pf-captured-route/v1"

# Item types that are noise for route grading.
_DISCOVERY_TYPES = {"mcp_list_tools", "tool_definitions"}
_REASONING_TYPES = {"reasoning"}

# Route-step item types kept as canonical events.
ROUTE_EVENT_TYPES = {
    "mcp_call",
    "a2a_preview_call",
    "a2a_preview_call_output",
    "mcp_approval_request",
    "message",
}

# Items that have no tool-style completion status -- their mere presence in a completed run IS the
# milestone, so the normalizer stamps them "completed" (a genuinely failed tool call keeps its real
# non-completed status and correctly fails grading).
_MILESTONE_TYPES = {"mcp_approval_request", "message"}

_MAX_TEXT = 8000


def _get(obj: Any, name: str, default: Any = "") -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for entry in value:
            if isinstance(entry, dict):
                parts.append(str(entry.get("text") or entry.get("content") or entry.get("output") or ""))
            else:
                parts.append(str(entry))
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        try:
            return json.dumps(value, sort_keys=True)
        except Exception:  # noqa: BLE001
            return str(value)
    return str(value)


def _redact_text(value: str) -> str:
    """Defense-in-depth: strip mint tokens / JWT-like bearer values from any captured text."""
    value = re.sub(r'("?mint_request_token"?\s*[:=]\s*"?)[^"\s,}]+', r"\1[REDACTED]", value)
    value = re.sub(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)?", "[REDACTED_TOKEN]", value)
    return value


def _truncate(value: str, limit: int = _MAX_TEXT) -> str:
    if len(value) > limit:
        return value[:limit] + "...[truncated]"
    return value


def _clean(value: Any) -> str:
    text = _coerce_text(value)
    if not text:
        return ""
    return _truncate(_redact_text(text))


def _canonical_event(
    *,
    index: int,
    itype: str,
    name: str,
    server_label: str,
    status: str,
    item_id: str,
    call_id: str,
    output: Any,
    text: Any,
    role: str,
) -> dict[str, Any]:
    label = (server_label or name).strip().lower()
    norm_status = (status or "").strip()
    if not norm_status and itype in _MILESTONE_TYPES:
        norm_status = "completed"
    return {
        "index": index,
        "type": itype,
        "label": label,
        "name": name,
        "server_label": server_label,
        "status": norm_status,
        "id": item_id,
        "call_id": call_id,
        "output": _clean(output),
        "text": _clean(text),
        "role": role or "",
    }


def _is_route_event(itype: str) -> bool:
    return itype in ROUTE_EVENT_TYPES and itype not in _DISCOVERY_TYPES and itype not in _REASONING_TYPES


def event_from_stream_item(item: Any, index: int) -> dict[str, Any] | None:
    """Normalize one ``response.output_item.done`` item (streamed probe) -> canonical event."""
    itype = str(_get(item, "type", "")).strip().lower()
    if not _is_route_event(itype):
        return None
    name = str(_get(item, "name", "") or "")
    server_label = str(_get(item, "server_label", "") or "")
    role = str(_get(item, "role", "") or "")
    output: Any = _get(item, "output", "")
    text: Any = ""
    if itype == "message":
        text = _get(item, "content", "") or output or ""
        output = ""
    return _canonical_event(
        index=index,
        itype=itype,
        name=name,
        server_label=server_label,
        status=str(_get(item, "status", "") or ""),
        item_id=str(_get(item, "id", "") or ""),
        call_id=str(_get(item, "call_id", "") or ""),
        output=output,
        text=text,
        role=role,
    )


def event_from_staged_row(row: dict[str, Any], index: int) -> dict[str, Any] | None:
    """Normalize one redacted ``integrated-live-*.json`` proof row (staged) -> canonical event.

    Staged rows store text under ``output_preview`` / ``message_preview`` (already redacted + short)
    and do not carry an A2A ``call_id``; everything else maps 1:1.
    """
    itype = str(row.get("type", "")).strip().lower()
    if not _is_route_event(itype):
        return None
    name = str(row.get("name", "") or "")
    server_label = str(row.get("server_label", "") or "")
    output: Any = row.get("output_preview", "") or ""
    text: Any = ""
    if itype == "message":
        text = row.get("message_preview", "") or ""
        output = ""
    return _canonical_event(
        index=index,
        itype=itype,
        name=name,
        server_label=server_label,
        status=str(row.get("status", "") or ""),
        item_id=str(row.get("id", "") or ""),
        call_id=str(row.get("call_id", "") or ""),
        output=output,
        text=text,
        role=str(row.get("role", "") or ""),
    )


def events_from_stream_items(items: list[Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in items:
        event = event_from_stream_item(item, len(events) + 1)
        if event is not None:
            events.append(event)
    return events


def events_from_staged_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        event = event_from_staged_row(row, len(events) + 1)
        if event is not None:
            events.append(event)
    return events


def build_canonical_capture(
    *,
    agent: str,
    query: str,
    response_id: str,
    status: str,
    source: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the canonical capture object written to ``.agents/evidence/captured-route-*.json``."""
    return {
        "schema_version": SCHEMA_VERSION,
        "agent": agent,
        "source": source,
        "query": query,
        "response_id": response_id,
        "status": status,
        "captured_events": events,
    }


def reconstruct_legacy_surface(captured_events: list[dict[str, Any]]) -> dict[str, Any]:
    """Rebuild the ``{output_items, output, output_text}`` surface the un-migrated evaluators read.

    The token-exposure / credential / abstain / gate-order / mint-approval evaluators still read
    ``output_items`` (type/server_label/name/role/content/output) and ``output_text``. We derive that
    surface FROM ``captured_events`` so every evaluator scores the same single source of truth.
    """
    items: list[dict[str, Any]] = []
    texts: list[str] = []
    for event in captured_events:
        item: dict[str, Any] = {
            "type": event.get("type", ""),
            "status": event.get("status", ""),
            "id": event.get("id", ""),
        }
        if event.get("server_label"):
            item["server_label"] = event["server_label"]
        if event.get("name"):
            item["name"] = event["name"]
        if event.get("output"):
            item["output"] = event["output"]
        if event.get("type") == "message":
            item["role"] = event.get("role") or "assistant"
            item["content"] = event.get("text", "")
            if event.get("text"):
                texts.append(event["text"])
        items.append(item)
    return {"output_items": items, "output": items, "output_text": "\n".join(texts)}


def load_capture(path: str | Path) -> dict[str, Any]:
    """Load + lightly validate a canonical capture file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"{path}: schema_version {data.get('schema_version')!r} != expected {SCHEMA_VERSION!r}"
        )
    if not isinstance(data.get("captured_events"), list):
        raise ValueError(f"{path}: captured_events must be a list")
    return data
