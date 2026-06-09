"""Governed credential mint approval.

This is the local trust surface for checklist item 5. It models the same shape Microsoft documents
for MCP/Toolbox approval: sensitive tool execution must be approved by the runtime before the call is
made; the endpoint/tool itself is not the enforcement boundary. Here, approval is explicit data that
must match the mint request before `credential.mint.mint()` is called.

This module does not replace `mint()` and does not weaken it. `mint_with_approval()` checks the
approval, then delegates to `mint()`, so the existing loop-status, citation, causal-spine, and
readiness re-derivation checks still run at the final step.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ..agents.types import LoopResult
from ..iq.derivation import ONTOLOGY_AS_OF, readiness_score
from ..iq.models import Role, Worker
from ..obs import tracing
from .mint import mint
from .schema import CredentialIntegrityError, ProofCredential


class MintApprovalError(CredentialIntegrityError):
    """Raised when credential mint approval is missing, denied, or does not match the request."""


@dataclass(frozen=True)
class MintApprovalRequest:
    """A deterministic, reviewable request to mint one credential.

    No model-authored fields are required to authorize this request. The request id is derived from
    code-owned facts so an approval cannot be replayed across a worker, skill, edge, or citation set.
    """

    request_id: str
    worker_id: str
    target_role_id: str
    skill_id: str
    driving_edge_id: str
    loop_status: str
    citations: tuple[str, ...]
    readiness: float
    require_approval: str = "always"

    def to_doc(self) -> dict:
        return {
            "request_id": self.request_id,
            "worker_id": self.worker_id,
            "target_role_id": self.target_role_id,
            "skill_id": self.skill_id,
            "driving_edge_id": self.driving_edge_id,
            "loop_status": self.loop_status,
            "citations": list(self.citations),
            "readiness": self.readiness,
            "require_approval": self.require_approval,
        }


@dataclass(frozen=True)
class MintApprovalDecision:
    """The runtime/human decision for a `MintApprovalRequest`."""

    request_id: str
    approved: bool
    approver: str
    rationale: str = ""

    def to_doc(self) -> dict:
        return {
            "request_id": self.request_id,
            "approved": self.approved,
            "approver": self.approver,
            "rationale": self.rationale,
        }


def _request_id(worker: Worker, role: Role, driving_edge_id: str, skill_id: str,
                loop_result: LoopResult) -> str:
    parts = (
        worker.id,
        role.id,
        driving_edge_id,
        skill_id,
        loop_result.status,
        ",".join(loop_result.citations),
    )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"mintreq_{digest}"


def request_mint_approval(worker: Worker, role: Role, driving_edge_id: str, skill_id: str,
                          loop_result: LoopResult) -> MintApprovalRequest:
    """Create a reviewable approval request for one verified loop result.

    Fail closed: an unverified/abstained loop never even gets an approval request. `mint()` still
    performs the final integrity checks after approval.
    """
    with tracing.span("mint.approval.request",
                      **{"pf.worker": worker.id, "pf.skill": skill_id,
                         "pf.driving_edge": driving_edge_id}) as span:
        if loop_result.status != "verified":
            span.set(**{"pf.approval_requested": False, "pf.reason": "loop_not_verified"})
            raise MintApprovalError(
                f"refusing approval request: loop status is '{loop_result.status}'")
        if not loop_result.citations:
            span.set(**{"pf.approval_requested": False, "pf.reason": "no_citations"})
            raise MintApprovalError("refusing approval request: verified item carries no citations")
        readiness = round(readiness_score(worker, role), 4)
        request = MintApprovalRequest(
            request_id=_request_id(worker, role, driving_edge_id, skill_id, loop_result),
            worker_id=worker.id,
            target_role_id=role.id,
            skill_id=skill_id,
            driving_edge_id=driving_edge_id,
            loop_status=loop_result.status,
            citations=tuple(loop_result.citations),
            readiness=readiness,
        )
        span.set(**{"pf.approval_requested": True, "pf.request_id": request.request_id,
                    "pf.readiness": readiness})
        span.event("mint.approval.requested", **{"pf.request_id": request.request_id})
        return request


def mint_with_approval(worker: Worker, role: Role, driving_edge_id: str, skill_id: str,
                       loop_result: LoopResult, approval: MintApprovalDecision,
                       calibration: dict | None = None,
                       valid_from: str = ONTOLOGY_AS_OF) -> ProofCredential:
    """Mint only after an explicit matching approval decision.

    Denial, missing approval, replayed approval, and tampered approval all fail closed. On approval,
    this function delegates to `mint()`; it does not duplicate or bypass the final mint checks.
    """
    with tracing.span("mint.approval.gate",
                      **{"pf.worker": worker.id, "pf.skill": skill_id,
                         "pf.driving_edge": driving_edge_id}) as span:
        expected = request_mint_approval(worker, role, driving_edge_id, skill_id, loop_result)
        span.set(**{"pf.request_id": expected.request_id, "pf.approved": approval.approved})
        if approval.request_id != expected.request_id:
            span.event("mint.approval.rejected", **{"pf.reason": "request_id_mismatch"})
            raise MintApprovalError(
                f"approval request mismatch: expected {expected.request_id!r}, "
                f"got {approval.request_id!r}")
        if not approval.approved:
            span.event("mint.approval.rejected", **{"pf.reason": "denied"})
            raise MintApprovalError("refusing to mint: approval denied")
        span.event("mint.approval.approved", **{"pf.approver": approval.approver})
        return mint(worker, role, driving_edge_id, skill_id, loop_result, calibration, valid_from)
