"""Fail if row-required live tools are missing from sample.output_items."""

from __future__ import annotations

import json


def _field(sample: dict, item: dict, name: str):
    sample = item.get("sample") or sample or {}
    return item.get(name, sample.get(name))


def _items_surface(sample: dict, item: dict) -> str:
    sample = item.get("sample") or sample or {}
    value = sample.get("output_items") or item.get("output_items") or []
    try:
        return json.dumps(value, sort_keys=True).lower()
    except Exception:  # noqa: BLE001
        return str(value).lower()


def _required_tools(sample: dict, item: dict) -> list[str]:
    must_emit = _field(sample, item, "must_emit") or []
    required = []
    for value in must_emit:
        text = str(value).strip()
        if text.startswith("pathforward-") or text == "mcp_approval_request":
            required.append(text.lower())
    return required


def grade(sample: dict, item: dict) -> float:
    try:
        required = _required_tools(sample, item)
        if not required:
            return 1.0
        surface = _items_surface(sample, item)
        return 1.0 if all(tool in surface for tool in required) else 0.0
    except Exception:  # noqa: BLE001
        return 0.0
