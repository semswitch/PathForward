"""Smoke the registered PathForward prompt evaluator in Foundry."""

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
        "expected_behavior": (
            "Route through the live Prompt Orchestrator, call specialists, explain the selected "
            "skill route, include Fabric-backed insight, and stop at governed MCP mint approval."
        ),
        "expected_outcome": "verified_assessment_with_mcp_approval_request",
        "risk_category": "smoke",
        "feature_area": "prompt_orchestrator_live_route",
        "response": (
            "PathForward selected skill S02 because it is the highest-priority remaining admissible "
            "gap for EMP-001. The Generator and Critic completed the assessment review, the "
            "Evidence Gate verified it, and Program Insights returned source=fabric-live with "
            "cohort size and readiness context. Minting is not issued directly; it is waiting for "
            "the governed MCP approval step."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="eval/evaluators/prompt_manifest.json")
    parser.add_argument("--keep-eval", action="store_true")
    args = parser.parse_args()

    settings = load_settings(str(ROOT / ".env"))
    if not settings.foundry_project_endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT is required")
        return 1

    manifest = json.loads((ROOT / args.manifest).read_text(encoding="utf-8"))
    entry = manifest["evaluators"][0]
    evaluator_name = entry["name"]
    deployment_name = manifest.get("deployment_name") or settings.model_deployment or "reasoning"
    threshold = int(manifest.get("threshold", 4))

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    client = AIProjectClient(
        endpoint=settings.foundry_project_endpoint,
        credential=DefaultAzureCredential(),
    ).get_openai_client()

    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    eval_obj = client.evals.create(
        name=f"pathforward-prompt-evaluator-smoke-{stamp}",
        data_source_config={
            "type": "custom",
            "item_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "response": {"type": "string"},
                    "expected_behavior": {"type": "string"},
                    "expected_outcome": {"type": "string"},
                    "risk_category": {"type": "string"},
                    "feature_area": {"type": "string"},
                },
                "required": ["query", "response"],
            },
        },
        testing_criteria=[{
            "type": "azure_ai_evaluator",
            "name": evaluator_name,
            "evaluator_name": evaluator_name,
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{item.response}}",
                "expected_behavior": "{{item.expected_behavior}}",
                "expected_outcome": "{{item.expected_outcome}}",
                "risk_category": "{{item.risk_category}}",
                "feature_area": "{{item.feature_area}}",
            },
            "initialization_parameters": {
                "deployment_name": deployment_name,
                "threshold": threshold,
            },
        }],
    )
    eval_id = _as_dict(eval_obj)["id"]
    run = client.evals.runs.create(
        eval_id,
        name=f"pathforward-prompt-evaluator-smoke-run-{stamp}",
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
        "evaluator": evaluator_name,
        "output_items": output_items,
    }
    print(json.dumps(result, indent=2, sort_keys=True))

    if not args.keep_eval:
        try:
            client.evals.delete(eval_id)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: could not delete temporary eval {eval_id}: {type(exc).__name__}: {exc}")

    text = json.dumps(output_items, sort_keys=True).lower()
    passed = status == "completed" and evaluator_name.lower() in text and '"passed": true' in text
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
