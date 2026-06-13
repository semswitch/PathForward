"""Read-only smoke for the deployed PathForward MCP endpoints (mint / gate / fabric / route).

Posts JSON-RPC `initialize` to each route and `tools/call resolve_route_facts` to the route resolver,
then prints only non-secret results. Auth uses the function key (x-functions-key header) read from
MCP_MINT_FUNCTION_KEY in .env; the key value is never printed. No tool with side effects is invoked.

    .venv\\Scripts\\python.exe scripts\\smoke_mcp_endpoints.py
"""
from __future__ import annotations

import json
import os
import sys
from urllib import error, request

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.config import load_settings  # noqa: E402

ROUTES = {
    "mint": "/api/mcp",
    "gate": "/api/gate-mcp",
    "fabric": "/api/fabric-mcp",
    "route": "/api/route-mcp",
}


def _base(mint_url: str) -> str:
    url = mint_url.rstrip("/")
    if not url.endswith("/api/mcp"):
        raise SystemExit("MCP_MINT_URL must end with /api/mcp")
    return url[: -len("/api/mcp")]


def _post(url: str, key: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "x-functions-key": key},
    )
    try:
        with request.urlopen(req, timeout=60) as resp:  # noqa: S310 - configured function endpoint
            body = resp.read().decode("utf-8")
            return getattr(resp, "status", 0), (json.loads(body) if body else {})
    except error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode("utf-8", "replace")[:200]}


def main() -> int:
    settings = load_settings(os.path.join(_ROOT, ".env"))
    key = os.environ.get("MCP_MINT_FUNCTION_KEY", "").strip()
    if not settings.mcp_mint_url or not key:
        print("FAIL: MCP_MINT_URL and MCP_MINT_FUNCTION_KEY are required in .env")
        return 1
    base = _base(settings.mcp_mint_url)

    ok = True
    for name, path in ROUTES.items():
        status, doc = _post(base + path, key, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        info = (doc.get("result") or {}).get("serverInfo") or {}
        passed = status == 200 and bool(info)
        ok = ok and passed
        label = info.get("name") or str(doc.get("error", "?"))[:60]
        print(f"[{'OK' if passed else 'FAIL'}] {name:6s} {path:16s} status={status} serverInfo={label}")

    # Functional read-only check of the new route resolver.
    status, doc = _post(base + ROUTES["route"], key, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "resolve_route_facts", "arguments": {"worker_id": "EMP-001"}},
    })
    sc = (doc.get("result") or {}).get("structuredContent") or {}
    passed = sc.get("status") == "resolved" and bool(sc.get("admissible_skill_ids"))
    ok = ok and passed
    print(f"[{'OK' if passed else 'FAIL'}] route  resolve_route_facts EMP-001 -> "
          f"status={sc.get('status')} target_role={sc.get('target_role')} "
          f"admissible={sc.get('admissible_skill_ids')}")

    print("SMOKE_PASS" if ok else "SMOKE_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
