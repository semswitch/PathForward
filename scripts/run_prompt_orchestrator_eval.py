"""Run a current Foundry Prompt Orchestrator eval with explicit evaluator parameters."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pathforward.config import load_settings  # noqa: E402


UNCONFIRMED = "UNCONFIRMED"
warnings.filterwarnings("ignore", message="Pydantic serializer warnings:*")


def _as_dict(value: Any) -> dict:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    return json.loads(json.dumps(value, default=str))


def _parse_azd_env_values(raw: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z0-9_]+", key):
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values


def _azd_env_values(environment: str) -> dict[str, str]:
    proc = subprocess.run(
        ["azd", "env", "get-values", "--environment", environment],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return _parse_azd_env_values(proc.stdout)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _field_schema(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, list):
        return {"type": "array"}
    if isinstance(value, dict):
        return {"type": "object"}
    return {"type": "string"}


def _item_schema(rows: list[dict[str, Any]]) -> dict[str, Any]:
    properties: dict[str, dict[str, Any]] = {}
    for row in rows:
        for key, value in row.items():
            properties.setdefault(key, _field_schema(value))
    return {
        "type": "object",
        "properties": properties,
        "required": ["query"],
    }


def _custom_code_mapping() -> dict[str, str]:
    return {
        "output_text": "{{sample.output_text}}",
        "output_items": "{{sample.output}}",
        "expected_outcome": "{{item.expected_outcome}}",
        "risk_category": "{{item.risk_category}}",
        "feature_area": "{{item.feature_area}}",
        "must_emit": "{{item.must_emit}}",
        "must_not_expose": "{{item.must_not_expose}}",
    }


def _prompt_mapping() -> dict[str, str]:
    return {
        "query": "{{item.query}}",
        "response": "{{sample.output_text}}",
        "expected_behavior": "{{item.expected_behavior}}",
        "expected_outcome": "{{item.expected_outcome}}",
        "risk_category": "{{item.risk_category}}",
        "feature_area": "{{item.feature_area}}",
    }


def _builtin_mapping() -> dict[str, str]:
    return {
        "query": "{{item.query}}",
        "response": "{{sample.output_text}}",
        "expected_behavior": "{{item.expected_behavior}}",
        "tool_calls": "{{sample.tool_calls}}",
        "tool_definitions": "{{sample.tool_definitions}}",
    }


def _latest_agent_version(project: Any, agent_name: str) -> str:
    versions = []
    for agent in project.agents.list_versions(agent_name=agent_name):
        version = str(getattr(agent, "version", "") or "")
        if version:
            versions.append(version)
    if not versions:
        raise RuntimeError(f"no Foundry agent versions found for {agent_name!r}")

    def key(value: str) -> tuple[int, str]:
        return (int(value), value) if value.isdigit() else (-1, value)

    return max(versions, key=key)


def _latest_evaluator_version(project: Any, name: str) -> str:
    versions = []
    for evaluator in project.beta.evaluators.list_versions(name):
        version = str(getattr(evaluator, "version", "") or "")
        if version:
            versions.append(version)
    if not versions:
        raise RuntimeError(f"no Foundry evaluator versions found for {name!r}")

    def key(value: str) -> tuple[int, str]:
        return (int(value), value) if value.isdigit() else (-1, value)

    return max(versions, key=key)


def _testing_criteria(
    config: dict[str, Any],
    settings_model: str,
    evaluator_versions: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    code_manifest = _load_manifest(ROOT / "eval" / "evaluators" / "manifest.json")
    prompt_manifest = _load_manifest(ROOT / "eval" / "evaluators" / "prompt_manifest.json")
    code_names = {entry["name"] for entry in code_manifest["evaluators"]}
    prompt_names = {entry["name"] for entry in prompt_manifest["evaluators"]}
    deployment_name = code_manifest.get("deployment_name") or prompt_manifest.get("deployment_name") or settings_model
    pass_threshold = float(code_manifest.get("pass_threshold", 1.0))
    prompt_threshold = int(prompt_manifest.get("threshold", 4))
    configured_params = config.get("evaluator_parameters") or {}

    criteria = []
    for evaluator in config.get("evaluators") or []:
        name = str(evaluator)
        criterion: dict[str, Any] = {
            "type": "azure_ai_evaluator",
            "name": name.split(".")[-1],
            "evaluator_name": name,
        }
        if name in code_names:
            criterion["name"] = name
            if evaluator_versions and evaluator_versions.get(name):
                criterion["evaluator_version"] = evaluator_versions[name]
            criterion["data_mapping"] = _custom_code_mapping()
            criterion["initialization_parameters"] = {
                "deployment_name": deployment_name,
                "pass_threshold": pass_threshold,
                **configured_params.get(name, {}),
            }
        elif name in prompt_names:
            criterion["name"] = name
            if evaluator_versions and evaluator_versions.get(name):
                criterion["evaluator_version"] = evaluator_versions[name]
            criterion["data_mapping"] = _prompt_mapping()
            criterion["initialization_parameters"] = {
                "deployment_name": deployment_name,
                "threshold": prompt_threshold,
                **configured_params.get(name, {}),
            }
        else:
            criterion["data_mapping"] = _builtin_mapping()
            criterion["initialization_parameters"] = {"deployment_name": deployment_name}
        criteria.append(criterion)
    return criteria


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        if str(value.get("role", "")).lower() == "system" and "content" in value:
            value = {**value, "content": "[REDACTED_SYSTEM_PROMPT]"}
        redacted = {}
        for key, item in value.items():
            if str(key).lower() in {"mint_request_token", "client_secret", "azure_client_secret"}:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r'("mint_request_token"\s*:\s*")[^"]+("?)', r"\1[REDACTED]\2", value)
        value = re.sub(r"(mint_request_token\s*[=:]\s*)\S+", r"\1[REDACTED]", value, flags=re.I)
        return re.sub(r"(eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+)", "[REDACTED_TOKEN]", value)
    return value


def _write_evidence(report: dict[str, Any], out_path: str = "") -> Path:
    if out_path:
        path = Path(out_path)
    else:
        evidence_dir = ROOT / ".agents" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        path = evidence_dir / f"foundry-prompt-orchestrator-eval-{report['run_id']}-{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_redact(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _result_counts(output_items: list[dict[str, Any]]) -> dict[str, int]:
    failures = 0
    errors = 0
    result_count = 0
    for item in output_items:
        for result in item.get("results") or []:
            result_count += 1
            if result.get("passed") is False:
                failures += 1
            status = str(result.get("status", "")).lower()
            if status and status != "completed":
                errors += 1
    return {"result_count": result_count, "failure_count": failures, "error_count": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="eval/prompt_orchestrator_smoke.yaml")
    parser.add_argument("--environment", default=os.environ.get("AZURE_ENV_NAME", "pathforward-dev"))
    parser.add_argument("--out", default="")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()

    settings = load_settings(str(ROOT / ".env"))
    if not settings.foundry_project_endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT is required")
        return 1

    config_path = ROOT / args.config
    config = _load_config(config_path)
    rows = _load_jsonl(ROOT / str(config["dataset_file"]))
    azd_values = _azd_env_values(args.environment)
    agent_cfg = config.get("agent") or {}
    agent_name = str(agent_cfg.get("name") or azd_values.get("AGENT_PATHFORWARD_ORCHESTRATOR_NAME"))
    configured_agent_version = str(agent_cfg.get("version") or "")
    if not agent_name:
        print("FAIL: agent name could not be resolved")
        return 1

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(endpoint=settings.foundry_project_endpoint,
                              credential=DefaultAzureCredential())
    client = project.get_openai_client()
    agent_version = configured_agent_version or _latest_agent_version(project, agent_name)
    custom_names = [
        str(name)
        for name in config.get("evaluators") or []
        if not str(name).startswith("builtin.")
    ]
    evaluator_versions = {
        name: _latest_evaluator_version(project, name)
        for name in custom_names
    }
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    eval_obj = client.evals.create(
        name=f"{config['name']}-{stamp}",
        data_source_config={
            "type": "custom",
            "item_schema": _item_schema(rows),
            "include_sample_schema": True,
        },
        testing_criteria=_testing_criteria(
            config,
            settings.model_deployment or "reasoning",
            evaluator_versions,
        ),
    )
    eval_id = _as_dict(eval_obj)["id"]
    run = client.evals.runs.create(
        eval_id,
        name=f"{config['name']}-run-{stamp}",
        data_source={
            "type": "azure_ai_target_completions",
            "source": {
                "type": "file_content",
                "content": [{"item": row} for row in rows[: int(config.get("max_samples") or len(rows))]],
            },
            "input_messages": {
                "type": "template",
                "template": [{"type": "message", "role": "user", "content": "{{item.query}}"}],
            },
            "target": {
                "type": "azure_ai_agent",
                "name": agent_name,
                "version": agent_version,
            },
        },
    )
    run_id = _as_dict(run)["id"]

    deadline = time.time() + args.timeout_seconds
    current = _as_dict(run)
    while time.time() < deadline:
        current = _as_dict(client.evals.runs.retrieve(run_id, eval_id=eval_id))
        if str(current.get("status", "")).lower() in {"completed", "failed", "cancelled"}:
            break
        time.sleep(10)

    output_items = [
        _as_dict(item)
        for item in client.evals.runs.output_items.list(run_id, eval_id=eval_id, limit=100)
    ]
    report = {
        "eval_id": eval_id,
        "run_id": run_id,
        "eval_name": _as_dict(eval_obj).get("name"),
        "run_name": current.get("name"),
        "status": current.get("status"),
        "created_at": current.get("created_at"),
        "config": str(config_path.relative_to(ROOT)),
        "dataset_file": str(config["dataset_file"]),
        "dataset_rows": len(rows),
        "sample_rows": min(len(rows), int(config.get("max_samples") or len(rows))),
        "agent": {"name": agent_name, "version": agent_version, "kind": str(agent_cfg.get("kind", "prompt"))},
        "evaluators": config.get("evaluators") or [],
        "evaluator_versions": evaluator_versions,
        "counts": _result_counts(output_items),
        "output_items": output_items,
    }
    evidence_path = _write_evidence(report, args.out)
    print(json.dumps({
        "eval_id": eval_id,
        "run_id": run_id,
        "status": current.get("status"),
        "agent": f"{agent_name} v{agent_version}",
        "config": str(config_path.relative_to(ROOT)),
        "counts": report["counts"],
        "evidence_path": str(evidence_path),
    }, indent=2, sort_keys=True))
    return 0 if str(current.get("status", "")).lower() == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
