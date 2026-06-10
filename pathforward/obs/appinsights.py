"""Minimal Application Insights custom-event ingestion.

This emits non-secret proof metadata for Hosted Agent runs when the platform OpenTelemetry export
path is not visible in Application Insights.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
from urllib import request


def _connection_parts(connection_string: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for part in connection_string.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        parts[key.strip().lower()] = value.strip()
    return parts


def emit_custom_event(connection_string: str, name: str, *,
                      properties: dict[str, Any] | None = None,
                      measurements: dict[str, float] | None = None,
                      timeout: float = 5.0) -> bool:
    """Send a single custom event to Application Insights.

    Returns False on missing config or ingestion failure. Product behavior must never depend on this
    telemetry path.
    """
    parts = _connection_parts(connection_string or "")
    ikey = parts.get("instrumentationkey")
    endpoint = (parts.get("ingestionendpoint") or
                "https://dc.services.visualstudio.com/").rstrip("/")
    if not ikey:
        return False

    safe_properties = {
        str(k): "" if v is None else str(v)
        for k, v in (properties or {}).items()
    }
    numeric_measurements = {
        str(k): float(v)
        for k, v in (measurements or {}).items()
        if isinstance(v, (int, float))
    }
    envelope = {
        "name": "Microsoft.ApplicationInsights.Event",
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "iKey": ikey,
        "tags": {
            "ai.cloud.role": safe_properties.get("service.name", "pathforward-hosted"),
            "ai.operation.name": name,
        },
        "data": {
            "baseType": "EventData",
            "baseData": {
                "ver": 2,
                "name": name,
                "properties": safe_properties,
                "measurements": numeric_measurements,
            },
        },
    }
    payload = json.dumps([envelope]).encode("utf-8")
    req = request.Request(
        f"{endpoint}/v2.1/track",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - configured AI endpoint
            return 200 <= getattr(resp, "status", 0) < 300
    except Exception:  # noqa: BLE001 - telemetry must fail open
        return False
