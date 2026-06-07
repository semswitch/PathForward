"""Mint the competency credential from a verified loop result.

The causal-spine assertion (JC-3): the credential's `cited_edge_id` MUST equal the
CertGap edge that drove the assessment blueprint. If they diverge, the demo's
"this credential proves exactly the gap we found" claim is false — so we fail loud.

Fail-closed: an abstained loop result NEVER mints a credential.
"""
from __future__ import annotations

from ..agents.types import LoopResult
from ..iq.derivation import ONTOLOGY_AS_OF
from ..iq.models import Worker
from .schema import (CredentialIntegrityError, ISSUER, ProofCredential,
                     VC_CONTEXT, VC_TYPE)


def mint(worker: Worker, driving_edge_id: str, skill_id: str, readiness: float,
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
