"""Smoke the registered PathForward code evaluators in Foundry."""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pathforward.config import load_settings  # noqa: E402


warnings.filterwarnings("ignore", message="Pydantic serializer warnings:*")


def _as_dict(value: Any) -> dict:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    return json.loads(json.dumps(value, default=str))


def _sample_item() -> dict:
    return {
        "query": "Run /pathforward for EMP-001",
        "expected_outcome": "verified_assessment_with_mcp_approval_request",
        "risk_category": "smoke",
        "feature_area": "prompt_orchestrator_live_route",
        "must_emit": [
            "pathforward-a2a-curator",
            "pathforward-a2a-generator",
            "pathforward-a2a-critic",
            "pathforward-gate",
            "pathforward-a2a-planner",
            "pathforward-a2a-insights",
            "source=fabric-live",
            "mcp_approval_request",
        ],
        "output_text": (
            "source=fabric-live; cohort size 11; average readiness 0.72; "
            "bottleneck skill counts available; approval required; credential not issued directly."
        ),
        "output_items": [
            {"name": "pathforward-a2a-curator", "type": "tool_call"},
            {"name": "pathforward-a2a-generator", "type": "tool_call"},
            {"name": "pathforward-a2a-critic", "type": "tool_call"},
            {"server_label": "pathforward-gate", "name": "verify_assessment_and_issue_mint_request"},
            {"name": "pathforward-a2a-planner", "type": "tool_call"},
            {
                "name": "pathforward-a2a-insights",
                "output": {"source": "fabric-live", "cohort size": 11},
            },
            {
                "type": "mcp_approval_request",
                "server_label": "pathforward-mint",
                "require_approval": "always",
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="eval/evaluators/manifest.json")
    parser.add_argument("--keep-eval", action="store_true")
    args = parser.parse_args()

    settings = load_settings(str(ROOT / ".env"))
    if not settings.foundry_project_endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT is required")
        return 1

    manifest = json.loads((ROOT / args.manifest).read_text(encoding="utf-8"))
    evaluator_names = [entry["name"] for entry in manifest["evaluators"]]
    deployment_name = manifest.get("deployment_name") or settings.model_deployment or "reasoning"
    threshold = float(manifest.get("pass_threshold", 1.0))

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    client = AIProjectClient(
        endpoint=settings.foundry_project_endpoint,
        credential=DefaultAzureCredential(),
    ).get_openai_client()

    criteria = [
        {
            "type": "azure_ai_evaluator",
            "name": name,
            "evaluator_name": name,
            "data_mapping": {
                "output_text": "{{item.output_text}}",
                "output_items": "{{item.output_items}}",
                "expected_outcome": "{{item.expected_outcome}}",
                "risk_category": "{{item.risk_category}}",
                "feature_area": "{{item.feature_area}}",
                "must_emit": "{{item.must_emit}}",
            },
            "initialization_parameters": {
                "deployment_name": deployment_name,
                "pass_threshold": threshold,
            },
        }
        for name in evaluator_names
    ]
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    eval_obj = client.evals.create(
        name=f"pathforward-code-evaluator-smoke-{stamp}",
        data_source_config={
            "type": "custom",
            "item_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "expected_outcome": {"type": "string"},
                    "risk_category": {"type": "string"},
                    "feature_area": {"type": "string"},
                    "must_emit": {"type": "array", "items": {"type": "string"}},
                    "output_text": {"type": "string"},
                    "output_items": {"type": "array"},
                },
                "required": ["query", "output_text", "output_items"],
            },
        },
        testing_criteria=criteria,
    )
    eval_id = _as_dict(eval_obj)["id"]
    run = client.evals.runs.create(
        eval_id,
        name=f"pathforward-code-evaluator-smoke-run-{stamp}",
        data_source={
            "type": "jsonl",
            "source": {
                "type": "file_content",
                "content": [{"item": _sample_item()}],
            },
        },
    )
    run_id = _as_dict(run)["id"]

    status = ""
    for _ in range(60):
        current = _as_dict(client.evals.runs.retrieve(run_id, eval_id=eval_id))
        status = str(current.get("status", ""))
        if status in {"completed", "failed", "cancelled"}:
            break
        time.sleep(5)

    output_items = [
        _as_dict(item)
        for item in client.evals.runs.output_items.list(run_id, eval_id=eval_id, limit=10)
    ]
    result = {
        "eval_id": eval_id,
        "run_id": run_id,
        "status": status,
        "evaluator_count": len(evaluator_names),
        "output_items": output_items,
    }
    print(json.dumps(result, indent=2, sort_keys=True))

    if not args.keep_eval:
        try:
            client.evals.delete(eval_id)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: could not delete temporary eval {eval_id}: {type(exc).__name__}: {exc}")

    passed = status == "completed" and output_items
    if passed:
        text = json.dumps(output_items, sort_keys=True).lower()
        passed = all(name.lower() in text for name in evaluator_names)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
