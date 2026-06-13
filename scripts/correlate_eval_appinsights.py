"""Correlate a Foundry eval run with Application Insights telemetry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import warnings
from datetime import UTC, datetime, timedelta
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


def _connection_parts(connection_string: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for part in (connection_string or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        parts[key.strip().lower()] = value.strip()
    return parts


def _parse_azd_env_values(raw: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z0-9_]+", key):
            continue
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def _azd_env_values(environment: str) -> dict[str, str]:
    try:
        proc = subprocess.run(
            ["azd", "env", "get-values", "--environment", environment],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
    except Exception:  # noqa: BLE001
        return {}
    return _parse_azd_env_values(proc.stdout)


def _load_eval_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _dataset_info(config: dict) -> dict[str, Any]:
    dataset_file = str(config.get("dataset_file", ""))
    path = (ROOT / dataset_file).resolve() if dataset_file else None
    info: dict[str, Any] = {
        "dataset_file": dataset_file,
        "dataset_version": UNCONFIRMED,
        "row_count": None,
    }
    if path and path.exists():
        data = path.read_bytes()
        info["dataset_version"] = "sha256:" + hashlib.sha256(data).hexdigest()[:16]
        info["row_count"] = sum(1 for line in data.splitlines() if line.strip())
    return info


def _evaluator_names(config: dict) -> list[str]:
    return [str(value) for value in config.get("evaluators") or []]


def _latest_evaluator_version(project: Any, name: str) -> dict[str, str]:
    if name.startswith("builtin."):
        return {"name": name, "version": "builtin", "id": ""}
    try:
        versions = []
        for item in project.beta.evaluators.list_versions(name, type="custom"):
            if isinstance(item, dict):
                versions.append(item)
            else:
                versions.append({
                    "name": str(getattr(item, "name", name)),
                    "version": str(getattr(item, "version", "")),
                    "id": str(getattr(item, "id", "")),
                })
    except Exception:  # noqa: BLE001
        return {"name": name, "version": UNCONFIRMED, "id": ""}
    if not versions:
        return {"name": name, "version": UNCONFIRMED, "id": ""}

    def sort_key(item: dict) -> tuple[int, str]:
        version = str(item.get("version", ""))
        return (int(version) if version.isdigit() else -1, version)

    latest = sorted(versions, key=sort_key)[-1]
    return {
        "name": name,
        "version": str(latest.get("version", UNCONFIRMED)),
        "id": str(latest.get("id", "")),
    }


def _eval_run(client: Any, eval_id: str, run_id: str) -> tuple[dict, list[dict]]:
    run = _as_dict(client.evals.runs.retrieve(run_id, eval_id=eval_id))
    output_items = [
        _as_dict(item)
        for item in client.evals.runs.output_items.list(run_id, eval_id=eval_id, limit=100)
    ]
    return run, output_items


def _run_created_at(run: dict | None) -> datetime:
    value = (run or {}).get("created_at")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def _eval_failure_counts(output_items: list[dict]) -> dict[str, int]:
    evaluator_failures = 0
    evaluator_errors = 0
    rows = 0
    for item in output_items:
        rows += 1
        for result in item.get("results") or []:
            status = str(result.get("status", "")).lower()
            if status and status != "completed":
                evaluator_errors += 1
            if result.get("passed") is False:
                evaluator_failures += 1
    return {
        "row_count": rows,
        "evaluator_failure_count": evaluator_failures,
        "evaluator_error_count": evaluator_errors,
    }


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _kql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _events_query(start: datetime, end: datetime, agent_name: str) -> str:
    agent = _kql_string(agent_name)
    return f"""
let start=datetime({_iso(start)});
let end=datetime({_iso(end)});
customEvents
| where timestamp between (start .. end)
| extend event_name=name,
         pf_status=tostring(customDimensions['pf.status']),
         pf_is_error=tostring(customDimensions['pf.is_error']),
         pf_route=tostring(customDimensions['pf.route']),
         pf_source=tostring(customDimensions['pf.source']),
         agent_name=tostring(customDimensions['gen_ai.agent.name'])
| where event_name startswith 'pathforward.' or agent_name == {agent} or pf_route startswith 'pathforward'
| summarize telemetry_event_count=count(),
            product_failure_event_count=countif(pf_status == 'failed' or pf_status == 'error' or pf_status == 'rejected' or pf_is_error == 'true' or pf_is_error == '1'),
            gate_event_count=countif(event_name == 'pathforward.mcp.gate'),
            mint_event_count=countif(event_name == 'pathforward.mcp.mint'),
            fabric_event_count=countif(event_name == 'pathforward.mcp.fabric'),
            fabric_live_event_count=countif(pf_source == 'fabric-live')
""".strip()


def _requests_query(start: datetime, end: datetime, agent_name: str) -> str:
    agent = _kql_string(agent_name)
    return f"""
let start=datetime({_iso(start)});
let end=datetime({_iso(end)});
requests
| where timestamp between (start .. end)
| extend request_name=name,
         success_string=tostring(success),
         result_code_string=tostring(resultCode),
         agent_name=tostring(customDimensions['gen_ai.agent.name'])
| where request_name has 'pathforward' or request_name has {agent} or agent_name == {agent}
| extend result_code=toint(result_code_string)
| summarize request_count=count(),
            failed_request_count=countif(success_string == 'False' or success_string == 'false' or success_string == '0' or result_code >= 500)
""".strip()


def _run_appinsights_query(app_id: str, resource_group: str, subscription: str,
                           query: str, start: datetime, end: datetime) -> dict:
    az = shutil.which("az") or shutil.which("az.cmd") or "az"
    cli_query = " ".join(line.strip() for line in query.splitlines() if line.strip())
    cmd = [
        az, "monitor", "app-insights", "query",
        "--app", app_id,
        "--analytics-query", cli_query,
        "--start-time", _iso(start),
        "--end-time", _iso(end),
        "--output", "json",
    ]
    app_is_guid = bool(re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        app_id,
    ))
    if resource_group and not app_is_guid:
        cmd.extend(["--resource-group", resource_group])
    if subscription:
        cmd.extend(["--subscription", subscription])
    proc = subprocess.run(cmd, text=True, capture_output=True, check=True)
    return json.loads(proc.stdout or "{}")


def _query_error(prefix: str, exc: Exception) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        return f"{prefix}:CalledProcessError:{detail}"
    return f"{prefix}:{type(exc).__name__}:{exc}"


def _first_row(table_result: dict) -> dict[str, Any]:
    tables = table_result.get("tables") or []
    if not tables:
        return {}
    table = tables[0]
    columns = [col["name"] for col in table.get("columns") or []]
    rows = table.get("rows") or []
    if not rows:
        return {}
    return {columns[i]: rows[0][i] for i in range(min(len(columns), len(rows[0])))}


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value))
    except Exception:  # noqa: BLE001
        return 0


def _write_report(report: dict, out_path: str | None) -> Path:
    if out_path:
        path = Path(out_path)
    else:
        evidence_dir = ROOT / ".agents" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        run_id = report.get("eval", {}).get("run_id", "unknown")
        path = evidence_dir / f"eval-appinsights-correlation-{run_id}-{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", default="eval.yaml")
    parser.add_argument("--environment", default=os.environ.get("AZURE_ENV_NAME", "pathforward-dev"))
    parser.add_argument("--window-minutes", type=int, default=45)
    parser.add_argument("--start-time", default="")
    parser.add_argument("--end-time", default="")
    parser.add_argument("--app-id", default="")
    parser.add_argument("--resource-group", default="")
    parser.add_argument("--subscription", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = load_settings(str(ROOT / ".env"))
    azd_values = _azd_env_values(args.environment)
    config = _load_eval_config(ROOT / args.config)
    agent_cfg = config.get("agent") or {}
    agent_name = str(agent_cfg.get("name") or azd_values.get("AGENT_PATHFORWARD_ORCHESTRATOR_NAME")
                     or "pathforward-orchestrator")
    agent_version = str(azd_values.get("AGENT_PATHFORWARD_ORCHESTRATOR_VERSION") or UNCONFIRMED)
    conn = settings.azure_monitor_connection_string or azd_values.get("AZURE_MONITOR_CONNECTION_STRING", "")
    conn_parts = _connection_parts(conn)
    app_id = args.app_id or conn_parts.get("applicationid", "")
    resource_group = args.resource_group or azd_values.get("AZURE_RESOURCE_GROUP", "")
    subscription = args.subscription or azd_values.get("AZURE_SUBSCRIPTION_ID", "")

    if not settings.foundry_project_endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT is required")
        return 1
    if not app_id and not args.dry_run:
        print("FAIL: App Insights ApplicationId is required. Set AZURE_MONITOR_CONNECTION_STRING or --app-id.")
        return 1

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(endpoint=settings.foundry_project_endpoint,
                              credential=DefaultAzureCredential())
    client = project.get_openai_client()
    run: dict = {}
    output_items: list[dict] = []
    try:
        run, output_items = _eval_run(client, args.eval_id, args.run_id)
    except Exception as exc:  # noqa: BLE001
        run = {"status": "UNCONFIRMED", "retrieval_error": f"{type(exc).__name__}: {exc}"}

    created_at = _run_created_at(run)
    if args.start_time:
        start = datetime.fromisoformat(args.start_time.replace("Z", "+00:00")).astimezone(UTC)
    else:
        start = created_at - timedelta(minutes=5)
    if args.end_time:
        end = datetime.fromisoformat(args.end_time.replace("Z", "+00:00")).astimezone(UTC)
    else:
        end = created_at + timedelta(minutes=args.window_minutes)

    evaluator_refs = [
        _latest_evaluator_version(project, name)
        for name in _evaluator_names(config)
    ]
    eval_counts = _eval_failure_counts(output_items)
    events_kql = _events_query(start, end, agent_name)
    requests_kql = _requests_query(start, end, agent_name)

    print("App Insights events KQL:")
    print(events_kql)
    print("\nApp Insights requests KQL:")
    print(requests_kql)

    event_summary: dict[str, Any] = {}
    request_summary: dict[str, Any] = {}
    query_errors: list[str] = []
    if not args.dry_run:
        try:
            event_summary = _first_row(_run_appinsights_query(
                app_id, resource_group, subscription, events_kql, start, end))
        except Exception as exc:  # noqa: BLE001
            query_errors.append(_query_error("events_query", exc))
        try:
            request_summary = _first_row(_run_appinsights_query(
                app_id, resource_group, subscription, requests_kql, start, end))
        except Exception as exc:  # noqa: BLE001
            query_errors.append(_query_error("requests_query", exc))

    product_failure_count = (
        _to_int(event_summary.get("product_failure_event_count"))
        + _to_int(request_summary.get("failed_request_count"))
    )
    report = {
        "eval": {
            "eval_id": args.eval_id,
            "run_id": args.run_id,
            "name": run.get("name", UNCONFIRMED),
            "status": run.get("status", UNCONFIRMED),
            "created_at": run.get("created_at", UNCONFIRMED),
        },
        "agent": {
            "name": agent_name,
            "version": agent_version,
            "kind": str(agent_cfg.get("kind", "prompt")),
        },
        "dataset": _dataset_info(config),
        "evaluators": evaluator_refs,
        "app_insights": {
            "app_id": app_id or UNCONFIRMED,
            "resource_group": resource_group or UNCONFIRMED,
            "subscription": subscription or UNCONFIRMED,
            "query_window": {"start": _iso(start), "end": _iso(end)},
            "events_kql": events_kql,
            "requests_kql": requests_kql,
            "event_summary": event_summary,
            "request_summary": request_summary,
            "query_errors": query_errors,
        },
        "counts": {
            **eval_counts,
            "telemetry_event_count": _to_int(event_summary.get("telemetry_event_count")),
            "request_count": _to_int(request_summary.get("request_count")),
            "product_failure_count": product_failure_count,
        },
    }
    out_path = _write_report(report, args.out)
    print(f"correlation_report={out_path}")
    print(json.dumps({
        "eval_id": args.eval_id,
        "run_id": args.run_id,
        "agent": f"{agent_name} v{agent_version}",
        "product_failure_count": product_failure_count,
        "evaluator_failure_count": eval_counts["evaluator_failure_count"],
        "telemetry_event_count": report["counts"]["telemetry_event_count"],
        "request_count": report["counts"]["request_count"],
        "query_errors": query_errors,
    }, indent=2, sort_keys=True))
    return 0 if not query_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
