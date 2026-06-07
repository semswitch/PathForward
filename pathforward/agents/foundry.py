"""Live Foundry generator: gpt-5.5 + the GA Azure AI Search tool, behind the same LLMClient
seam as FakeLLMClient.

The model AUTONOMOUSLY retrieves (tool_choice='auto') and returns a STRUCTURED assessment item.
The json_schema output format must live on the agent DEFINITION (`PromptAgentDefinition.text`) —
per-call `text` is rejected when an agent is referenced. `cited_ref_ids` come back as search
document ids ('__'-keys) and are decoded to derivation ref_ids; `retrieved_ref_ids` come from the
tool trace (never model-authored), feeding the loop's corpus-intersect-retrieved gate.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional

from .client import LLMResponse

_RATE_LIMIT_RETRIES = 6   # the eval/red-team batch can exceed the deployment's per-minute quota

DEFAULT_CONNECTION = "pathforward-search"
DEFAULT_AGENT = "pathforward-generator"

_LIVE_SUFFIX = (
    "\n\nTOOL USE: ALWAYS call the Azure AI Search tool to retrieve evidence about the target "
    "skill and the worker's certification gap BEFORE composing the item, and ground the item only "
    "in retrieved evidence. In cited_ref_ids, list the exact `id` values of the search documents "
    "you grounded on (for example 'certgap__EMP-001__S01', 'requires__R-CLOUD__S01', "
    "'corpus__AZ-204') — only ids that appear in the approved allowed_ref_ids. Set numeric_claim "
    "to a single checkable arithmetic equality like '18 + 6 == 24' ONLY if the item truly involves "
    "arithmetic; otherwise null. Never put the correct answer text inside the stem."
)


def _key_to_ref(key: str) -> str:
    return key.replace("__", "::")


def _is_content_filter(exc: Exception) -> bool:
    """True when the request was blocked by the RAI/content policy (e.g. a jailbreak prompt)."""
    if getattr(exc, "code", None) == "content_filter":
        return True
    s = str(exc).lower()
    return "content_filter" in s or "content management policy" in s


def retrieved_ref_ids(resp) -> tuple[str, ...]:
    """Decode the retrieval trace: azure_ai_search_call_output.documents[].id -> ref_id."""
    out: list[str] = []
    seen: set[str] = set()
    for item in (getattr(resp, "output", None) or []):
        if getattr(item, "type", None) == "azure_ai_search_call_output":
            try:
                docs = json.loads(getattr(item, "output", "") or "{}").get("documents", [])
            except Exception:  # noqa: BLE001
                docs = []
            for d in docs:
                key = d.get("id", "")
                ref = _key_to_ref(key)
                if key and ref not in seen:
                    seen.add(ref)
                    out.append(ref)
    return tuple(out)


@dataclass
class FoundryLLMClient:
    """Drop-in LLMClient backed by a Foundry prompt agent + Azure AI Search tool.

    Lazily creates ONE agent version (search tool + the item json_schema) on first respond() and
    reuses it; call close() to delete it. Keyless via DefaultAzureCredential.
    """
    endpoint: str
    model: str = "reasoning"
    connection_name: str = DEFAULT_CONNECTION
    index_name: str = "pathforward-iq"
    agent_name: str = DEFAULT_AGENT
    _project: object = field(default=None, repr=False)
    _openai: object = field(default=None, repr=False)
    _agent: object = field(default=None, repr=False)

    def _ensure(self, instructions: str, schema: Optional[dict]) -> None:
        if self._agent is not None:
            return
        from azure.ai.projects import AIProjectClient
        from azure.ai.projects.models import (
            AISearchIndexResource, AzureAISearchQueryType, AzureAISearchTool,
            AzureAISearchToolResource, PromptAgentDefinition, PromptAgentDefinitionTextOptions,
            TextResponseFormatJsonSchema,
        )
        from azure.identity import DefaultAzureCredential

        self._project = AIProjectClient(endpoint=self.endpoint, credential=DefaultAzureCredential())
        self._openai = self._project.get_openai_client()
        conn_id = self._project.connections.get(self.connection_name).id
        tool = AzureAISearchTool(azure_ai_search=AzureAISearchToolResource(indexes=[
            AISearchIndexResource(project_connection_id=conn_id, index_name=self.index_name,
                                  query_type=AzureAISearchQueryType.SEMANTIC)]))
        text = None
        if schema:
            text = PromptAgentDefinitionTextOptions(format=TextResponseFormatJsonSchema(
                type="json_schema", name="assessment_item", schema=schema, strict=True))
        # RAI is enforced at the model DEPLOYMENT (raiPolicyName) and DECLARED on the governed toolbox
        # version; agent-definition rai_config is not honored by the prompt-agent runtime on 2.2.0
        # (it rejects even system policy names), so it is intentionally not set here.
        self._agent = self._project.agents.create_version(
            agent_name=self.agent_name,
            definition=PromptAgentDefinition(model=self.model, instructions=instructions + _LIVE_SUFFIX,
                                             tools=[tool], text=text),
            description="PathForward live generator agent.",
        )

    def _create_with_backoff(self, input: str):
        """Call the agent, backing off on the deployment's per-minute rate limit (429)."""
        last: Optional[Exception] = None
        for attempt in range(_RATE_LIMIT_RETRIES):
            try:
                return self._openai.responses.create(
                    input=input, tool_choice="auto",   # AUTONOMY: the model decides to search
                    extra_body={"agent_reference": {"name": self._agent.name, "type": "agent_reference"}},
                )
            except Exception as exc:  # noqa: BLE001
                status = getattr(exc, "status_code", None) or getattr(
                    getattr(exc, "response", None), "status_code", None)
                if status == 429 or "rate limit" in str(exc).lower():
                    last = exc
                    time.sleep(8 * (attempt + 1))   # 8,16,24,... clears the 60s quota window
                    continue
                raise
        raise last  # type: ignore[misc]

    def respond(self, instructions: str, input: str, *,
                previous_response_id: Optional[str] = None,
                schema: Optional[dict] = None) -> LLMResponse:
        self._ensure(instructions, schema)
        try:
            resp = self._create_with_backoff(input)
        except Exception as exc:  # noqa: BLE001
            if _is_content_filter(exc):
                # RAI policy blocked the prompt (e.g. a jailbreak) — surface an empty, ungrounded
                # response so the loop fail-closes. The block IS the defense holding.
                return LLMResponse("", "", {"_content_filtered": True}, previous_response_id,
                                   retrieved_ref_ids=())
            raise
        try:
            parsed = json.loads(resp.output_text or "{}")
        except Exception:  # noqa: BLE001
            parsed = {}
        if "cited_ref_ids" in parsed:
            parsed["cited_ref_ids"] = [_key_to_ref(k) for k in (parsed.get("cited_ref_ids") or [])]
        return LLMResponse(getattr(resp, "id", ""), resp.output_text or "", parsed,
                           previous_response_id, retrieved_ref_ids=retrieved_ref_ids(resp))

    def close(self) -> None:
        if self._agent is not None and self._project is not None:
            try:
                self._project.agents.delete_version(agent_name=self._agent.name,
                                                    agent_version=self._agent.version)
            except Exception:  # noqa: BLE001
                pass
            self._agent = None
