"""Fail if mint or mint approval appears before the Evidence Gate call."""

from __future__ import annotations

import json


def _field(sample: dict, item: dict, name: str):
    sample = item.get("sample") or sample or {}
    return item.get(name, sample.get(name))


def _items(sample: dict, item: dict) -> list:
    sample = item.get("sample") or sample or {}
    value = sample.get("output_items") or item.get("output_items") or []
    if not isinstance(value, list):
        return []
    return [
        entry for entry in value
        if not (
            isinstance(entry, dict)
            and str(entry.get("type", "")).lower() in {"mcp_list_tools", "tool_definitions"}
        )
    ]


def _item_text(value) -> str:
    try:
        return json.dumps(value, sort_keys=True).lower()
    except Exception:  # noqa: BLE001
        return str(value).lower()


def _is_gate_item(value) -> bool:
    if isinstance(value, dict):
        return (
            str(value.get("server_label", "")).lower() == "pathforward-gate"
            or str(value.get("name", "")).lower() == "verify_assessment_and_issue_mint_request"
        )
    return any(needle in _item_text(value) for needle in ("pathforward-gate", "verify_assessment_and_issue_mint_request"))


def _is_mint_item(value) -> bool:
    if isinstance(value, dict):
        item_type = str(value.get("type", "")).lower()
        return (
            item_type == "mcp_approval_request"
            or str(value.get("server_label", "")).lower() == "pathforward-mint"
            or str(value.get("name", "")).lower() == "pathforward_mint_credential"
        )
    return any(needle in _item_text(value) for needle in ("mcp_approval_request", "pathforward-mint"))


def _first_index(items: list, predicate) -> int | None:
    for index, value in enumerate(items):
        if predicate(value):
            return index
    return None


def _mint_expected(sample: dict, item: dict) -> bool:
    must_emit = _field(sample, item, "must_emit") or []
    expected = str(_field(sample, item, "expected_outcome") or "").lower()
    joined = " ".join(str(value).lower() for value in must_emit)
    return "mcp_approval_request" in joined or "approval_requested" in expected


def grade(sample: dict, item: dict) -> float:
    try:
        items = _items(sample, item)
        gate_index = _first_index(items, _is_gate_item)
        mint_index = _first_index(items, _is_mint_item)
        if mint_index is None:
            return 1.0 if gate_index is not None or not _mint_expected(sample, item) else 0.0
        if gate_index is None:
            return 0.0
        return 1.0 if gate_index < mint_index else 0.0
    except Exception:  # noqa: BLE001
        return 0.0
