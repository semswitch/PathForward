"""Signed mint requests for the hosted MCP mint tool.

The MCP tool receives a sealed request token, not model-authored credential facts. The token is
created only after the assessment loop has reached `verified`, and the MCP tool still delegates to
`mint()` so readiness and causal-spine checks run at issuance time.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Protocol

from ..agents.types import LoopResult
from ..iq.models import Role, Worker
from ..obs import tracing
from .mint import mint
from .schema import CredentialIntegrityError, ProofCredential


class McpMintError(CredentialIntegrityError):
    """Raised when a hosted MCP mint request is invalid or cannot be issued."""


@dataclass(frozen=True)
class McpMintRequest:
    request_id: str
    worker_id: str
    target_role_id: str
    skill_id: str
    driving_edge_id: str
    loop_status: str
    attempts: int
    citations: tuple[str, ...]
    citation_digest: str
    loop_digest: str
    issued_at: int
    expires_at: int
    require_approval: str = "always"

    def to_doc(self) -> dict:
        return {
            "request_id": self.request_id,
            "worker_id": self.worker_id,
            "target_role_id": self.target_role_id,
            "skill_id": self.skill_id,
            "driving_edge_id": self.driving_edge_id,
            "loop_status": self.loop_status,
            "attempts": self.attempts,
            "citations": list(self.citations),
            "citation_digest": self.citation_digest,
            "loop_digest": self.loop_digest,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "require_approval": self.require_approval,
        }


@dataclass(frozen=True)
class SealedMcpMintRequest:
    request: McpMintRequest
    token: str
    tool_name: str = "pathforward_mint_credential"
    server_label: str = "pathforward-mint"
    require_approval: str = "always"

    def to_doc(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "server_label": self.server_label,
            "require_approval": self.require_approval,
            "arguments": {"mint_request_token": self.token},
            "request": self.request.to_doc(),
        }


class MintReplayStore(Protocol):
    def claim(self, request_id: str) -> bool:
        """Return True only once for a request id."""


class MemoryMintReplayStore:
    """Process-local replay guard used by tests and single-worker MCP deployments."""

    def __init__(self):
        self._seen: set[str] = set()

    def claim(self, request_id: str) -> bool:
        if request_id in self._seen:
            return False
        self._seen.add(request_id)
        return True


_DEFAULT_STORE = MemoryMintReplayStore()


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    pad = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + pad).encode("ascii"))


def _canonical_json(doc: dict) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(parts: tuple[str, ...]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _citation_digest(citations: tuple[str, ...]) -> str:
    return _digest(citations)


def _loop_digest(worker: Worker, role: Role, driving_edge_id: str, skill_id: str,
                 loop_result: LoopResult) -> str:
    return _digest((
        worker.id,
        role.id,
        driving_edge_id,
        skill_id,
        loop_result.status,
        str(loop_result.attempts),
        ",".join(loop_result.citations),
    ))


def _request_id(loop_digest: str) -> str:
    return f"mcpmint_{loop_digest[:24]}"


def mint_signing_key() -> str:
    key = os.environ.get("PATHFORWARD_MINT_SIGNING_KEY", "").strip()
    if key:
        return key
    if os.environ.get("PATHFORWARD_ALLOW_DEV_MINT_KEY", "").strip() == "1":
        return "pathforward-dev-mint-key"
    raise McpMintError("PATHFORWARD_MINT_SIGNING_KEY is required for MCP mint requests")


def create_mcp_mint_request(worker: Worker, role: Role, driving_edge_id: str, skill_id: str,
                            loop_result: LoopResult, *, now: int | None = None,
                            ttl_seconds: int = 900,
                            signing_key: str | None = None) -> SealedMcpMintRequest:
    """Create a sealed request after the loop is verified.

    The token is safe to hand to a Foundry MCP approval flow because the payload is signed by code
    and rechecked by the MCP tool before `mint()` is called.
    """
    with tracing.span("mcp_mint.request.create",
                      **{"pf.worker": worker.id, "pf.skill": skill_id,
                         "pf.driving_edge": driving_edge_id}) as span:
        if loop_result.status != "verified":
            span.set(**{"pf.mcp_mint_request": False, "pf.reason": "loop_not_verified"})
            raise McpMintError(f"refusing MCP mint request: loop status is '{loop_result.status}'")
        if not loop_result.citations:
            span.set(**{"pf.mcp_mint_request": False, "pf.reason": "no_citations"})
            raise McpMintError("refusing MCP mint request: verified item carries no citations")
        issued_at = int(time.time() if now is None else now)
        citations = tuple(loop_result.citations)
        loop_digest = _loop_digest(worker, role, driving_edge_id, skill_id, loop_result)
        request = McpMintRequest(
            request_id=_request_id(loop_digest),
            worker_id=worker.id,
            target_role_id=role.id,
            skill_id=skill_id,
            driving_edge_id=driving_edge_id,
            loop_status=loop_result.status,
            attempts=loop_result.attempts,
            citations=citations,
            citation_digest=_citation_digest(citations),
            loop_digest=loop_digest,
            issued_at=issued_at,
            expires_at=issued_at + ttl_seconds,
        )
        token = seal_mcp_mint_request(request, signing_key=signing_key)
        span.set(**{"pf.mcp_mint_request": True, "pf.request_id": request.request_id,
                    "pf.expires_at": request.expires_at})
        span.event("mcp_mint.request.created", **{"pf.request_id": request.request_id})
        return SealedMcpMintRequest(request=request, token=token)


def seal_mcp_mint_request(request: McpMintRequest, *, signing_key: str | None = None) -> str:
    payload = _canonical_json(request.to_doc())
    key = (signing_key or mint_signing_key()).encode("utf-8")
    sig = hmac.new(key, payload, hashlib.sha256).digest()
    return f"{_b64e(payload)}.{_b64e(sig)}"


def open_mcp_mint_request(token: str, *, now: int | None = None,
                          signing_key: str | None = None) -> McpMintRequest:
    try:
        payload_part, sig_part = token.split(".", 1)
        payload = _b64d(payload_part)
        supplied_sig = _b64d(sig_part)
    except Exception as exc:  # noqa: BLE001
        raise McpMintError("invalid MCP mint token format") from exc
    key = (signing_key or mint_signing_key()).encode("utf-8")
    expected_sig = hmac.new(key, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(supplied_sig, expected_sig):
        raise McpMintError("invalid MCP mint token signature")
    try:
        raw = json.loads(payload.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise McpMintError("invalid MCP mint token payload") from exc
    citations = tuple(str(c) for c in raw.get("citations", ()))
    request = McpMintRequest(
        request_id=str(raw.get("request_id", "")),
        worker_id=str(raw.get("worker_id", "")),
        target_role_id=str(raw.get("target_role_id", "")),
        skill_id=str(raw.get("skill_id", "")),
        driving_edge_id=str(raw.get("driving_edge_id", "")),
        loop_status=str(raw.get("loop_status", "")),
        attempts=int(raw.get("attempts", 0)),
        citations=citations,
        citation_digest=str(raw.get("citation_digest", "")),
        loop_digest=str(raw.get("loop_digest", "")),
        issued_at=int(raw.get("issued_at", 0)),
        expires_at=int(raw.get("expires_at", 0)),
        require_approval=str(raw.get("require_approval", "always")),
    )
    current = int(time.time() if now is None else now)
    if not request.request_id.startswith("mcpmint_"):
        raise McpMintError("invalid MCP mint request id")
    if request.require_approval != "always":
        raise McpMintError("MCP mint request must require approval")
    if request.loop_status != "verified":
        raise McpMintError(f"refusing MCP mint: loop status is '{request.loop_status}'")
    if not request.citations:
        raise McpMintError("refusing MCP mint: verified item carries no citations")
    if request.citation_digest != _citation_digest(request.citations):
        raise McpMintError("MCP mint citation digest mismatch")
    if current > request.expires_at:
        raise McpMintError("MCP mint request expired")
    if request.request_id != _request_id(request.loop_digest):
        raise McpMintError("MCP mint request id mismatch")
    return request


def mint_from_mcp_request(worker: Worker, role: Role, token: str, *,
                          replay_store: MintReplayStore | None = None,
                          now: int | None = None,
                          signing_key: str | None = None) -> ProofCredential:
    """Validate a sealed MCP request and issue the credential through deterministic `mint()`."""
    with tracing.span("mcp_mint.tool",
                      **{"pf.tool": "pathforward_mint_credential"}) as span:
        request = open_mcp_mint_request(token, now=now, signing_key=signing_key)
        span.set(**{"pf.request_id": request.request_id, "pf.worker": request.worker_id,
                    "pf.skill": request.skill_id})
        if request.worker_id != worker.id:
            span.event("mcp_mint.rejected", **{"pf.reason": "worker_mismatch"})
            raise McpMintError("MCP mint worker mismatch")
        if request.target_role_id != role.id:
            span.event("mcp_mint.rejected", **{"pf.reason": "role_mismatch"})
            raise McpMintError("MCP mint role mismatch")
        expected_loop_digest = _digest((
            worker.id,
            role.id,
            request.driving_edge_id,
            request.skill_id,
            request.loop_status,
            str(request.attempts),
            ",".join(request.citations),
        ))
        if request.loop_digest != expected_loop_digest:
            span.event("mcp_mint.rejected", **{"pf.reason": "loop_digest_mismatch"})
            raise McpMintError("MCP mint loop digest mismatch")
        store = replay_store or _DEFAULT_STORE
        if not store.claim(request.request_id):
            span.event("mcp_mint.rejected", **{"pf.reason": "replay"})
            raise McpMintError("MCP mint request replay rejected")
        loop = LoopResult(
            status=request.loop_status,
            driving_edge_id=request.driving_edge_id,
            targeted_skill_id=request.skill_id,
            attempts=request.attempts,
            item=None,
            verdict=None,
            transcript=[],
            citations=request.citations,
        )
        credential = mint(worker, role, request.driving_edge_id, request.skill_id, loop)
        span.event("mcp_mint.minted", **{"pf.request_id": request.request_id})
        return credential
