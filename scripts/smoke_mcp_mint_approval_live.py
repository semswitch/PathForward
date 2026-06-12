"""Live hosted-orchestrator proof for MCP approval-approved credential minting.

This script uses the Foundry Prompt Agent `pathforward-orchestrator`, not local orchestration:

1. The agent calls `pathforward-gate.verify_assessment_and_issue_mint_request`.
2. Foundry returns an `mcp_approval_request` for `pathforward-mint.pathforward_mint_credential`.
3. With `--approve`, the script submits `mcp_approval_response`.
4. The mint MCP tool calls deterministic `mint()` and returns the credential.

The signed `mint_request_token` is never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pathforward.config import load_settings  # noqa: E402


AGENT_NAME = "pathforward-orchestrator"

ITEM_BY_SKILL: dict[str, dict[str, Any]] = {
    "S01": {
        "driving_edge_id": "certgap::EMP-001::S01",
        "stem": "Which evidence-supported action addresses the selected Cloud Engineer skill gap?",
        "options": [
            "Ignore the target role",
            "Use the cited certification path",
            "Change the worker identity",
            "Skip verification",
        ],
        "answer_index": 1,
        "cited_ref_ids": [
            "certgap::EMP-001::S01",
            "requires::R-CLOUD::S01",
            "corpus::AZ-204",
        ],
    },
    "S02": {
        "driving_edge_id": "certgap::EMP-001::S02",
        "stem": "Which evidence-backed next step addresses EMP-001's Azure Functions gap?",
        "options": [
            "Use the cited AZ-204 certification path",
            "Certify an unrelated role",
            "Skip assessment because the worker has another skill",
            "Change the target worker",
        ],
        "answer_index": 0,
        "cited_ref_ids": [
            "certgap::EMP-001::S02",
            "requires::R-CLOUD::S02",
            "corpus::AZ-204",
        ],
    },
}


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _content_text(item: Any) -> str:
    parts: list[str] = []
    for content in _get_attr(item, "content", None) or []:
        text = _get_attr(content, "text", None)
        if text:
            parts.append(str(text))
    return "".join(parts)


def _redact(text: str) -> str:
    text = re.sub(r'("mint_request_token"\s*:\s*")[^"]+("?)', r"\1[REDACTED]\2", text)
    text = re.sub(r"(mint_request_token\s*[=:]\s*)\S+", r"\1[REDACTED]", text, flags=re.I)
    return re.sub(r"(eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+)", "[REDACTED_TOKEN]", text)


def _prompt(skill_id: str, attempt: int) -> str:
    item = ITEM_BY_SKILL[skill_id]
    options = "\n".join(f"    - {option}" for option in item["options"])
    citations = "\n".join(f"    - {ref}" for ref in item["cited_ref_ids"])
    return f"""Use the attached pathforward-gate MCP tool to verify this exact assessment item.
If and only if the gate returns verified and a code-issued mint_request_token is present, call
pathforward-mint.pathforward_mint_credential. I explicitly approve minting only after that
deterministic gate verification; do not print the token value.

worker_id: EMP-001
target_role_id: R-CLOUD
skill_id: {skill_id}
driving_edge_id: {item["driving_edge_id"]}
attempt: {attempt}
item:
  stem: {item["stem"]}
  options:
{options}
  answer_index: {item["answer_index"]}
  cited_ref_ids:
{citations}
  numeric_claim: null

Return JSON with gate_called, gate_status, token_present, mint_called, credential_issued, and
credential_subject if minted. Redact any token."""


def _summarize_response(resp: Any) -> tuple[list[dict[str, Any]], list[Any]]:
    rows: list[dict[str, Any]] = []
    approvals: list[Any] = []
    for idx, item in enumerate(_get_attr(resp, "output", None) or []):
        item_type = _get_attr(item, "type", "")
        row: dict[str, Any] = {"idx": idx, "type": item_type}
        for key in ("id", "name", "server_label", "status"):
            value = _get_attr(item, key, None)
            if value is not None:
                row[key] = str(value)
        if item_type in {"mcp_call", "mcp_tool_call"}:
            output = str(_get_attr(item, "output", "") or "")
            row["output_status_verified"] = '"status":"verified"' in output
            row["output_status_minted"] = '"status":"minted"' in output
            row["credential_present"] = '"credential"' in output
            row["output_has_token"] = "mint_request_token" in output
        if item_type == "mcp_approval_request":
            args = str(_get_attr(item, "arguments", "") or "")
            row["arguments_has_token"] = "mint_request_token" in args
            row["arguments_preview"] = _redact(args)[:500]
            approvals.append(item)
        if item_type == "message":
            row["message_preview"] = _redact(_content_text(item))[:1600]
        rows.append(row)
    return rows, approvals


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run live MCP approval-approved mint proof through pathforward-orchestrator."
    )
    parser.add_argument("--skill-id", choices=sorted(ITEM_BY_SKILL), default="S02")
    parser.add_argument(
        "--attempt",
        type=int,
        default=None,
        help=(
            "Assessment attempt value. Required with --approve because the mint replay guard "
            "rejects reusing the same skill/attempt proof."
        ),
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Submit the mcp_approval_response and mint. Without this, stop at the approval request.",
    )
    args = parser.parse_args()
    if args.approve and args.attempt is None:
        print("FAIL: --approve requires an explicit unused --attempt value")
        return 1
    attempt = 0 if args.attempt is None else args.attempt

    settings = load_settings(str(ROOT / ".env"))
    if not settings.foundry_project_endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT is required")
        return 1
    if not settings.model_deployment:
        print("FAIL: AZURE_AI_MODEL_DEPLOYMENT_NAME is required")
        return 1

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(
        endpoint=settings.foundry_project_endpoint,
        credential=DefaultAzureCredential(),
    )
    client = project.get_openai_client()

    first = client.responses.create(
        input=_prompt(args.skill_id, attempt),
        tool_choice="auto",
        extra_body={"agent_reference": {"name": AGENT_NAME, "type": "agent_reference"}},
    )
    first_rows, approvals = _summarize_response(first)
    print(json.dumps({
        "phase": "approval_request",
        "response_id": _get_attr(first, "id"),
        "status": _get_attr(first, "status"),
        "approval_count": len(approvals),
        "rows": first_rows,
    }, indent=2))

    if not approvals:
        print("FAIL: no mcp_approval_request returned")
        return 1
    if not args.approve:
        print("STOP: approval request received; rerun with --approve to execute mint")
        return 0

    approval_id = str(_get_attr(approvals[0], "id"))
    second = client.responses.create(
        model=settings.model_deployment,
        previous_response_id=_get_attr(first, "id"),
        input=[{
            "type": "mcp_approval_response",
            "approval_request_id": approval_id,
            "approve": True,
        }],
        extra_body={"agent_reference": {"name": AGENT_NAME, "type": "agent_reference"}},
    )
    second_rows, _ = _summarize_response(second)
    minted = any(row.get("output_status_minted") and row.get("credential_present")
                 for row in second_rows)
    print(json.dumps({
        "phase": "approved_mint",
        "response_id": _get_attr(second, "id"),
        "status": _get_attr(second, "status"),
        "minted": minted,
        "rows": second_rows,
    }, indent=2))
    if not minted:
        print("FAIL: approval response completed without minted credential")
        return 1
    print("PASS: hosted orchestrator approval-approved MCP mint proof")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
