"""JSON-RPC MCP endpoint for live Fabric Program Insights.

The MCP tool is intentionally narrow: it asks the published Fabric data agent a
natural-language cohort/program question and returns only the narrative answer.
Credential minting and Evidence Gate logic are not reachable from this server.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from pathforward.agents.client import LLMResponse
from pathforward.agents.foundry import FabricDataAgentClient


TOOL_NAME = "query_program_insights"
SERVER_LABEL = "pathforward-fabric"
PROTOCOL_VERSION = "2025-06-18"
DEFAULT_API_VERSION = "2024-05-01-preview"
DEFAULT_SCOPE = "https://analysis.windows.net/powerbi/api/.default"


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


def _env(name: str, fallback: str = "") -> str:
    return os.environ.get(name, fallback).strip()


def _fabric_base_url() -> str:
    configured = _env("FABRIC_DATA_AGENT_OPENAI_BASE")
    if configured:
        return configured.rstrip("/") + "/"
    workspace_id = _env("FABRIC_WORKSPACE_ID")
    artifact_id = _env("FABRIC_ARTIFACT_ID")
    if not workspace_id or not artifact_id:
        raise RuntimeError(
            "Fabric MCP requires FABRIC_DATA_AGENT_OPENAI_BASE or both "
            "FABRIC_WORKSPACE_ID and FABRIC_ARTIFACT_ID"
        )
    return (
        "https://api.fabric.microsoft.com/v1/"
        f"workspaces/{workspace_id}/dataAgents/{artifact_id}/aiassistant/openai/"
    )


def _fabric_client_from_env() -> FabricDataAgentClient:
    tenant_id = _env("PATHFORWARD_FABRIC_SP_TENANT_ID", _env("AZURE_TENANT_ID"))
    client_id = _env("PATHFORWARD_FABRIC_SP_CLIENT_ID", _env("AZURE_CLIENT_ID"))
    client_secret = _env("PATHFORWARD_FABRIC_SP_CLIENT_SECRET", _env("AZURE_CLIENT_SECRET"))
    if not tenant_id or not client_id or not client_secret:
        raise RuntimeError(
            "Fabric MCP requires service-principal credentials "
            "(PATHFORWARD_FABRIC_SP_* or AZURE_CLIENT_* env vars)"
        )
    return FabricDataAgentClient(
        base_url=_fabric_base_url(),
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        scope=_env("FABRIC_DATA_AGENT_SCOPE", DEFAULT_SCOPE),
        api_version=_env("FABRIC_DATA_AGENT_API_VERSION", DEFAULT_API_VERSION),
    )


def tool_definition() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": (
            "Query the published PathForward Fabric data agent for read-only cohort and program "
            "insights. Returns fabric-live advisory analytics only; it cannot mint credentials."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural-language analytics question for the PathForward Fabric data agent."
                    ),
                }
            },
            "required": ["query"],
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


def _tool_call_result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": _tool_text(payload)}],
        "isError": is_error,
    }
    if not is_error:
        result["structuredContent"] = payload
    return result


def _query_tool(arguments: dict[str, Any], *,
                client_factory: Callable[[], Any] = _fabric_client_from_env) -> dict[str, Any]:
    query = str(arguments.get("query", "")).strip()
    if not query:
        raise ValueError("query is required")
    client = client_factory()
    try:
        response: LLMResponse = client.respond(
            "You are the PathForward Program Insights analyst. Answer only from the connected "
            "Fabric data agent. Include concrete cohort metrics when available.",
            query,
        )
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    return {
        "source": "fabric-live",
        "query": query,
        "narrative": response.output_text,
    }


def handle_jsonrpc(payload: dict[str, Any], *,
                   client_factory: Callable[[], Any] = _fabric_client_from_env
                   ) -> dict[str, Any] | None:
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
                payload = _query_tool(arguments, client_factory=client_factory)
                return _rpc_success(rpc_id, _tool_call_result(payload))
            except Exception as exc:  # noqa: BLE001
                return _rpc_success(
                    rpc_id,
                    _tool_call_result({"source": "fabric-live", "error": str(exc)}, is_error=True),
                )
        raise JsonRpcError(-32601, f"method not found: {method}")
    except JsonRpcError as exc:
        return _rpc_error(rpc_id, exc.code, exc.message)


def handle_http_body(raw_body: bytes, *,
                     client_factory: Callable[[], Any] = _fabric_client_from_env) -> McpHttpResult:
    try:
        payload = json.loads(raw_body.decode("utf-8") if raw_body else "{}")
    except Exception:  # noqa: BLE001
        return _json_response(_rpc_error(None, -32700, "parse error"), status_code=400)
    if not isinstance(payload, dict):
        return _json_response(_rpc_error(None, -32600, "invalid request"), status_code=400)
    response = handle_jsonrpc(payload, client_factory=client_factory)
    if response is None:
        return McpHttpResult(status_code=202, body="", headers={})
    return _json_response(response)
