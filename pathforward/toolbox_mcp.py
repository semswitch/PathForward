"""Minimal Foundry Toolbox MCP client for live proof scripts.

The production claim for Foundry Skills is `resources/list` + `resources/read` against the toolbox
MCP endpoint. This helper intentionally implements only the tiny JSON-RPC surface the PathForward
smokes need.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

TOKEN_SCOPE = "https://ai.azure.com/.default"


@dataclass
class McpResponse:
    result: dict[str, Any]
    session_id: str = ""


class ToolboxMcpClient:
    def __init__(self, endpoint: str, toolbox_name: str):
        self.url = f"{endpoint.rstrip('/')}/toolboxes/{toolbox_name}/mcp?api-version=v1"
        self.session_id = ""
        self._next_id = 1

    @staticmethod
    def _token() -> str:
        from azure.identity import DefaultAzureCredential
        return DefaultAzureCredential().get_token(TOKEN_SCOPE).token

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._token()}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Foundry-Features": "Toolboxes=V1Preview",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        return headers

    @staticmethod
    def _parse_response(resp: httpx.Response) -> dict[str, Any]:
        text = resp.text.strip()
        if not text:
            return {}
        if "text/event-stream" in resp.headers.get("content-type", ""):
            payloads = []
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    payloads.append(line.partition(":")[2].strip())
            text = payloads[-1] if payloads else "{}"
        return json.loads(text)

    def call(self, method: str, params: dict[str, Any] | None = None) -> McpResponse:
        rid = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params
        resp = httpx.post(self.url, headers=self._headers(), json=payload, timeout=60.0)
        if resp.status_code >= 400:
            raise RuntimeError(f"MCP {method} failed: HTTP {resp.status_code}: {resp.text[:1000]}")
        if sid := resp.headers.get("mcp-session-id"):
            self.session_id = sid
        parsed = self._parse_response(resp)
        if "error" in parsed:
            raise RuntimeError(f"MCP {method} error: {parsed['error']}")
        return McpResponse(result=parsed.get("result") or {}, session_id=self.session_id)

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        resp = httpx.post(self.url, headers=self._headers(), json=payload, timeout=60.0)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"MCP notification {method} failed: HTTP {resp.status_code}: {resp.text[:1000]}")

    def initialize(self) -> dict[str, Any]:
        init = self.call("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pathforward-toolbox-mcp", "version": "0.1.0"},
        })
        self.notify("notifications/initialized")
        return init.result


def read_skill_from_toolbox(endpoint: str, toolbox_name: str, skill_name: str) -> tuple[str, dict]:
    """Return `(skill_body, evidence)` for `skill://{skill_name}/SKILL.md` from the toolbox MCP endpoint."""
    mcp = ToolboxMcpClient(endpoint, toolbox_name)
    init = mcp.initialize()
    tools = mcp.call("tools/list").result.get("tools") or []
    resources = mcp.call("resources/list").result.get("resources") or []
    resource_uris = [r.get("uri") for r in resources if isinstance(r, dict)]
    expected = f"skill://{skill_name}"
    skill_uri = next((uri for uri in resource_uris
                      if uri == expected or uri == f"{expected}/SKILL.md"), "")
    if not skill_uri:
        raise RuntimeError(f"no {expected} resource listed by toolbox MCP resources")
    read = mcp.call("resources/read", {"uri": skill_uri}).result
    parts: list[str] = []
    for item in read.get("contents") or []:
        text = item.get("text") if isinstance(item, dict) else None
        if text:
            parts.append(text)
    body = "\n\n".join(parts).strip()
    if not body:
        raise RuntimeError(f"resources/read returned no text for {skill_uri}")
    return body, {
        "protocol": init.get("protocolVersion"),
        "tools": [t.get("name") or t.get("type") or "(unnamed)"
                  for t in tools if isinstance(t, dict)],
        "resources": resource_uris,
        "skill_uri": skill_uri,
        "skill_chars": len(body),
    }
