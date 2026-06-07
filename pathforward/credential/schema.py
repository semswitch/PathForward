"""W3C Verifiable Credentials 2.0-aligned proof artifact."""
from __future__ import annotations

from dataclasses import dataclass, field


class CredentialIntegrityError(Exception):
    """Raised when the credential's cited edge does not match the driving CertGap edge."""


@dataclass
class ProofCredential:
    context: list
    type: list
    issuer: str
    valid_from: str                     # validity-time (no wall-clock; from ontology as_of)
    credential_subject: dict            # {worker_id, skill_id, readiness, cited_edge_id}
    evidence: list                      # citation ref ids supporting the assessment
    calibration: dict                   # {difficulty, discrimination, label}
    proof: dict = field(default_factory=dict)   # placeholder for a signed VC proof (Day-6 stretch)

    def to_doc(self) -> dict:
        return {
            "@context": self.context,
            "type": self.type,
            "issuer": self.issuer,
            "validFrom": self.valid_from,
            "credentialSubject": self.credential_subject,
            "evidence": self.evidence,
            "calibration": self.calibration,
            "proof": self.proof,
        }


VC_CONTEXT = ["https://www.w3.org/ns/credentials/v2"]
VC_TYPE = ["VerifiableCredential", "CompetencyCredential"]
ISSUER = "did:web:pathforward.example"   # synthetic issuer DID
