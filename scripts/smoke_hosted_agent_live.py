"""Live proof for the Foundry Hosted Agent `pathforward-orchestrator`.

This targets the actual hosted-agent endpoint, not the project-level prompt-agent
`agent_reference` path:

    /agents/pathforward-orchestrator/endpoint/protocols/openai/responses

It proves the currently deployed hosted route can:
  - call versioned Foundry specialist agents whose Skills were provisioned from Toolbox resources,
  - run the live multi-agent route with Search + Fabric-live Insights,
  - prepare a signed MCP mint request without minting in-process.

The output evidence intentionally avoids secrets and raw auth material.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from azure.identity import DefaultAzureCredential

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from pathforward.config import load_settings  # noqa: E402


AGENT_NAME = "pathforward-orchestrator"
API_VERSION = "2025-11-15-preview"
EXPECTED_AGENT_VERSION = os.getenv("PATHFORWARD_EXPECTED_HOSTED_VERSION", "").strip()


def _is_expected_hosted_agent(agent_ref: dict[str, Any]) -> bool:
    if agent_ref.get("name") != AGENT_NAME:
        return False
    if not EXPECTED_AGENT_VERSION:
        return bool(agent_ref.get("version"))
    return str(agent_ref.get("version")) == EXPECTED_AGENT_VERSION


@dataclass(frozen=True)
class HostedCall:
    name: str
    input_text: str
    expect_credential: bool
    expect_mcp_mint_request: bool
    required_checks: tuple[str, ...]


def _hosted_url(endpoint: str) -> str:
    return (
        endpoint.rstrip("/")
        + f"/agents/{AGENT_NAME}/endpoint/protocols/openai/responses"
        + f"?api-version={API_VERSION}"
    )


def _extract_json_block(text: str) -> dict[str, Any]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _stream_hosted_response(url: str, token: str, input_text: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"input": input_text, "stream": True}
    text_parts: list[str] = []
    completed: dict[str, Any] = {}
    with httpx.stream("POST", url, headers=headers, json=payload, timeout=420) as resp:
        resp.raise_for_status()
        for raw_line in resp.iter_lines():
            line = raw_line.strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            typ = event.get("type", "")
            if typ == "response.output_text.delta":
                text_parts.append(event.get("delta", ""))
            elif typ == "response.completed":
                completed = event.get("response") or {}
            elif typ == "response.failed":
                completed = event.get("response") or {}
                break
    output_text = "".join(text_parts)
    if not output_text and completed:
        try:
            output_text = completed["output"][0]["content"][0]["text"]
        except Exception:  # noqa: BLE001
            output_text = ""
    doc = _extract_json_block(output_text)
    return {
        "response_id": completed.get("id") or completed.get("response_id", ""),
        "status": completed.get("status", ""),
        "agent_reference": completed.get("agent_reference") or {},
        "agent_session_id": completed.get("agent_session_id", ""),
        "output_text": output_text,
        "doc": doc,
    }


def _summarize_call(call: HostedCall, result: dict[str, Any]) -> dict[str, Any]:
    doc = result["doc"]
    loop = ((doc.get("result") or {}).get("loop") or {})
    insights = ((doc.get("result") or {}).get("insights") or {})
    skill_evidence = doc.get("skill_evidence") or {}
    credential = doc.get("credential")
    mcp_mint_request = doc.get("mcp_mint_request")
    agent_ref = result.get("agent_reference") or {}
    checks = {
        "response_completed": result.get("status") == "completed",
        "hosted_agent_expected": _is_expected_hosted_agent(agent_ref),
        "surface_live": doc.get("surface") == "foundry-hosted-agent" and doc.get("mode") == "live",
        "versioned_agents": skill_evidence.get("source") == "foundry-versioned-agents",
        "loop_verified": loop.get("status") == "verified",
        "loop_abstained": loop.get("status") == "abstained",
        "fabric_live": insights.get("source") == "fabric-live",
        "mcp_mint_request_present": bool(mcp_mint_request),
        "mcp_mint_request_absent": not bool(mcp_mint_request),
        "credential_presence_expected": bool(credential) == call.expect_credential,
        "mcp_mint_presence_expected": bool(mcp_mint_request) == call.expect_mcp_mint_request,
    }
    return {
        "name": call.name,
        "response_id": result.get("response_id", ""),
        "agent_reference": agent_ref,
        "agent_session_id": result.get("agent_session_id", ""),
        "worker_id": doc.get("worker_id", ""),
        "target_role_id": doc.get("target_role_id", ""),
        "selected_skill_id": ((doc.get("result") or {}).get("orchestrator") or {}).get(
            "selected_target_skill_id", ""
        ),
        "loop_status": loop.get("status", ""),
        "attempts": loop.get("attempts", 0),
        "retrieved_ref_ids": ((loop.get("item") or {}).get("retrieved_ref_ids") or []),
        "citations": loop.get("citations") or [],
        "insights_source": insights.get("source", ""),
        "mcp_mint_request_id": ((mcp_mint_request or {}).get("request") or {}).get("request_id", ""),
        "credential_issued": bool(credential),
        "credential_cited_edge_id": (((credential or {}).get("credentialSubject") or {}).get(
            "cited_edge_id", ""
        )),
        "checks": checks,
        "passed": all(checks[name] for name in call.required_checks),
    }


def _write_evidence(out_base: Path, summaries: list[dict[str, Any]], raw: dict[str, Any]) -> None:
    out_base.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    data = {
        "as_of": stamp,
        "agent": AGENT_NAME,
        "api_version": API_VERSION,
        "summaries": summaries,
        "raw": raw,
    }
    out_base.with_suffix(".json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    lines = [
        "# Hosted Agent Live Proof",
        "",
        f"Generated: `{stamp}`",
        "",
        "Target: Foundry Hosted Agent `pathforward-orchestrator` via the dedicated hosted-agent "
        "`responses` endpoint.",
        "",
        "This evidence intentionally records response IDs, agent version, pass/fail checks, retrieval "
        "IDs, citations, MCP mint request IDs, and credential-spine facts only. It does not include secrets.",
        "",
        "## Results",
        "",
    ]
    for item in summaries:
        lines.extend([
            f"### {item['name']}",
            "",
            f"- Response: `{item['response_id']}`",
            f"- Agent reference: `{item['agent_reference']}`",
            f"- Worker: `{item['worker_id']}` -> `{item['target_role_id']}`",
            f"- Selected skill: `{item['selected_skill_id']}`",
            f"- Loop: `{item['loop_status']}` after `{item['attempts']}` attempt(s)",
            f"- Insights source: `{item['insights_source']}`",
            f"- MCP mint request: `{item['mcp_mint_request_id'] or '(none)'}`",
            f"- Credential issued: `{item['credential_issued']}`",
            f"- Credential cited edge: `{item['credential_cited_edge_id'] or '(none)'}`",
            f"- Passed: `{item['passed']}`",
            "",
            "Checks:",
        ])
        for name, ok in item["checks"].items():
            lines.append(f"- `{name}`: `{ok}`")
        lines.append("")
    out_base.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Live smoke for the Foundry Hosted Agent route.")
    ap.add_argument("--output-base", default=".agents/evidence/hosted-agent-live-proof",
                    help="Evidence path without extension.")
    args = ap.parse_args()

    settings = load_settings(str(_ROOT / ".env"))
    if not settings.foundry_project_endpoint:
        print("SKIP: AZURE_AI_PROJECT_ENDPOINT/FOUNDRY_PROJECT_ENDPOINT is not configured")
        return 0

    token = DefaultAzureCredential().get_token("https://ai.azure.com/.default").token
    url = _hosted_url(settings.foundry_project_endpoint)
    calls = [
        HostedCall(
            name="diagnose_toolbox",
            input_text="diagnose toolbox",
            expect_credential=False,
            expect_mcp_mint_request=False,
            required_checks=("response_completed", "hosted_agent_expected"),
        ),
        HostedCall(
            name="no_approval_default",
            input_text="Run /pathforward for EMP-001",
            expect_credential=False,
            expect_mcp_mint_request=True,
            required_checks=(
                "response_completed",
                "hosted_agent_expected",
                "surface_live",
                "versioned_agents",
                "loop_verified",
                "fabric_live",
                "mcp_mint_request_present",
                "credential_presence_expected",
            ),
        ),
        HostedCall(
            name="semantic_abstain",
            input_text=json.dumps({
                "message": "Run /pathforward semantic ABSTAIN proof",
                "abstain_probe": True,
            }),
            expect_credential=False,
            expect_mcp_mint_request=False,
            required_checks=(
                "response_completed",
                "hosted_agent_expected",
                "surface_live",
                "versioned_agents",
                "loop_abstained",
                "mcp_mint_request_absent",
                "credential_presence_expected",
                "mcp_mint_presence_expected",
            ),
        ),
    ]

    raw: dict[str, Any] = {}
    summaries: list[dict[str, Any]] = []
    for call in calls:
        print(f"\n[{call.name}] invoking hosted agent...")
        result = _stream_hosted_response(url, token, call.input_text)
        raw[call.name] = {
            "response_id": result["response_id"],
            "status": result["status"],
            "agent_reference": result["agent_reference"],
            "agent_session_id": result["agent_session_id"],
            "doc": result["doc"],
        }
        summary = _summarize_call(call, result)
        summaries.append(summary)
        print(f"  response={summary['response_id']} loop={summary['loop_status']} "
              f"credential={summary['credential_issued']} passed={summary['passed']}")

    out_base = (_ROOT / args.output_base).resolve()
    _write_evidence(out_base, summaries, raw)
    print(f"\nwrote {out_base.with_suffix('.md')} and {out_base.with_suffix('.json')}")
    return 0 if all(s["passed"] for s in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
