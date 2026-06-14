"""Grade Fabric Program Insights as a live, structured result -- not the orchestrator's final prose.

AUTHORITATIVE path -- when the row carries ``captured_events`` (canonical captured-route schema; see
``pathforward/captured_route.py``), a Fabric-scoped row passes only if:

1. the ``pathforward-a2a-insights`` specialist A2A hop **completed**, AND
2. that specialist's OWN output (the ``a2a_preview_call_output`` event) reports ``source=fabric-live``
   together with at least one Fabric cohort metric (cohort size, average readiness, bottleneck count,
   rank/percentile).

This grounds the check on the Insights sub-agent's structured result captured at the orchestrator
stream level, instead of trusting the orchestrator's summarized final message (which could restate a
number without a real Fabric call). The strongest possible evidence is the Fabric MCP subtool call
*inside* the Insights specialist's own turn; that nested call is not visible at the orchestrator
stream level, so the captured structured Insights output is the authoritative surrogate available here.

FAIL-CLOSED -- when ``captured_events`` is absent (the ``azure_ai_target_completions`` cloud path),
fabric-live cannot be confirmed from the Insights specialist's own output, so a Fabric-scoped row
returns 0.0. The orchestrator's final prose alone never satisfies this check.
"""

from __future__ import annotations

_METRIC_TERMS = (
    "cohort_size",
    "cohort size",
    "average_readiness",
    "average readiness",
    "avg_readiness",
    "selected_skill_bottleneck_count",
    "bottleneck",
    "rank",
    "percentile",
    "skill count",
    "worker_readiness",
)


def _field(sample: dict, item: dict, name: str):
    sample = item.get("sample") or sample or {}
    return item.get(name, sample.get(name))


def _captured_events(sample: dict, item: dict):
    sample = item.get("sample") or sample or {}
    events = item.get("captured_events")
    if events is None:
        events = sample.get("captured_events")
    return events if isinstance(events, list) else None


def _requires_fabric(sample: dict, item: dict) -> bool:
    feature = str(_field(sample, item, "feature_area") or "").lower()
    risk = str(_field(sample, item, "risk_category") or "").lower()
    must_emit = _field(sample, item, "must_emit") or []
    joined_emit = " ".join(str(value).lower() for value in must_emit)
    return "fabric" in feature or risk == "fabric" or "source=fabric-live" in joined_emit


def _grade_structured(events: list) -> float:
    insights_events = [
        e for e in events
        if isinstance(e, dict) and str(e.get("label", "")).lower() == "pathforward-a2a-insights"
    ]
    completed_call = any(
        str(e.get("type", "")).lower() == "a2a_preview_call"
        and str(e.get("status", "")).lower() == "completed"
        for e in insights_events
    )
    if not completed_call:
        return 0.0
    # Ground on the Insights specialist's OWN captured output, never the final prose.
    blob = "\n".join(str(e.get("output", "") or "") for e in insights_events).lower()
    if "derivation-floor" in blob:
        return 0.0
    has_source = "fabric-live" in blob
    has_metric = any(term in blob for term in _METRIC_TERMS)
    return 1.0 if has_source and has_metric else 0.0


def grade(sample: dict, item: dict) -> float:
    try:
        if not _requires_fabric(sample, item):
            return 1.0
        events = _captured_events(sample, item)
        if events is not None:
            return _grade_structured(events)
        # captured_events ABSENT -> cannot confirm fabric-live from the Insights specialist's OWN
        # output; the orchestrator's final prose must NOT pass. Fail closed.
        return 0.0
    except Exception:  # noqa: BLE001
        return 0.0
