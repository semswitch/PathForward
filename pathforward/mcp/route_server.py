"""JSON-RPC MCP endpoint for deterministic PathForward route facts.

Given a worker (and an optional target role), this server returns the code-derived route facts the
Orchestrator needs to drive `/pathforward` autonomously from a minimal prompt: the admissible
certification-gap skills (cert gap INTERSECT assessable), their deterministic driving edge ids, and
the approved grounding refs per admissible skill. It is READ-ONLY: it never mints, never issues a
token, and never sets a verified status. The Orchestrator may CALL this tool but can never fabricate
or override these facts; the Evidence Gate independently re-derives and re-checks everything it
receives, so a wrong route fact can never make an ungrounded item pass.

This exposes, as a tool, the same deterministic derivation the harness previously injected into the
prompt (`build_seed()` + `pathforward/iq/traversal.py`). It is code, not an agent (contract item 1).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import build_seed


TOOL_NAME = "resolve_route_facts"
SERVER_LABEL = "pathforward-route"
PROTOCOL_VERSION = "2025-06-18"


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class McpHttpResult:
    status_code: int
    body: str
    headers: dict[str, str]


def _json_response(payload: dict[str, Any], status_code: int = 200) -> McpHttpResult:
    return McpHttpResult(
        status_code=status_code,
        body=json.dumps(payload, separators=(",", ":")),
        headers={"Content-Type": "application/json"},
    )


def _rpc_success(rpc_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _rpc_error(rpc_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}


def _tool_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def tool_definition() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": (
            "Resolve deterministic PathForward route facts for a worker: target role, existing "
            "skills, admissible certification-gap skills (cert gap that is assessable), the "
            "deterministic driving edge id per admissible skill, and the approved grounding ref ids "
            "per admissible skill. Read-only: never mints, issues a token, or sets a verified status."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "worker_id": {"type": "string"},
                "target_role_id": {
                    "type": "string",
                    "description": "Optional; defaults to the worker's own target role.",
                },
            },
            "required": ["worker_id"],
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "_meta": {
            "tool_configuration": {
                "type": "mcp",
                "server_label": SERVER_LABEL,
                "require_approval": "never",
            }
        },
    }


def _resolve_route_facts(args: dict[str, Any]) -> dict[str, Any]:
    worker_id = str(args.get("worker_id", "")).strip()
    if not worker_id:
        raise ValueError("worker_id is required")

    onto = build_seed()
    if worker_id not in onto.workers:
        raise ValueError("unknown worker_id")
    worker = onto.workers[worker_id]

    target_role_id = str(args.get("target_role_id", "")).strip() or worker.target_role_id
    if target_role_id not in onto.roles:
        raise ValueError("unknown target_role_id")
    if worker.target_role_id != target_role_id:
        raise ValueError("target_role_id does not match the worker's target role")
    role = onto.roles[target_role_id]

    # Deterministic derivation (the ONLY place route facts come from): the cert gap in role order,
    # narrowed to skills that actually have learning content to assess.
    cert_gap = dv.cert_gap_skill_ids(worker, role)
    admissible = [sid for sid in cert_gap if traversal.is_assessable(sid, onto)]
    driving_edge_ids = {sid: dv.certgap_edge_id(worker_id, sid) for sid in admissible}
    approved_ref_map = {
        sid: list(traversal.approved_refs(worker, onto.skills[sid], onto)) for sid in admissible
    }
    return {
        "status": "resolved",
        "worker_id": worker_id,
        "target_role_id": target_role_id,
        "target_role": role.name,
        "existing_skills": list(worker.has_skill_ids),
        "cert_gap_skill_ids": list(cert_gap),
        "admissible_skill_ids": admissible,
        "driving_edge_ids": driving_edge_ids,
        "approved_ref_map": approved_ref_map,
        "readiness": dv.readiness_score(worker, role),
        "derivation_version": dv.DERIVATION_VERSION,
    }


def _tool_call_result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": _tool_text(payload)}],
        "isError": is_error,
    }
    if not is_error:
        result["structuredContent"] = payload
    return result


def _input_rejection(message: str) -> dict[str, Any]:
    return {"status": "rejected", "error": message, "admissible_skill_ids": []}


def handle_jsonrpc(payload: dict[str, Any]) -> dict[str, Any] | None:
    method = payload.get("method")
    rpc_id = payload.get("id")
    params = payload.get("params") or {}

    if method == "notifications/initialized" and "id" not in payload:
        return None

    try:
        if method == "initialize":
            return _rpc_success(rpc_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_LABEL, "version": "0.1.0"},
            })
        if method == "tools/list":
            return _rpc_success(rpc_id, {"tools": [tool_definition()]})
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name != TOOL_NAME:
                raise JsonRpcError(-32602, f"unknown tool: {name}")
            try:
                result = _resolve_route_facts(arguments)
                return _rpc_success(rpc_id, _tool_call_result(result))
            except ValueError as exc:
                return _rpc_success(
                    rpc_id,
                    _tool_call_result(_input_rejection(str(exc)), is_error=False),
                )
            except Exception as exc:  # noqa: BLE001
                return _rpc_success(
                    rpc_id,
                    _tool_call_result({"status": "rejected", "error": str(exc)}, is_error=True),
                )
        raise JsonRpcError(-32601, f"method not found: {method}")
    except JsonRpcError as exc:
        return _rpc_error(rpc_id, exc.code, exc.message)


def handle_http_body(raw_body: bytes) -> McpHttpResult:
    try:
        payload = json.loads(raw_body.decode("utf-8") if raw_body else "{}")
    except Exception:  # noqa: BLE001
        return _json_response(_rpc_error(None, -32700, "parse error"), status_code=400)
    if not isinstance(payload, dict):
        return _json_response(_rpc_error(None, -32600, "invalid request"), status_code=400)
    response = handle_jsonrpc(payload)
    if response is None:
        return McpHttpResult(status_code=202, body="", headers={})
    return _json_response(response)
