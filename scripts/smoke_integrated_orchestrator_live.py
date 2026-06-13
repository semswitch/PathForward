"""Integrated live Prompt Orchestrator proof.

This script invokes the live Foundry Prompt Agent `pathforward-orchestrator`.
It does not call `run_multiagent`, does not instantiate FakeLLMClient, and does not execute local
control flow. The only local logic here is harness logic: send the live prompt, summarize tool calls,
submit the MCP approval response when requested, and save redacted proof under `.agents/evidence`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pathforward.config import load_settings  # noqa: E402


AGENT_NAME = "pathforward-orchestrator"


warnings.filterwarnings("ignore", message="Pydantic serializer warnings:*")


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
    text = re.sub(r"(eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+)", "[REDACTED_TOKEN]", text)
    return text


def _preview(value: Any, limit: int = 1400) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, sort_keys=True)
        except Exception:  # noqa: BLE001
            value = str(value)
    return _redact(value)[:limit]


def _message_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _abstain_state(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    state = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    if not state:
        return None
    if state in {
        "not_abstain",
        "not_abstained",
        "no_abstain",
        "no_abstention",
        "false",
        "none",
        "minted",
        "verified",
    }:
        return False
    if state in {
        "abstain",
        "abstained",
        "abstention",
        "fail_closed_abstain",
        "failed_closed_abstain",
        "no_mint_abstain",
    }:
        return True
    return None


def _message_mentions_abstain(message: str) -> bool:
    upper = message.upper()
    if re.search(r"\b(?:NOT|NO|NON)\s+ABSTAIN(?:ED)?\b|\bNOT[_-]ABSTAIN(?:ED)?\b", upper):
        return False
    return bool(re.search(r"\bABSTAIN(?:ED)?\b", upper))


def _integrated_prompt(attempt: int, approve_mint: bool) -> str:
    approval_line = (
        "I approve minting only after the deterministic gate returns a code-issued "
        "mint_request_token and the Foundry MCP approval step is presented."
        if approve_mint else
        "Do not mint unless the deterministic gate returns a code-issued mint_request_token and "
        "a separate MCP approval response is supplied."
    )
    return f"""Run /pathforward as the live integrated product route for EMP-001 targeting R-CLOUD.

Use the attached Foundry tools. Do not answer from memory and do not collapse this into a plan-only
response.

Required live route:
1. Call pathforward-a2a-curator with worker_id EMP-001, target_role_id R-CLOUD, target_role Cloud
   Engineer, existing skills [S05, S12, S03], and admissible skills [S01, S02, S08].
2. Select one skill only from [S01, S02, S08]. The deterministic driving edge id must be
   certgap::EMP-001::<selected_skill_id>.
3. Use difficulty_band=core and attempt={attempt}.
4. Call pathforward-a2a-generator for the selected skill with the exact JSON item contract:
   stem, options, answer_index, cited_ref_ids, numeric_claim.
5. Call pathforward-a2a-critic before the gate.
6. Call pathforward-gate.verify_assessment_and_issue_mint_request using the generated item.
7. If the gate rejects, retry Generator once using only the bounded failed criteria/remediation from
   the gate, then call the gate again. If it still rejects, ABSTAIN and do not mint.
8. If the gate verifies and returns a mint_request_token, call pathforward-a2a-planner.
9. Call pathforward-a2a-insights with an explicit instruction to use its attached pathforward-fabric
   MCP tool. The Insights output must include source=fabric-live and concrete Fabric cohort metrics:
   cohort size, average readiness, and bottleneck skill counts when available.
10. {approval_line}

Return concise JSON with:
tools_called, selected_skill_id, attempt, difficulty_band, gate_status, reflection_or_retry,
planner_summary, fabric_insight_summary, abstain_state, mint_state, and credential_subject if minted.
Never print or expose the mint_request_token."""


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

        arguments = _get_attr(item, "arguments", None)
        output = _get_attr(item, "output", None)
        if arguments is not None:
            row["arguments_has_token"] = "mint_request_token" in str(arguments)
            row["arguments_preview"] = _preview(arguments)
        if output is not None:
            output_text = str(output)
            row["output_status_verified"] = '"status":"verified"' in output_text or '"status": "verified"' in output_text
            row["output_status_rejected"] = '"status":"rejected"' in output_text or '"status": "rejected"' in output_text
            row["output_status_minted"] = '"status":"minted"' in output_text or '"status": "minted"' in output_text
            row["credential_present"] = '"credential"' in output_text or "credentialSubject" in output_text
            row["output_has_fabric_live"] = "Fabric-live" in output_text or "fabric-live" in output_text
            row["output_preview"] = _preview(output)
        if item_type == "mcp_approval_request":
            approvals.append(item)
        if item_type == "message":
            message_text = _content_text(item)
            message_doc = _message_json(message_text)
            if message_doc and "abstain_state" in message_doc:
                row["abstain_state"] = str(message_doc["abstain_state"])
            row["message_preview"] = _preview(message_text, limit=2200)
        rows.append(row)
    return rows, approvals


def _observations(rows: list[dict[str, Any]]) -> dict[str, bool]:
    names = [str(row.get("name", "")) for row in rows]
    types = [str(row.get("type", "")) for row in rows]
    messages = [str(row.get("message_preview", "")) for row in rows]
    abstain = False
    for row in reversed(rows):
        if "abstain_state" not in row:
            continue
        parsed_abstain = _abstain_state(row["abstain_state"])
        if parsed_abstain is not None:
            abstain = parsed_abstain
            break
    else:
        abstain = any(_message_mentions_abstain(message) for message in messages)
    return {
        "curator_a2a": "pathforward-a2a-curator" in names,
        "generator_a2a": "pathforward-a2a-generator" in names,
        "critic_a2a": "pathforward-a2a-critic" in names,
        "planner_a2a": "pathforward-a2a-planner" in names,
        "insights_a2a": "pathforward-a2a-insights" in names,
        "gate_mcp": any(
            row.get("server_label") == "pathforward-gate"
            or row.get("name") == "verify_assessment_and_issue_mint_request"
            for row in rows
        ),
        "gate_verified": any(row.get("output_status_verified") for row in rows),
        "gate_rejected": any(row.get("output_status_rejected") for row in rows),
        "fabric_live": any(row.get("output_has_fabric_live") for row in rows),
        "approval_request": "mcp_approval_request" in types,
        "mint_mcp": any(
            row.get("server_label") == "pathforward-mint"
            or row.get("name") == "pathforward_mint_credential"
            for row in rows
        ),
        "minted": any(row.get("output_status_minted") and row.get("credential_present") for row in rows),
        "abstain": abstain,
    }


def _write_evidence(doc: dict[str, Any]) -> Path:
    evidence_dir = ROOT / ".agents" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = evidence_dir / f"integrated-live-baseline-{stamp}.json"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return {
            str(k): _jsonable(v)
            for k, v in vars(obj).items()
            if not str(k).startswith("_")
        }
    return str(obj)


def _stream_create(client: Any, *, evidence_prefix: str, **kwargs: Any) -> tuple[Any | None, Path]:
    evidence_dir = ROOT / ".agents" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = evidence_dir / f"{evidence_prefix}-{stamp}.jsonl"
    final_response = None
    with path.open("w", encoding="utf-8") as fh:
        try:
            stream = client.responses.create(stream=True, **kwargs)
            for event in stream:
                doc = _jsonable(event)
                fh.write(json.dumps(doc, sort_keys=True) + "\n")
                event_type = str(doc.get("type", ""))
                if event_type in {"response.completed", "response.failed", "response.incomplete"}:
                    final_response = _get_attr(event, "response", None)
        except Exception as exc:  # noqa: BLE001
            fh.write(json.dumps({
                "type": "harness.exception",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }, sort_keys=True) + "\n")
            raise
    return final_response, path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the integrated live Prompt Orchestrator route.")
    parser.add_argument("--attempt", type=int, default=int(time.time()))
    parser.add_argument("--approve", action="store_true", help="Approve the MCP mint request if returned.")
    args = parser.parse_args()

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

    first, stream_path = _stream_create(
        client,
        evidence_prefix="integrated-live-baseline-stream",
        input=_integrated_prompt(args.attempt, args.approve),
        tool_choice="auto",
        extra_body={"agent_reference": {"name": AGENT_NAME, "type": "agent_reference"}},
    )
    if first is None:
        print(f"FAIL: no final response returned; stream_path={stream_path}")
        return 1
    first_rows, approvals = _summarize_response(first)
    all_rows = list(first_rows)
    first_obs = _observations(first_rows)
    print(json.dumps({
        "phase": "integrated_request",
        "response_id": _get_attr(first, "id"),
        "status": _get_attr(first, "status"),
        "approval_count": len(approvals),
        "observations": first_obs,
        "rows": first_rows,
    }, indent=2))

    second_rows: list[dict[str, Any]] = []
    if approvals and args.approve:
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
        all_rows.extend(second_rows)
        print(json.dumps({
            "phase": "approval_response",
            "response_id": _get_attr(second, "id"),
            "status": _get_attr(second, "status"),
            "observations": _observations(second_rows),
            "rows": second_rows,
        }, indent=2))
    elif approvals:
        print("STOP: approval request received; rerun with --approve to mint.")

    obs = _observations(all_rows)
    proof = {
        "agent": AGENT_NAME,
        "attempt": args.attempt,
        "approved": bool(args.approve),
        "first_response_id": _get_attr(first, "id"),
        "first_response_status": _get_attr(first, "status"),
        "stream_path": str(stream_path),
        "observations": obs,
        "rows": all_rows,
    }
    evidence_path = _write_evidence(proof)
    print(f"evidence_path={evidence_path}")

    if _get_attr(first, "status", "") == "failed":
        print("BASELINE_FAIL: first integrated response failed")
        return 1

    required = (
        "curator_a2a",
        "generator_a2a",
        "critic_a2a",
        "gate_mcp",
        "gate_verified",
        "planner_a2a",
        "insights_a2a",
        "fabric_live",
    )
    missing = [name for name in required if not obs.get(name)]
    if args.approve and not obs.get("minted"):
        missing.append("minted")
    if missing:
        print(f"BASELINE_FAIL: missing {missing}")
        return 1
    print("BASELINE_PASS: integrated live Prompt Orchestrator route completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
