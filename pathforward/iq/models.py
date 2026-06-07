"""Ontology data models.

Frozen dataclasses with tuple fields so entities are hashable and immutable.
Edges carry provenance + validity-time (`effective_at`) and a `source_badge`
distinguishing live-Fabric inference from mirror-served data — both required by
the demo's falsifiable "live recompute" moment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Edge type vocabulary
BASE_EDGE_TYPES = ("has", "requires", "certifies", "targets")
DERIVED_EDGE_TYPES = ("certgap", "readiness")

SOURCE_LIVE = "computed-live (Fabric)"
SOURCE_MIRROR = "served-from-mirror"


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    domain: str = ""


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    required_skill_ids: tuple[str, ...]


@dataclass(frozen=True)
class Certification:
    id: str
    name: str
    certifies_skill_ids: tuple[str, ...]
    recommended_hours: int


@dataclass(frozen=True)
class Worker:
    id: str
    name: str
    current_role_title: str          # free text; the at-risk role being automated
    target_role_id: str              # references a Role in the ontology
    has_skill_ids: tuple[str, ...]
    weekly_capacity_hours: float
    accessibility_needs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Edge:
    id: str
    type: str
    source_id: str
    target_id: str
    derived: bool = False
    derivation_rule: Optional[str] = None
    source_ref_ids: tuple[str, ...] = ()
    provenance: str = ""
    effective_at: str = ""           # ISO date — validity-time of the assertion
    confidence: float = 1.0
    weight: Optional[float] = None    # readiness edges carry the 0..1 score here
    source_badge: str = SOURCE_LIVE

    def to_doc(self) -> dict:
        """Flat dict for JSON serialization / Search indexing."""
        return {
            "id": self.id,
            "type": self.type,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "derived": self.derived,
            "derivation_rule": self.derivation_rule,
            "source_ref_ids": list(self.source_ref_ids),
            "provenance": self.provenance,
            "effective_at": self.effective_at,
            "confidence": self.confidence,
            "weight": self.weight,
            "source_badge": self.source_badge,
        }


@dataclass
class Ontology:
    skills: dict[str, Skill] = field(default_factory=dict)
    roles: dict[str, Role] = field(default_factory=dict)
    certifications: dict[str, Certification] = field(default_factory=dict)
    workers: dict[str, Worker] = field(default_factory=dict)

    def role(self, role_id: str) -> Role:
        return self.roles[role_id]

    def skill(self, skill_id: str) -> Skill:
        return self.skills[skill_id]

    def certs_for_skill(self, skill_id: str) -> list[Certification]:
        return [c for c in self.certifications.values() if skill_id in c.certifies_skill_ids]

    def summary(self) -> dict:
        return {
            "skills": len(self.skills),
            "roles": len(self.roles),
            "certifications": len(self.certifications),
            "workers": len(self.workers),
        }
