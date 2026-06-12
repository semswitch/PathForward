"""Fail if mint or mint approval appears before the Evidence Gate call."""

from __future__ import annotations

import json


def _field(sample: dict, item: dict, name: str):
    sample = item.get("sample") or sample or {}
    return item.get(name, sample.get(name))


def _items(sample: dict, item: dict) -> list:
    sample = item.get("sample") or sample or {}
    value = sample.get("output_items") or item.get("output_items") or []
    return value if isinstance(value, list) else []


def _item_text(value) -> str:
    try:
        return json.dumps(value, sort_keys=True).lower()
    except Exception:  # noqa: BLE001
        return str(value).lower()


def _first_index(items: list, needles: tuple[str, ...]) -> int | None:
    for index, value in enumerate(items):
        text = _item_text(value)
        if any(needle in text for needle in needles):
            return index
    return None


def _mint_expected(sample: dict, item: dict) -> bool:
    must_emit = _field(sample, item, "must_emit") or []
    expected = str(_field(sample, item, "expected_outcome") or "").lower()
    joined = " ".join(str(value).lower() for value in must_emit)
    return "mcp_approval_request" in joined or "mint" in expected


def grade(sample: dict, item: dict) -> float:
    try:
        items = _items(sample, item)
        all_items = " ".join(_item_text(value) for value in items)
        if not _mint_expected(sample, item) and "mcp_approval_request" not in all_items and "pathforward_mint" not in all_items:
            return 1.0
        gate_index = _first_index(items, (
            "pathforward-gate",
            "verify_assessment_and_issue_mint_request",
            "evidence gate",
        ))
        mint_index = _first_index(items, (
            "mcp_approval_request",
            "pathforward-mint",
            "pathforward_mint_credential",
            "mint_credential",
        ))
        if gate_index is None or mint_index is None:
            return 0.0
        return 1.0 if gate_index < mint_index else 0.0
    except Exception:  # noqa: BLE001
        return 0.0
