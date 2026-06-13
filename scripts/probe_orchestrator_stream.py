"""Stream a single live Prompt Orchestrator turn and narrate each route step.

Observability probe for debugging the eval transient. It sends one prompt to the live Foundry Prompt
Agent via the Responses API (streaming) and prints each output item AS IT HAPPENS, with elapsed time,
so you can see exactly how far the route gets and where it aborts. SINGLE-SHOT by default (no retry) so
it reflects the same one-attempt behavior the Foundry eval target uses.

Examples:
  python scripts/probe_orchestrator_stream.py                       # uses the smoke suite row 0 query
  python scripts/probe_orchestrator_stream.py --prompt "..."        # arbitrary prompt
  python scripts/probe_orchestrator_stream.py --attempts 3          # gauge raw success/failure rate
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pathforward.config import load_settings  # noqa: E402

AGENT_NAME = "pathforward-orchestrator"


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def _row_query(suite: str, row_index: int) -> str:
    rows = []
    for line in (ROOT / suite).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return str(rows[row_index]["query"])


def _label(item: Any) -> str:
    return str(_get(item, "server_label", "") or _get(item, "name", "") or "")


def _stream_once(client: Any, query: str, attempt: int) -> dict[str, Any]:
    t0 = time.time()
    steps: list[dict[str, Any]] = []
    final = None
    error = None
    print(f"\n=== attempt {attempt} — streaming ===")
    try:
        stream = client.responses.create(
            stream=True,
            input=query,
            tool_choice="auto",
            extra_body={"agent_reference": {"name": AGENT_NAME, "type": "agent_reference"}},
        )
        for event in stream:
            etype = str(_get(event, "type", ""))
            if etype.endswith("response.output_item.done"):
                item = _get(event, "item", None)
                if item is None:
                    continue
                itype = str(_get(item, "type", ""))
                if itype == "reasoning":
                    continue  # skip noisy reasoning items
                status = str(_get(item, "status", ""))
                elapsed = time.time() - t0
                label = _label(item)
                steps.append({"t": round(elapsed, 1), "type": itype, "label": label, "status": status})
                print(f"  +{elapsed:6.1f}s  {itype:24} {label:28} [{status}]")
            elif etype in ("response.completed", "response.failed", "response.incomplete"):
                final = _get(event, "response", None)
                print(f"  +{time.time() - t0:6.1f}s  EVENT: {etype}")
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        print(f"  +{time.time() - t0:6.1f}s  EXCEPTION: {error[:400]}")

    status = str(_get(final, "status", "")) if final is not None else ("error" if error else "no_final")
    resp_id = str(_get(final, "id", "")) if final is not None else ""
    print(f"  -> elapsed={time.time() - t0:.1f}s status={status} response_id={resp_id} steps={len(steps)}")
    return {"attempt": attempt, "status": status, "response_id": resp_id, "error": error, "steps": steps}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--suite", default="eval/suites/prompt_orchestrator_smoke.jsonl")
    parser.add_argument("--row-index", type=int, default=0)
    parser.add_argument("--attempts", type=int, default=1)
    args = parser.parse_args()

    settings = load_settings(str(ROOT / ".env"))
    if not settings.foundry_project_endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT is required")
        return 1

    query = args.prompt or _row_query(args.suite, args.row_index)
    print("QUERY:", query[:400])

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(endpoint=settings.foundry_project_endpoint, credential=DefaultAzureCredential())
    client = project.get_openai_client()

    results = [_stream_once(client, query, i + 1) for i in range(args.attempts)]
    ok = sum(1 for r in results if r["status"] == "completed")
    print(f"\nSUMMARY: {ok}/{len(results)} completed | "
          + " | ".join(f"#{r['attempt']}:{r['status']}({len(r['steps'])} steps)" for r in results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
