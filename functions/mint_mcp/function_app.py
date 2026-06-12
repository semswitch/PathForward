"""Azure Functions HTTP adapter for the PathForward MCP mint server."""
from __future__ import annotations

import sys
from pathlib import Path

import azure.functions as func

# Local dev and deployment packages include the repo package at the project root or next to this
# function file. Add both candidate roots without relying on ambient working directory.
_HERE = Path(__file__).resolve()
for _candidate in (_HERE.parent, _HERE.parents[2] if len(_HERE.parents) > 2 else _HERE.parent):
    if (_candidate / "pathforward").exists():
        sys.path.insert(0, str(_candidate))

from pathforward.mcp.fabric_server import handle_http_body as handle_fabric_http_body  # noqa: E402
from pathforward.mcp.gate_server import handle_http_body as handle_gate_http_body  # noqa: E402
from pathforward.mcp.mint_server import handle_http_body as handle_mint_http_body  # noqa: E402


app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.function_name(name="pathforward_mint_mcp")
@app.route(route="mcp", methods=["POST"])
def pathforward_mint_mcp(req: func.HttpRequest) -> func.HttpResponse:
    result = handle_mint_http_body(req.get_body())
    return func.HttpResponse(
        body=result.body,
        status_code=result.status_code,
        headers=result.headers,
    )


@app.function_name(name="pathforward_fabric_mcp")
@app.route(route="fabric-mcp", methods=["POST"])
def pathforward_fabric_mcp(req: func.HttpRequest) -> func.HttpResponse:
    result = handle_fabric_http_body(req.get_body())
    return func.HttpResponse(
        body=result.body,
        status_code=result.status_code,
        headers=result.headers,
    )


@app.function_name(name="pathforward_gate_mcp")
@app.route(route="gate-mcp", methods=["POST"])
def pathforward_gate_mcp(req: func.HttpRequest) -> func.HttpResponse:
    result = handle_gate_http_body(req.get_body())
    return func.HttpResponse(
        body=result.body,
        status_code=result.status_code,
        headers=result.headers,
    )
