"""Non-secret telemetry events for hosted MCP tools."""
from __future__ import annotations

import json
import os
from typing import Any, Callable

from pathforward.obs.appinsights import emit_custom_event


def _connection_string() -> str:
    return (
        os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
        or os.environ.get("AZURE_MONITOR_CONNECTION_STRING", "").strip()
    )


def _content_doc(result: dict[str, Any]) -> dict[str, Any]:
    for item in result.get("content") or []:
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _mcp_doc(raw_body: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        body = json.loads(raw_body or "{}")
    except Exception:  # noqa: BLE001
        return {}, {}
    if not isinstance(body, dict):
        return {}, {}
    result = body.get("result") if isinstance(body.get("result"), dict) else {}
    structured = result.get("structuredContent") if isinstance(result.get("structuredContent"), dict) else {}
    return result, structured or _content_doc(result)


def _safe_props(route: str, status_code: int, result: dict[str, Any],
                doc: dict[str, Any]) -> dict[str, Any]:
    props = {
        "service.name": "pathforward-mcp-function",
        "pf.route": route,
        "pf.status_code": str(status_code),
        "pf.status": str(doc.get("status", "unknown")),
        "pf.is_error": str(bool(result.get("isError"))),
    }
    for source, target in (
        ("worker_id", "pf.worker"),
        ("target_role_id", "pf.target_role"),
        ("skill_id", "pf.skill"),
        ("driving_edge_id", "pf.driving_edge"),
    ):
        value = doc.get(source)
        if value is not None:
            props[target] = str(value)
    if isinstance(doc.get("mint_request"), dict):
        request = doc["mint_request"].get("request") if isinstance(doc["mint_request"].get("request"), dict) else {}
        props["pf.mint_request_created"] = str(bool(request))
        if request.get("request_id"):
            props["pf.request_id"] = str(request["request_id"])
    if isinstance(doc.get("credential"), dict):
        subject = doc["credential"].get("credentialSubject")
        if isinstance(subject, dict):
            for source, target in (
                ("worker_id", "pf.worker"),
                ("target_role_id", "pf.target_role"),
                ("skill_id", "pf.skill"),
                ("cited_edge_id", "pf.driving_edge"),
            ):
                value = subject.get(source)
                if value is not None:
                    props[target] = str(value)
        props["pf.credential_issued"] = "true"
    return props


def _measurements(doc: dict[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    for source, target in (
        ("approved_ref_ids", "pf.approved_ref_count"),
        ("retrieved_ref_ids", "pf.retrieved_ref_count"),
        ("effective_allowed_ref_ids", "pf.effective_ref_count"),
    ):
        value = doc.get(source)
        if isinstance(value, list):
            values[target] = float(len(value))
    credential = doc.get("credential")
    if isinstance(credential, dict):
        subject = credential.get("credentialSubject")
        if isinstance(subject, dict) and isinstance(subject.get("readiness"), (int, float)):
            values["pf.readiness"] = float(subject["readiness"])
    return values


def emit_mcp_result_event(route: str, raw_body: str, status_code: int, *,
                          emitter: Callable[..., bool] = emit_custom_event,
                          connection_string: str | None = None) -> bool:
    """Emit one sanitized custom event for an MCP response.

    The event intentionally excludes request bodies, prompts, citations, credential evidence, and
    `mint_request_token` values.
    """
    result, doc = _mcp_doc(raw_body)
    if not doc and not result:
        return False
    if not any(key in doc for key in ("status", "credential", "mint_request")):
        return False
    if route == "gate-mcp":
        event_name = "pathforward.mcp.gate"
    elif route == "mcp":
        event_name = "pathforward.mcp.mint"
    elif route == "fabric-mcp":
        event_name = "pathforward.mcp.fabric"
    else:
        event_name = "pathforward.mcp.response"
    return emitter(
        connection_string if connection_string is not None else _connection_string(),
        event_name,
        properties=_safe_props(route, status_code, result, doc),
        measurements=_measurements(doc),
    )
