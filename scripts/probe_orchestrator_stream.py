"""Stream a single live Prompt Orchestrator turn, dump every event, and pinpoint the failing tool.

Observability probe for the single-shot route. Sends one prompt to the live Foundry Prompt Agent via
the Responses API (streaming), prints each output item AS IT HAPPENS, and writes every raw event to a
redacted JSONL under `.agents/evidence` so we can read the exact `tool_call_id` immediately preceding a
`response.failed` / tool_user_error. SINGLE-SHOT by default (no retry) -- the same one-attempt shape the
Foundry eval target uses.

Examples:
  python scripts/probe_orchestrator_stream.py                       # uses the smoke suite row 0 query
  python scripts/probe_orchestrator_stream.py --prompt "..."        # arbitrary prompt
  python scripts/probe_orchestrator_stream.py --attempts 3          # gauge raw success/failure rate
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pathforward import captured_route as cr  # noqa: E402
from pathforward.config import load_settings  # noqa: E402

AGENT_NAME = "pathforward-orchestrator"
# Output-item types that represent an actual tool/route step (the 400 suspects).
TOOL_ITEM_TYPES = {"mcp_call", "a2a_preview_call", "function_call", "mcp_approval_request", "tool_call"}


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


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
        return {str(k): _jsonable(v) for k, v in vars(obj).items() if not str(k).startswith("_")}
    return str(obj)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if str(k).lower() in {"mint_request_token", "client_secret"} else _redact(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r'("mint_request_token"\s*:\s*")[^"]+("?)', r"\1[REDACTED]\2", value)
        return re.sub(r"(eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+)", "[REDACTED_TOKEN]", value)
    return value


def _row_query(suite: str, row_index: int) -> str:
    rows = []
    for line in (ROOT / suite).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return str(rows[row_index]["query"])


def _label(item: Any) -> str:
    return str(_get(item, "server_label", "") or _get(item, "name", "") or "")


def _is_tool(itype: str) -> bool:
    return itype in TOOL_ITEM_TYPES or "call" in itype


def _stream_once(client: Any, query: str, attempt: int, dump_dir: Path,
                 write_capture: bool = True) -> dict[str, Any]:
    t0 = time.time()
    steps: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    done_items: list[Any] = []  # every output_item.done item (redacted) -> canonical capture
    final = None
    error = None
    last_tool: dict[str, Any] | None = None  # most recent tool call seen -- the 400 suspect on failure
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dump_path = dump_dir / f"probe-stream-a{attempt}-{stamp}.jsonl"
    print(f"\n=== attempt {attempt} -- streaming (dump: {dump_path.name}) ===")
    fh = dump_path.open("w", encoding="utf-8")
    try:
        stream = client.responses.create(
            stream=True,
            input=query,
            tool_choice="auto",
            extra_body={"agent_reference": {"name": AGENT_NAME, "type": "agent_reference"}},
        )
        for event in stream:
            doc = _redact(_jsonable(event))
            fh.write(json.dumps(doc, sort_keys=True) + "\n")
            etype = str(_get(event, "type", ""))
            if etype.endswith("response.output_item.added") or etype.endswith("response.output_item.done"):
                item = _get(event, "item", None)
                if item is None:
                    continue
                if etype.endswith("response.output_item.done"):
                    done_items.append(_redact(_jsonable(item)))  # source for the canonical capture
                itype = str(_get(item, "type", ""))
                if itype == "reasoning":
                    continue  # skip noisy reasoning items
                iid = str(_get(item, "id", ""))
                label = _label(item)
                status = str(_get(item, "status", ""))
                phase = "done" if etype.endswith("done") else "start"
                elapsed = time.time() - t0
                if _is_tool(itype):
                    row = {"id": iid, "type": itype, "name": label, "status": status, "phase": phase}
                    last_tool = row
                    tool_calls.append(row)
                    steps.append({"t": round(elapsed, 1), **row})
                    print(f"  +{elapsed:6.1f}s  {phase:5} {itype:20} {label:28} id={iid[:36]:36} [{status}]")
                elif phase == "done":
                    steps.append({"t": round(elapsed, 1), "phase": phase, "type": itype,
                                  "name": label, "id": iid, "status": status})
                    print(f"  +{elapsed:6.1f}s  {phase:5} {itype:20} {label:28} [{status}]")
            elif etype in ("response.completed", "response.failed", "response.incomplete"):
                final = _get(event, "response", None)
                print(f"  +{time.time() - t0:6.1f}s  EVENT: {etype}")
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        print(f"  +{time.time() - t0:6.1f}s  EXCEPTION: {error[:400]}")
    finally:
        fh.close()

    status = str(_get(final, "status", "")) if final is not None else ("error" if error else "no_final")
    resp_id = str(_get(final, "id", "")) if final is not None else ""
    print(f"  -> elapsed={time.time() - t0:.1f}s status={status} response_id={resp_id} tool_calls={len(tool_calls)}")
    print("  -> tool calls in order (name @ tool_call_id):")
    for s in tool_calls:
        print(f"       {(s['name'] or s['type']):30} id={s['id']:40} [{s['status']}/{s['phase']}]")
    if status != "completed":
        print(f"  -> SUSPECT (last tool before non-completion): {json.dumps(last_tool)}")
        err = _get(final, "error", None) if final is not None else None
        if err:
            print(f"  -> final.error: {json.dumps(_jsonable(err))[:500]}")

    capture_path = ""
    if write_capture and status == "completed" and done_items:
        events = cr.events_from_stream_items(done_items)
        capture = cr.build_canonical_capture(
            agent=AGENT_NAME, query=query, response_id=resp_id, status=status,
            source="stream", events=events,
        )
        out = dump_dir / f"captured-route-{stamp}.json"
        out.write_text(json.dumps(capture, indent=2, sort_keys=True), encoding="utf-8")
        capture_path = str(out)
        print(f"  -> canonical capture: {out.name} ({len(events)} events) "
              f"[score it: python scripts/capture_and_score_route.py --capture {out.relative_to(ROOT)}]")

    return {"attempt": attempt, "status": status, "response_id": resp_id, "error": error,
            "tool_calls": tool_calls, "last_tool": last_tool, "dump": str(dump_path),
            "capture": capture_path}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--suite", default="eval/suites/prompt_orchestrator_smoke.jsonl")
    parser.add_argument("--row-index", type=int, default=0)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--capture", action=argparse.BooleanOptionalAction, default=True,
                        help="Write the canonical captured-route JSON for each completed attempt (default on).")
    args = parser.parse_args()

    settings = load_settings(str(ROOT / ".env"))
    if not settings.foundry_project_endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT is required")
        return 1

    query = args.prompt or _row_query(args.suite, args.row_index)
    print("QUERY:", query[:400])

    dump_dir = ROOT / ".agents" / "evidence"
    dump_dir.mkdir(parents=True, exist_ok=True)

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(endpoint=settings.foundry_project_endpoint, credential=DefaultAzureCredential())
    client = project.get_openai_client()

    results = [_stream_once(client, query, i + 1, dump_dir, write_capture=args.capture)
               for i in range(args.attempts)]
    ok = sum(1 for r in results if r["status"] == "completed")
    print(f"\nSUMMARY: {ok}/{len(results)} completed | "
          + " | ".join(f"#{r['attempt']}:{r['status']}({len(r['tool_calls'])} tool calls)" for r in results))
    for r in results:
        if r["status"] != "completed":
            print(f"  #{r['attempt']} SUSPECT tool: {json.dumps(r['last_tool'])}  dump={r['dump']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
