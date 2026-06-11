"""Live smoke for the Azure Function MCP mint endpoint and Foundry toolbox attachment.

This smoke is intentionally fail-closed: it proves discovery and tamper rejection, but it does not
mint a credential. Approval-approved minting belongs in the final Orchestrator proof.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pathforward.config import load_settings  # noqa: E402
from pathforward.mcp.mint_server import TOOL_NAME  # noqa: E402
from pathforward.toolbox_mcp import ToolboxMcpClient  # noqa: E402


def _post(url: str, key: str, payload: dict) -> dict:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-functions-key": key,
        },
    )
    with request.urlopen(req, timeout=60) as resp:  # noqa: S310 - configured Function URL
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    settings = load_settings(str(ROOT / ".env"))
    url = settings.mcp_mint_url.strip()
    key = os.environ.get("MCP_MINT_FUNCTION_KEY", "").strip()
    if not url:
        print("FAIL: MCP_MINT_URL is required")
        return 1
    if not key:
        print("FAIL: MCP_MINT_FUNCTION_KEY is required")
        return 1

    init = _post(url, key, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pathforward-smoke", "version": "0.1.0"},
        },
    })
    server_name = init.get("result", {}).get("serverInfo", {}).get("name")
    print(f"direct initialize: {server_name}")

    listed = _post(url, key, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools = listed.get("result", {}).get("tools") or []
    tool_names = [tool.get("name") for tool in tools]
    print(f"direct tools/list: {tool_names}")
    mint_tool = next((tool for tool in tools if tool.get("name") == TOOL_NAME), None)
    if not mint_tool:
        print(f"FAIL: {TOOL_NAME} not listed")
        return 1
    approval = mint_tool.get("_meta", {}).get("tool_configuration", {}).get("require_approval")
    if approval != "always":
        print(f"FAIL: expected require_approval=always, got {approval!r}")
        return 1

    rejected = _post(url, key, {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": TOOL_NAME,
            "arguments": {"mint_request_token": "tampered.invalid"},
        },
    })
    if not rejected.get("result", {}).get("isError"):
        print("FAIL: tampered token did not fail closed")
        return 1
    print("direct tamper rejection: ok")

    if settings.foundry_project_endpoint:
        mcp = ToolboxMcpClient(settings.foundry_project_endpoint, "pathforward-orchestrator-toolbox")
        mcp.initialize()
        search = mcp.call("tools/call", {
            "name": "tool_search",
            "arguments": {"query": "mint credential approval pathforward"},
        }).result
        search_text = "\n".join(
            item.get("text", "") for item in search.get("content") or [] if isinstance(item, dict)
        )
        if "pathforward-mint___pathforward_mint_credential" not in search_text:
            print("FAIL: toolbox tool_search did not return MCP mint tool")
            return 1
        print("toolbox tool_search: MCP mint found")
        via_toolbox = mcp.call("tools/call", {
            "name": "call_tool",
            "arguments": {
                "name": "pathforward-mint___pathforward_mint_credential",
                "arguments": {"mint_request_token": "tampered.invalid"},
            },
        }).result
        if not via_toolbox.get("isError"):
            print("FAIL: toolbox-mediated tampered token did not fail closed")
            return 1
        print("toolbox tamper rejection: ok")

    print("PASS: MCP mint live smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
