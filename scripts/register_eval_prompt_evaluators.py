"""Register PathForward custom prompt evaluators in the Foundry evaluator catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pathforward.config import load_settings  # noqa: E402


def _version_payload(entry: dict, prompt_text: str, threshold: int) -> dict:
    return {
        "name": entry["name"],
        "display_name": entry["display_name"],
        "description": entry["description"],
        "evaluator_type": "custom",
        "categories": ["quality"],
        "definition": {
            "type": "prompt",
            "prompt_text": prompt_text,
            "init_parameters": {
                "type": "object",
                "properties": {
                    "deployment_name": {"type": "string"},
                    "threshold": {"type": "number"},
                },
                "required": ["deployment_name", "threshold"],
            },
            "data_schema": {
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
            "metrics": {
                "result": {
                    "type": "ordinal",
                    "desirable_direction": "increase",
                    "min_value": 1,
                    "max_value": 5,
                    "threshold": threshold,
                    "is_primary": True,
                }
            },
        },
        "tags": {
            "pathforward": "true",
            "contract": "agentic-architecture",
            "authority": "subjective-signal-only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="eval/evaluators/prompt_manifest.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest_path = ROOT / args.manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    settings = load_settings(str(ROOT / ".env"))
    endpoint = settings.foundry_project_endpoint
    if not endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT is required")
        return 1

    deployment_name = manifest.get("deployment_name") or settings.model_deployment or "reasoning"
    threshold = int(manifest.get("threshold", 4))
    payloads = []
    for entry in manifest["evaluators"]:
        source = ROOT / entry["local_uri"]
        payloads.append((entry, _version_payload(
            entry,
            source.read_text(encoding="utf-8"),
            threshold,
        )))

    if args.dry_run:
        print(json.dumps({
            "endpoint": endpoint,
            "deployment_name": deployment_name,
            "threshold": threshold,
            "evaluator_count": len(payloads),
            "evaluators": [entry["name"] for entry, _ in payloads],
        }, indent=2))
        return 0

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
    created = []
    for entry, payload in payloads:
        evaluator = project.beta.evaluators.create_version(
            name=entry["name"],
            evaluator_version=payload,
        )
        created.append({
            "name": evaluator.name,
            "version": evaluator.version,
            "id": getattr(evaluator, "id", None),
        })
        print(f"EVALUATOR {evaluator.name} v{evaluator.version}")

    print(json.dumps({"created": created}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
