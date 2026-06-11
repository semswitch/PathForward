"""JSON-RPC MCP endpoint for governed credential minting.

This module is framework-neutral so it can be tested without the Azure Functions runtime. The
Azure Function in `functions/mint_mcp/function_app.py` is only the HTTP adapter.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from pathforward.credential.mcp_mint import (
    McpMintError,
    MintReplayStore,
    mint_from_mcp_request,
    open_mcp_mint_request,
)
from pathforward.iq.seed import build_seed


TOOL_NAME = "pathforward_mint_credential"
SERVER_LABEL = "pathforward-mint"
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


class AzureTableMintReplayStore:
    """Durable replay guard for Azure Functions.

    Uses a Table Storage insert as an atomic claim. A duplicate entity means the mint request was
    already used.
    """

    def __init__(self, *, connection_string: str, table_name: str = "PathForwardMintReplay"):
        if not connection_string:
            raise ValueError("connection_string is required")
        self.connection_string = connection_string
        self.table_name = table_name
        self._client = None

    def _table(self):
        if self._client is None:
            from azure.data.tables import TableServiceClient

            service = TableServiceClient.from_connection_string(self.connection_string)
            self._client = service.create_table_if_not_exists(self.table_name)
        return self._client

    def claim(self, request_id: str) -> bool:
        from azure.core.exceptions import ResourceExistsError

        entity = {
            "PartitionKey": "mcp-mint",
            "RowKey": request_id,
        }
        try:
            self._table().create_entity(entity=entity)
            return True
        except ResourceExistsError:
            return False


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
            "Mint a PathForward competency credential from a signed, code-issued mint request token. "
            "Requires explicit user approval in the Foundry toolbox before invocation."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "mint_request_token": {
                    "type": "string",
                    "description": (
                        "Signed token created after Evidence Gate verification. Do not provide raw "
                        "credential facts or verified flags."
                    ),
                }
            },
            "required": ["mint_request_token"],
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        "_meta": {
            "tool_configuration": {
                "type": "mcp",
                "server_label": SERVER_LABEL,
                "require_approval": "always",
            }
        },
    }


def _replay_store_from_env() -> MintReplayStore | None:
    connection = (
        os.environ.get("PATHFORWARD_MINT_REPLAY_TABLE_CONNECTION", "").strip()
        or os.environ.get("AzureWebJobsStorage", "").strip()
    )
    if not connection or connection.lower() == "usedevelopmentstorage=true":
        return None
    table = os.environ.get("PATHFORWARD_MINT_REPLAY_TABLE", "PathForwardMintReplay").strip()
    return AzureTableMintReplayStore(connection_string=connection, table_name=table)


def _mint_tool(arguments: dict[str, Any], *,
               replay_store: MintReplayStore | None = None) -> dict[str, Any]:
    token = str(arguments.get("mint_request_token", "")).strip()
    if not token:
        raise McpMintError("mint_request_token is required")

    # Open once to discover worker/role from signed payload. `mint_from_mcp_request` opens and
    # validates again before issuing, so this lookup cannot authorize minting by itself.
    request = open_mcp_mint_request(token)
    onto = build_seed()
    try:
        worker = onto.workers[request.worker_id]
        role = onto.roles[request.target_role_id]
    except KeyError as exc:
        raise McpMintError("MCP mint request references an unknown worker or role") from exc

    credential = mint_from_mcp_request(
        worker,
        role,
        token,
        replay_store=replay_store or _replay_store_from_env(),
    )
    return {
        "status": "minted",
        "request_id": request.request_id,
        "credential": credential.to_doc(),
    }


def _tool_call_result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": _tool_text(payload)}],
        "isError": is_error,
    }
    if not is_error:
        result["structuredContent"] = payload
    return result


def handle_jsonrpc(payload: dict[str, Any], *,
                   replay_store: MintReplayStore | None = None) -> dict[str, Any] | None:
    method = payload.get("method")
    rpc_id = payload.get("id")
    params = payload.get("params") or {}

    # Notification: no response body by JSON-RPC convention.
    if method == "notifications/initialized" and "id" not in payload:
        return None

    try:
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_LABEL, "version": "0.1.0"},
            }
            return _rpc_success(rpc_id, result)
        if method == "tools/list":
            return _rpc_success(rpc_id, {"tools": [tool_definition()]})
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name != TOOL_NAME:
                raise JsonRpcError(-32602, f"unknown tool: {name}")
            try:
                minted = _mint_tool(arguments, replay_store=replay_store)
                return _rpc_success(rpc_id, _tool_call_result(minted))
            except McpMintError as exc:
                return _rpc_success(
                    rpc_id,
                    _tool_call_result({"status": "rejected", "error": str(exc)}, is_error=True),
                )
        raise JsonRpcError(-32601, f"method not found: {method}")
    except JsonRpcError as exc:
        return _rpc_error(rpc_id, exc.code, exc.message)


def handle_http_body(raw_body: bytes, *,
                     replay_store: MintReplayStore | None = None) -> McpHttpResult:
    try:
        payload = json.loads(raw_body.decode("utf-8") if raw_body else "{}")
    except Exception:  # noqa: BLE001
        return _json_response(_rpc_error(None, -32700, "parse error"), status_code=400)
    if not isinstance(payload, dict):
        return _json_response(_rpc_error(None, -32600, "invalid request"), status_code=400)
    response = handle_jsonrpc(payload, replay_store=replay_store)
    if response is None:
        return McpHttpResult(status_code=202, body="", headers={})
    return _json_response(response)
