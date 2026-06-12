"""Fail if Fabric-scoped rows do not show live Fabric source and metrics."""

from __future__ import annotations

import json


def _field(sample: dict, item: dict, name: str):
    sample = item.get("sample") or sample or {}
    return item.get(name, sample.get(name))


def _surface(sample: dict, item: dict) -> str:
    sample = item.get("sample") or sample or {}
    parts = [sample.get("output_text") or "", item.get("output_text") or ""]
    for key in ("output_items", "messages"):
        value = sample.get(key) or item.get(key) or []
        try:
            parts.append(json.dumps(value, sort_keys=True))
        except Exception:  # noqa: BLE001
            parts.append(str(value))
    return "\n".join(str(part) for part in parts if part)


def _requires_fabric(sample: dict, item: dict) -> bool:
    feature = str(_field(sample, item, "feature_area") or "").lower()
    risk = str(_field(sample, item, "risk_category") or "").lower()
    must_emit = _field(sample, item, "must_emit") or []
    joined_emit = " ".join(str(value).lower() for value in must_emit)
    return "fabric" in feature or risk == "fabric" or "source=fabric-live" in joined_emit


def grade(sample: dict, item: dict) -> float:
    try:
        if not _requires_fabric(sample, item):
            return 1.0
        surface = _surface(sample, item).lower()
        if "derivation-floor" in surface:
            return 0.0
        has_source = "source=fabric-live" in surface or '"source": "fabric-live"' in surface or "fabric-live" in surface
        metric_terms = (
            "cohort size",
            "average readiness",
            "bottleneck",
            "rank",
            "percentile",
            "skill count",
        )
        has_metric = any(term in surface for term in metric_terms)
        return 1.0 if has_source and has_metric else 0.0
    except Exception:  # noqa: BLE001
        return 0.0
