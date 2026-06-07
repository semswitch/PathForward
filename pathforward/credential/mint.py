"""Mint the competency credential from a verified loop result.

The causal-spine assertion (JC-3): the credential's `cited_edge_id` MUST equal the
CertGap edge that drove the assessment blueprint, that edge must belong to THIS worker
and skill, and the readiness is DERIVED here (never caller-supplied) so it cannot be
inflated. If any invariant breaks, we fail loud.

Fail-closed: an abstained loop result NEVER mints a credential.
"""
from __future__ import annotations

from ..agents.types import LoopResult
from ..iq.derivation import ONTOLOGY_AS_OF, readiness_score
from ..iq.models import Role, Worker
from .schema import (CredentialIntegrityError, ISSUER, ProofCredential,
                     VC_CONTEXT, VC_TYPE)


def mint(worker: Worker, role: Role, driving_edge_id: str, skill_id: str,
         loop_result: LoopResult, calibration: dict | None = None,
         valid_from: str = ONTOLOGY_AS_OF) -> ProofCredential:
    if loop_result.status != "verified":
        raise CredentialIntegrityError(
            f"refusing to mint: loop status is '{loop_result.status}' (fail-closed)")
    if loop_result.driving_edge_id != driving_edge_id:
        raise CredentialIntegrityError(
            f"driving edge mismatch: loop drove {loop_result.driving_edge_id!r} "
            f"but credential cites {driving_edge_id!r}")
    if not loop_result.citations:
        raise CredentialIntegrityError("refusing to mint: verified item carries no citations")

    # Spine integrity (red-team hardening): the cited edge MUST be THIS worker's CertGap edge for
    # THIS skill — not another worker's gap (cross-worker contamination) or a mismatched skill.
    parts = driving_edge_id.split("::")
    if len(parts) != 3 or parts[0] != "certgap":
        raise CredentialIntegrityError(
            f"refusing to mint: cited_edge_id {driving_edge_id!r} is not a CertGap edge")
    edge_worker, edge_skill = parts[1], parts[2]
    if edge_worker != worker.id:
        raise CredentialIntegrityError(
            f"subject worker {worker.id!r} != worker {edge_worker!r} in cited edge {driving_edge_id!r}")
    if edge_skill != skill_id:
        raise CredentialIntegrityError(
            f"skill {skill_id!r} != skill {edge_skill!r} in cited edge {driving_edge_id!r}")
    if role.id != worker.target_role_id:
        raise CredentialIntegrityError(
            f"role {role.id!r} is not the worker's target role {worker.target_role_id!r}")

    # Readiness is DERIVED here from the ontology — never a caller-supplied (inflatable) input.
    readiness = round(readiness_score(worker, role), 4)

    return ProofCredential(
        context=VC_CONTEXT,
        type=VC_TYPE,
        issuer=ISSUER,
        valid_from=valid_from,
        credential_subject={
            "worker_id": worker.id,
            "skill_id": skill_id,
            "target_role_id": worker.target_role_id,
            "readiness": readiness,
            "cited_edge_id": driving_edge_id,   # == the CertGap edge that drove the blueprint
        },
        evidence=list(loop_result.citations),
        calibration=calibration or {"label": "estimated (cold-start)"},
        proof={"type": "DataIntegrityProof", "note": "synthetic demo artifact; not a real credential"},
    )
