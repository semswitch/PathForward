"""Foundry Hosted Agent wrapper for the PathForward Orchestrator.

The heavy lifting lives in `pathforward.hosted_orchestrator`; this file only adapts it to the
Foundry hosted-agent `responses` protocol.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv

from pathforward.hosted_orchestrator import (
    HostedRequest,
    diagnose_live_toolbox,
    run_hosted_orchestrator,
    summarize_hosted_response,
)
from pathforward.config import load_settings

load_dotenv(override=False)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("pathforward.hosted")


def _parse_request_text(text: str) -> HostedRequest:
    """Accept either plain text or a JSON object for worker/eval selection."""
    message = text
    worker_id = os.getenv("PATHFORWARD_WORKER_ID", "EMP-001")
    approver = "hosted-agent-runtime"
    abstain_probe = False
    try:
        parsed = json.loads(text)
    except Exception:  # noqa: BLE001
        parsed = None
    if isinstance(parsed, dict):
        message = str(parsed.get("message") or parsed.get("input") or text)
        worker_id = str(parsed.get("worker_id") or worker_id)
        approver = str(parsed.get("approver") or approver)
        abstain_probe = bool(parsed.get("abstain_probe", False))
    return HostedRequest(
        message=message,
        worker_id=worker_id,
        approver=approver,
        mode=os.getenv("PATHFORWARD_HOSTED_MODE", "auto"),
        abstain_probe=abstain_probe,
    )


def _extract_text_from_create_response(request: Any, get_input_expanded) -> str:
    inp = getattr(request, "input", "")
    if isinstance(inp, str):
        return inp
    for item in get_input_expanded(request):
        content = getattr(item, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for part in content:
                text = getattr(part, "text", None)
                if text:
                    return text
    return ""


def _run_text_request(text: str) -> str:
    if "diagnose toolbox" in text.lower():
        doc = diagnose_live_toolbox(load_settings())
        return "PathForward hosted Toolbox diagnostic completed.\n\n```json\n" + (
            json.dumps(doc, indent=2) + "\n```"
        )
    doc = run_hosted_orchestrator(_parse_request_text(text))
    return summarize_hosted_response(doc) + "\n\n```json\n" + json.dumps(doc, indent=2) + "\n```"


try:
    from azure.ai.agentserver.responses import (
        CreateResponse,
        ResponseContext,
        ResponseEventStream,
        ResponsesAgentServerHost,
        ResponsesServerOptions,
        get_input_expanded,
    )
except Exception as exc:  # noqa: BLE001
    raise RuntimeError(
        "The hosted responses adapter is not installed. Install "
        "`hosted/pathforward_orchestrator/requirements.txt` before running this entrypoint."
    ) from exc


app = ResponsesAgentServerHost(
    options=ResponsesServerOptions(default_fetch_history_count=10),
)


@app.response_handler
async def handler(
    request: CreateResponse,
    context: ResponseContext,
    cancellation_signal: asyncio.Event,
):
    stream = ResponseEventStream(
        response_id=context.response_id,
        model=getattr(request, "model", None),
    )
    yield stream.emit_created()
    yield stream.emit_in_progress()

    text = _extract_text_from_create_response(request, get_input_expanded)
    if not text:
        text = "Run /pathforward for the default worker."

    loop = asyncio.get_running_loop()
    try:
        reply = await asyncio.wait_for(loop.run_in_executor(None, _run_text_request, text),
                                       timeout=300.0)
    except asyncio.CancelledError:
        reply = "The PathForward Orchestrator request was cancelled."
    except asyncio.TimeoutError:
        reply = "The PathForward Orchestrator timed out before completing."
    except Exception as exc:  # noqa: BLE001
        logger.exception("PathForward hosted request failed")
        reply = f"PathForward hosted request failed: {exc}"

    message_item = stream.add_output_item_message()
    yield message_item.emit_added()
    text_content = message_item.add_text_content()
    yield text_content.emit_added()
    yield text_content.emit_delta(reply)
    yield text_content.emit_text_done()
    yield text_content.emit_done()
    yield message_item.emit_done()
    yield stream.emit_completed()


if __name__ == "__main__":
    app.run()
