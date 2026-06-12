"""Live Foundry generator: gpt-5.5 + the GA Azure AI Search tool, behind the LLMClient seam.

The model AUTONOMOUSLY retrieves (tool_choice='auto') and returns a STRUCTURED assessment item.
The json_schema output format must live on the agent DEFINITION (`PromptAgentDefinition.text`) —
per-call `text` is rejected when an agent is referenced. `cited_ref_ids` come back as search
document ids ('__'-keys) and are decoded to derivation ref_ids; `retrieved_ref_ids` come from the
tool trace (never model-authored), feeding the loop's corpus-intersect-retrieved gate.
"""
from __future__ import annotations

import json
import time
import uuid
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
        tool = AzureAISearchTool(
            name="pathforward_search",
            description="Search the PathForward IQ corpus for grounded assessment evidence.",
            azure_ai_search=AzureAISearchToolResource(indexes=[
                AISearchIndexResource(project_connection_id=conn_id, index_name=self.index_name,
                                      query_type=AzureAISearchQueryType.SEMANTIC)]),
        )
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


@dataclass
class PersistentFoundryLLMClient:
    """LLMClient for a pre-provisioned Foundry prompt agent with Azure AI Search attached.

    The product prompt-agent route uses this client for the Generator so the agent remains visible
    and versioned in Foundry. It never creates or deletes agent versions at request time.
    """
    endpoint: str
    agent_name: str
    _project: object = field(default=None, repr=False)
    _openai: object = field(default=None, repr=False)

    def _ensure(self) -> None:
        if self._openai is not None:
            return
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential

        self._project = AIProjectClient(endpoint=self.endpoint, credential=DefaultAzureCredential())
        self._openai = self._project.get_openai_client()

    def _create_with_backoff(self, input: str):
        last: Optional[Exception] = None
        for attempt in range(_RATE_LIMIT_RETRIES):
            try:
                return self._openai.responses.create(
                    input=input,
                    tool_choice="auto",
                    extra_body={"agent_reference": {"name": self.agent_name, "type": "agent_reference"}},
                )
            except Exception as exc:  # noqa: BLE001
                status = getattr(exc, "status_code", None) or getattr(
                    getattr(exc, "response", None), "status_code", None)
                if status == 429 or "rate limit" in str(exc).lower():
                    last = exc
                    time.sleep(8 * (attempt + 1))
                    continue
                raise
        raise last  # type: ignore[misc]

    def respond(self, instructions: str, input: str, *,
                previous_response_id: Optional[str] = None,
                schema: Optional[dict] = None) -> LLMResponse:
        self._ensure()
        try:
            resp = self._create_with_backoff(input)
        except Exception as exc:  # noqa: BLE001
            if _is_content_filter(exc):
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
        return None


@dataclass
class ReasoningFoundryClient:
    """Drop-in LLMClient for a TOOL-LESS Foundry reasoning agent (the Curator / Planner).

    Unlike FoundryLLMClient (which attaches Azure AI Search and decodes a retrieval trace), a
    reasoning agent reasons over the structured data handed to it in `input` — it neither retrieves
    nor cites a corpus, so `retrieved_ref_ids` is always (). Each instance lazily creates and caches
    ONE prompt-agent version under `agent_name` (with the caller's json_schema response format) on
    first respond(); call close() to delete it. Keyless via DefaultAzureCredential. This is the
    live client for the Curator/Planner seam — the deterministic gates
    in curator.py / planner.py remain the trust boundary regardless of what the model returns.

    Foundry facts verified via the Microsoft Learn MCP (2026-06-07):
      - `PromptAgentDefinition.tools` is optional (only model + kind are required) -> a tool-less
        prompt agent is valid.
        (learn.microsoft.com/python/api/azure-ai-projects/azure.ai.projects.models.promptagentdefinition)
      - Structured JSON output (PromptAgentDefinitionTextOptions) works without tools.
      - `TextResponseFormatJsonSchema.strict` defaults to False; the FULL JSON Schema is allowed when
        strict=False (the strict subset — additionalProperties:false, all-required, no typed maps —
        is required only when strict=True). We use strict=False so the reasoning schemas (e.g. the
        Curator's freeform `rationale` map) are accepted.
        (learn.microsoft.com/azure/ai-foundry/openai/how-to/structured-outputs)
    """
    endpoint: str
    agent_name: str
    model: str = "reasoning"
    _project: object = field(default=None, repr=False)
    _openai: object = field(default=None, repr=False)
    _agent: object = field(default=None, repr=False)

    def _ensure(self, instructions: str, schema: Optional[dict]) -> None:
        if self._agent is not None:
            return
        from azure.ai.projects import AIProjectClient
        from azure.ai.projects.models import (
            PromptAgentDefinition, PromptAgentDefinitionTextOptions, TextResponseFormatJsonSchema,
        )
        from azure.identity import DefaultAzureCredential

        self._project = AIProjectClient(endpoint=self.endpoint, credential=DefaultAzureCredential())
        self._openai = self._project.get_openai_client()
        text = None
        if schema:
            # strict=False: allow the full reasoning schema (the gates, not the schema, are the
            # trust boundary). See the class docstring for the Learn-MCP-verified rationale.
            text = PromptAgentDefinitionTextOptions(format=TextResponseFormatJsonSchema(
                type="json_schema", name="reasoning_output", schema=schema, strict=False))
        # Tool-less by construction: no `tools` attached. RAI is enforced at the model deployment
        # (raiPolicyName), as with the generator agent.
        self._agent = self._project.agents.create_version(
            agent_name=self.agent_name,
            definition=PromptAgentDefinition(model=self.model, instructions=instructions, text=text),
            description=f"PathForward tool-less reasoning agent ({self.agent_name}).",
        )

    def _create_with_backoff(self, input: str):
        """Call the agent (no tool_choice — it has no tools), backing off on the 429 rate limit."""
        last: Optional[Exception] = None
        for attempt in range(_RATE_LIMIT_RETRIES):
            try:
                return self._openai.responses.create(
                    input=input,
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
                # RAI blocked the prompt — surface an empty parse so the gate falls back safely.
                return LLMResponse("", "", {"_content_filtered": True}, previous_response_id,
                                   retrieved_ref_ids=())
            raise
        try:
            parsed = json.loads(resp.output_text or "{}")
        except Exception:  # noqa: BLE001
            parsed = {}
        return LLMResponse(getattr(resp, "id", ""), resp.output_text or "", parsed,
                           previous_response_id, retrieved_ref_ids=())   # reasoning != retrieval

    def close(self) -> None:
        if self._agent is not None and self._project is not None:
            try:
                self._project.agents.delete_version(agent_name=self._agent.name,
                                                    agent_version=self._agent.version)
            except Exception:  # noqa: BLE001
                pass
            self._agent = None


@dataclass
class PersistentReasoningFoundryClient:
    """LLMClient for a pre-provisioned tool-less Foundry prompt agent."""
    endpoint: str
    agent_name: str
    _project: object = field(default=None, repr=False)
    _openai: object = field(default=None, repr=False)

    def _ensure(self) -> None:
        if self._openai is not None:
            return
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential

        self._project = AIProjectClient(endpoint=self.endpoint, credential=DefaultAzureCredential())
        self._openai = self._project.get_openai_client()

    def _create_with_backoff(self, input: str):
        last: Optional[Exception] = None
        for attempt in range(_RATE_LIMIT_RETRIES):
            try:
                return self._openai.responses.create(
                    input=input,
                    extra_body={"agent_reference": {"name": self.agent_name, "type": "agent_reference"}},
                )
            except Exception as exc:  # noqa: BLE001
                status = getattr(exc, "status_code", None) or getattr(
                    getattr(exc, "response", None), "status_code", None)
                if status == 429 or "rate limit" in str(exc).lower():
                    last = exc
                    time.sleep(8 * (attempt + 1))
                    continue
                raise
        raise last  # type: ignore[misc]

    def respond(self, instructions: str, input: str, *,
                previous_response_id: Optional[str] = None,
                schema: Optional[dict] = None) -> LLMResponse:
        self._ensure()
        try:
            resp = self._create_with_backoff(input)
        except Exception as exc:  # noqa: BLE001
            if _is_content_filter(exc):
                return LLMResponse("", "", {"_content_filtered": True}, previous_response_id,
                                   retrieved_ref_ids=())
            raise
        try:
            parsed = json.loads(resp.output_text or "{}")
        except Exception:  # noqa: BLE001
            parsed = {}
        return LLMResponse(getattr(resp, "id", ""), resp.output_text or "", parsed,
                           previous_response_id, retrieved_ref_ids=())

    def close(self) -> None:
        return None


@dataclass
class FabricDataAgentClient:
    """Drop-in LLMClient for the published Fabric data-agent REST/OpenAI endpoint.

    This is the service-identity route for Program Insights. The published Fabric data-agent endpoint
    supports service-principal tokens, so this client uses `ClientSecretCredential` and the
    OpenAI-compatible assistant surface.

    The output is still advisory and read-only: it only supplies the Program Insights narrative, while
    `cohort.py` remains the reconciliation anchor and the credential mint path never depends on this
    response.
    """
    base_url: str
    tenant_id: str
    client_id: str
    client_secret: str = field(repr=False)
    scope: str = "https://analysis.windows.net/powerbi/api/.default"
    api_version: str = "2024-05-01-preview"
    _credential: object = field(default=None, repr=False)
    _openai: object = field(default=None, repr=False)
    _assistant: object = field(default=None, repr=False)

    def _token(self) -> str:
        self._ensure()
        return self._credential.get_token(self.scope).token  # type: ignore[union-attr]

    def _ensure(self) -> None:
        if self._openai is not None:
            return
        if not self.base_url:
            raise RuntimeError("FabricDataAgentClient requires FABRIC_DATA_AGENT_OPENAI_BASE")
        if not (self.tenant_id and self.client_id and self.client_secret):
            raise RuntimeError(
                "FabricDataAgentClient requires tenant_id, client_id, and client_secret "
                "(background service env: PATHFORWARD_FABRIC_SP_TENANT_ID, "
                "PATHFORWARD_FABRIC_SP_CLIENT_ID, PATHFORWARD_FABRIC_SP_CLIENT_SECRET)"
            )
        from azure.identity import ClientSecretCredential
        from openai import OpenAI

        self._credential = ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        self._openai = OpenAI(
            api_key=self._token,
            base_url=self.base_url,
            default_query={"api-version": self.api_version},
            default_headers={"Accept": "application/json"},
        )

    def _assistant_id(self):
        if self._assistant is None:
            self._ensure()
            # Fabric data-agent assistants require a model field, but the published data agent owns
            # the actual model routing. Microsoft samples use the literal "not used".
            self._assistant = self._openai.beta.assistants.create(  # type: ignore[union-attr]
                model="not used"
            )
        return self._assistant.id

    def _create_thread_run(self, input: str):
        self._ensure()
        thread = self._openai.beta.threads.create(  # type: ignore[union-attr]
            extra_headers={"ActivityId": str(uuid.uuid4())}
        )
        self._openai.beta.threads.messages.create(  # type: ignore[union-attr]
            thread_id=thread.id,
            role="user",
            content=input,
        )
        run = self._openai.beta.threads.runs.create(  # type: ignore[union-attr]
            thread_id=thread.id,
            assistant_id=self._assistant_id(),
            extra_headers={"ActivityId": str(uuid.uuid4())},
        )
        return thread.id, run.id

    def _delete_thread(self, thread_id: str) -> None:
        self._ensure()
        try:
            self._openai.beta.threads.delete(thread_id=thread_id)  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass

    def _poll_run(self, thread_id: str, run_id: str):
        self._ensure()
        last = None
        for _ in range(90):
            last = self._openai.beta.threads.runs.retrieve(  # type: ignore[union-attr]
                thread_id=thread_id,
                run_id=run_id,
            )
            status = getattr(last, "status", "")
            if status in {"completed", "failed", "cancelled", "expired"}:
                return last
            time.sleep(2)
        return last

    @staticmethod
    def _run_failure_text(run) -> str:
        detail = getattr(run, "last_error", None) or getattr(run, "incomplete_details", None)
        if detail is None:
            return ""
        code = getattr(detail, "code", "")
        message = getattr(detail, "message", "")
        if isinstance(detail, dict):
            code = detail.get("code", code)
            message = detail.get("message", message)
        return f"{code} {message} {detail}".strip()

    @classmethod
    def _is_transient_run_failure(cls, run) -> bool:
        text = cls._run_failure_text(run).lower()
        return (
            "server_error" in text
            or "internal server" in text
            or "temporar" in text
            or "already completed" in text
            or "timeout" in text
        )

    @staticmethod
    def _message_text(message) -> str:
        parts: list[str] = []
        for item in getattr(message, "content", []) or []:
            text = getattr(item, "text", None)
            if text is not None:
                value = getattr(text, "value", None)
                if value:
                    parts.append(str(value))
                    continue
            value = getattr(item, "value", None)
            if value:
                parts.append(str(value))
        return "\n".join(parts).strip()

    def _latest_assistant_text(self, thread_id: str) -> str:
        self._ensure()
        messages = self._openai.beta.threads.messages.list(  # type: ignore[union-attr]
            thread_id=thread_id,
            order="desc",
            limit=20,
        )
        for msg in getattr(messages, "data", []) or []:
            if getattr(msg, "role", "") == "assistant":
                text = self._message_text(msg)
                if text:
                    return text
        return ""

    def respond(self, instructions: str, input: str, *,
                previous_response_id: Optional[str] = None,
                schema: Optional[dict] = None) -> LLMResponse:
        prompt = f"{instructions.strip()}\n\nUser request:\n{input}".strip()
        last: Optional[Exception] = None
        for attempt in range(_RATE_LIMIT_RETRIES):
            thread_id = ""
            try:
                thread_id, run_id = self._create_thread_run(prompt)
                run = self._poll_run(thread_id, run_id)
                status = getattr(run, "status", "")
                if status != "completed":
                    detail = self._run_failure_text(run)
                    err = RuntimeError(f"Fabric data-agent run ended with status {status}: {detail}")
                    if status == "failed" and self._is_transient_run_failure(run):
                        last = err
                        time.sleep(8 * (attempt + 1))
                        continue
                    raise err
                output = self._latest_assistant_text(thread_id)
                parsed = {"narrative": output} if output else {}
                return LLMResponse(run_id, output, parsed, previous_response_id,
                                   retrieved_ref_ids=())
            except Exception as exc:  # noqa: BLE001
                status = getattr(exc, "status_code", None) or getattr(
                    getattr(exc, "response", None), "status_code", None)
                if status == 429 or "rate limit" in str(exc).lower():
                    last = exc
                    time.sleep(8 * (attempt + 1))
                    continue
                raise
            finally:
                if thread_id:
                    self._delete_thread(thread_id)
        raise last  # type: ignore[misc]

    def close(self) -> None:
        if self._assistant is not None and self._openai is not None:
            try:
                self._openai.beta.assistants.delete(self._assistant.id)
            except Exception:  # noqa: BLE001
                pass
            self._assistant = None
