"""JSON-RPC MCP endpoint for Evidence Gate token issuance.

This server verifies a generated assessment item with code-owned retrieval and the deterministic
Evidence Gate. It issues a signed mint request token only after verification. It never mints.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from pathforward.agents.evidence_gate import EvidenceGate
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.types import AssessmentItem, LoopResult, Verdict
from pathforward.credential.mcp_mint import create_mcp_mint_request
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import build_seed


TOOL_NAME = "verify_assessment_and_issue_mint_request"
SERVER_LABEL = "pathforward-gate"
PROTOCOL_VERSION = "2025-06-18"

_REMEDIATION_BY_CRITERION = {
    "grounded": "retrieve and cite approved evidence before composing the item",
    "evidence_answerable": "ensure the answer is derivable from the cited evidence",
    "single_correct": "ensure exactly one option is correct",
    "no_leakage": "do not place the correct answer text in the stem",
    "numeric_valid": "register any arithmetic as a checkable numeric_claim tied to the item",
}

_INPUT_REMEDIATION = (
    "Use only the code-provided worker, role, admissible skill, and the deterministic edge id "
    "`certgap::{worker_id}::{skill_id}` before retrying the gate."
)


class RefRetriever(Protocol):
    def retrieve_refs(self, *, query: str, allowed_ref_ids: tuple[str, ...],
                      worker_id: str, role_id: str, skill_id: str) -> tuple[str, ...]:
        """Return Search-owned ref_ids for the item under review."""


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class McpHttpResult:
    status_code: int
    body: str
    headers: dict[str, str]


def _env(name: str, fallback: str = "") -> str:
    return os.environ.get(name, fallback).strip()


def _json_response(payload: dict[str, Any], status_code: int = 200) -> McpHttpResult:
    return McpHttpResult(
        status_code=status_code,
        body=json.dumps(payload, separators=(",", ":")),
        headers={"Content-Type": "application/json"},
    )


def _rpc_success(rpc_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _rpc_error(rpc_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}


def _tool_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _odata_quote(value: str) -> str:
    return value.replace("'", "''")


def _allowed_filter(allowed_ref_ids: tuple[str, ...]) -> str:
    return " or ".join(f"ref_id eq '{_odata_quote(ref)}'" for ref in allowed_ref_ids)


class AzureSearchRefRetriever:
    def __init__(self, *, endpoint: str, index_name: str):
        if not endpoint:
            raise ValueError("AZURE_SEARCH_ENDPOINT is required for gate retrieval")
        if not index_name:
            raise ValueError("AZURE_SEARCH_INDEX is required for gate retrieval")
        self.endpoint = endpoint
        self.index_name = index_name
        self._client = None

    @staticmethod
    def _credential():
        tenant_id = _env("PATHFORWARD_GATE_SP_TENANT_ID", _env("AZURE_TENANT_ID"))
        client_id = _env("PATHFORWARD_GATE_SP_CLIENT_ID", _env("AZURE_CLIENT_ID"))
        client_secret = _env("PATHFORWARD_GATE_SP_CLIENT_SECRET", _env("AZURE_CLIENT_SECRET"))
        if tenant_id and client_id and client_secret:
            from azure.identity import ClientSecretCredential

            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
        api_key = _env("PATHFORWARD_SEARCH_API_KEY", _env("AZURE_SEARCH_API_KEY"))
        if api_key:
            from azure.core.credentials import AzureKeyCredential

            return AzureKeyCredential(api_key)
        from azure.identity import DefaultAzureCredential

        return DefaultAzureCredential()

    def _search_client(self):
        if self._client is None:
            from azure.search.documents import SearchClient

            self._client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=self._credential(),
            )
        return self._client

    def retrieve_refs(self, *, query: str, allowed_ref_ids: tuple[str, ...],
                      worker_id: str, role_id: str, skill_id: str) -> tuple[str, ...]:
        if not allowed_ref_ids:
            return ()
        search_text = " ".join(part for part in (query, worker_id, role_id, skill_id) if part)
        results = self._search_client().search(
            search_text=search_text or "*",
            filter=_allowed_filter(allowed_ref_ids),
            select=["ref_id"],
            top=max(10, len(allowed_ref_ids)),
        )
        refs: list[str] = []
        seen: set[str] = set()
        for doc in results:
            ref = str(doc.get("ref_id", "")).strip()
            if ref and ref not in seen:
                seen.add(ref)
                refs.append(ref)
        return tuple(refs)


def _retriever_from_env() -> AzureSearchRefRetriever:
    return AzureSearchRefRetriever(
        endpoint=_env("AZURE_SEARCH_ENDPOINT"),
        index_name=_env("AZURE_SEARCH_INDEX", "pathforward-iq"),
    )


def tool_definition() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": (
            "Verify a PathForward assessment item with code-owned Search retrieval and the "
            "deterministic Evidence Gate. Returns a signed mint_request_token only when verified."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "worker_id": {"type": "string"},
                "target_role_id": {"type": "string"},
                "skill_id": {"type": "string"},
                "driving_edge_id": {
                    "type": "string",
                    "description": "Deterministic edge id: certgap::{worker_id}::{skill_id}.",
                },
                "attempt": {"type": "integer"},
                "item": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "stem": {"type": "string"},
                        "options": {"type": "array", "items": {"type": "string"}},
                        "answer_index": {"type": "integer"},
                        "cited_ref_ids": {"type": "array", "items": {"type": "string"}},
                        "numeric_claim": {"type": ["string", "null"]},
                    },
                    "required": [
                        "stem",
                        "options",
                        "answer_index",
                        "cited_ref_ids",
                        "numeric_claim",
                    ],
                },
            },
            "required": ["worker_id", "target_role_id", "skill_id", "driving_edge_id", "item"],
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        "_meta": {
            "tool_configuration": {
                "type": "mcp",
                "server_label": SERVER_LABEL,
                "require_approval": "never",
            }
        },
    }


def _tool_call_result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": _tool_text(payload)}],
        "isError": is_error,
    }
    if not is_error:
        result["structuredContent"] = payload
    return result


def _input_rejection(message: str) -> dict[str, Any]:
    return {
        "status": "rejected",
        "error": message,
        "feedback": {
            "failed_criteria": ["input_contract"],
            "remediation": [_INPUT_REMEDIATION],
        },
        "mint_request": None,
    }


def _string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(v) for v in value if str(v).strip())


def _item_from_payload(args: dict[str, Any], retrieved_ref_ids: tuple[str, ...]) -> AssessmentItem:
    raw = args.get("item")
    if not isinstance(raw, dict):
        raise ValueError("item is required")
    options = _string_list(raw.get("options"))
    return AssessmentItem(
        id=f"item::{args['driving_edge_id']}::gate",
        targeted_skill_id=str(args["skill_id"]),
        driving_edge_id=str(args["driving_edge_id"]),
        stem=str(raw.get("stem", "")),
        options=options,
        answer_index=int(raw.get("answer_index", 0)),
        cited_ref_ids=_string_list(raw.get("cited_ref_ids")),
        retrieved_ref_ids=retrieved_ref_ids,
        numeric_claim=raw.get("numeric_claim"),
        attempt=int(args.get("attempt", 0) or 0),
    )


def _feedback(verdict: Verdict) -> dict[str, Any]:
    failed = [name for name, ok in verdict.criteria.items() if not ok]
    failed = [name for name in failed if name in _REMEDIATION_BY_CRITERION]
    return {
        "failed_criteria": failed,
        "remediation": [_REMEDIATION_BY_CRITERION[name] for name in failed],
    }


def _query_text(raw_item: dict[str, Any]) -> str:
    options = raw_item.get("options") if isinstance(raw_item.get("options"), list) else []
    answer_index = int(raw_item.get("answer_index", 0) or 0)
    answer = str(options[answer_index]) if 0 <= answer_index < len(options) else ""
    return " ".join([str(raw_item.get("stem", "")), answer])


def _verify_and_issue(args: dict[str, Any], *,
                      retriever_factory: Callable[[], RefRetriever] = _retriever_from_env
                      ) -> dict[str, Any]:
    worker_id = str(args.get("worker_id", "")).strip()
    target_role_id = str(args.get("target_role_id", "")).strip()
    skill_id = str(args.get("skill_id", "")).strip()
    driving_edge_id = str(args.get("driving_edge_id", "")).strip()
    if not all((worker_id, target_role_id, skill_id, driving_edge_id)):
        raise ValueError("worker_id, target_role_id, skill_id, and driving_edge_id are required")

    onto = build_seed()
    if worker_id not in onto.workers:
        raise ValueError("unknown worker_id")
    if target_role_id not in onto.roles:
        raise ValueError("unknown target_role_id")
    if skill_id not in onto.skills:
        raise ValueError("unknown skill_id")
    worker = onto.workers[worker_id]
    role = onto.roles[target_role_id]
    skill = onto.skills[skill_id]
    if worker.target_role_id != role.id:
        raise ValueError("target_role_id does not match worker target role")
    expected_edge_id = dv.certgap_edge_id(worker.id, skill.id)
    if driving_edge_id != expected_edge_id:
        raise ValueError("driving_edge_id does not match worker/skill cert gap")
    if skill.id not in dv.cert_gap_skill_ids(worker, role):
        raise ValueError("skill_id is not an active certification gap for this worker and role")
    if not traversal.is_assessable(skill.id, onto):
        raise ValueError("skill_id is not assessable")

    allowed = traversal.approved_refs(worker, skill, onto)
    raw_item = args.get("item") if isinstance(args.get("item"), dict) else {}
    retrieved = retriever_factory().retrieve_refs(
        query=_query_text(raw_item),
        allowed_ref_ids=allowed,
        worker_id=worker.id,
        role_id=role.id,
        skill_id=skill.id,
    )
    effective_allowed = tuple(ref for ref in retrieved if ref in set(allowed))
    item = _item_from_payload(args, effective_allowed)
    gate = EvidenceGate(LocalNumericChecker())
    verdict = gate.verify(item, effective_allowed)
    base = {
        "worker_id": worker.id,
        "target_role_id": role.id,
        "skill_id": skill.id,
        "driving_edge_id": driving_edge_id,
        "approved_ref_ids": list(allowed),
        "retrieved_ref_ids": list(retrieved),
        "effective_allowed_ref_ids": list(effective_allowed),
        "verdict": verdict.to_doc(),
    }
    if not verdict.passed:
        return {
            **base,
            "status": "rejected",
            "feedback": _feedback(verdict),
            "mint_request": None,
        }

    citations = tuple(c for c in item.cited_ref_ids if c in set(effective_allowed))
    loop = LoopResult(
        "verified",
        driving_edge_id,
        skill.id,
        max(1, int(args.get("attempt", 0) or 0) + 1),
        item,
        verdict,
        [{"attempt": item.attempt, "item": item, "critic": None, "verdict": verdict}],
        citations,
    )
    sealed = create_mcp_mint_request(worker, role, driving_edge_id, skill.id, loop)
    return {
        **base,
        "status": "verified",
        "feedback": None,
        "mint_request": sealed.to_doc(),
    }


def handle_jsonrpc(payload: dict[str, Any], *,
                   retriever_factory: Callable[[], RefRetriever] = _retriever_from_env
                   ) -> dict[str, Any] | None:
    method = payload.get("method")
    rpc_id = payload.get("id")
    params = payload.get("params") or {}

    if method == "notifications/initialized" and "id" not in payload:
        return None

    try:
        if method == "initialize":
            return _rpc_success(rpc_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_LABEL, "version": "0.1.0"},
            })
        if method == "tools/list":
            return _rpc_success(rpc_id, {"tools": [tool_definition()]})
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name != TOOL_NAME:
                raise JsonRpcError(-32602, f"unknown tool: {name}")
            try:
                result = _verify_and_issue(arguments, retriever_factory=retriever_factory)
                return _rpc_success(rpc_id, _tool_call_result(result))
            except ValueError as exc:
                return _rpc_success(
                    rpc_id,
                    _tool_call_result(_input_rejection(str(exc)), is_error=False),
                )
            except Exception as exc:  # noqa: BLE001
                return _rpc_success(
                    rpc_id,
                    _tool_call_result({"status": "rejected", "error": str(exc)}, is_error=True),
                )
        raise JsonRpcError(-32601, f"method not found: {method}")
    except JsonRpcError as exc:
        return _rpc_error(rpc_id, exc.code, exc.message)


def handle_http_body(raw_body: bytes, *,
                     retriever_factory: Callable[[], RefRetriever] = _retriever_from_env
                     ) -> McpHttpResult:
    try:
        payload = json.loads(raw_body.decode("utf-8") if raw_body else "{}")
    except Exception:  # noqa: BLE001
        return _json_response(_rpc_error(None, -32700, "parse error"), status_code=400)
    if not isinstance(payload, dict):
        return _json_response(_rpc_error(None, -32600, "invalid request"), status_code=400)
    response = handle_jsonrpc(payload, retriever_factory=retriever_factory)
    if response is None:
        return McpHttpResult(status_code=202, body="", headers={})
    return _json_response(response)
