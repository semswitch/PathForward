"""Cohort / program-level read aggregates — the read-only data layer the Program Insights agent
reasons over.

Every number here is computed from the SAME derivation functions (`cert_gap_skill_ids`,
`readiness_score`) that feed the Search mirror and the credential, so the cohort/program view can
never disagree with the per-worker trust path — and the Insights agent reasons over numbers it
cannot fabricate (it only narrates; the facts are code-owned).

This module is strictly READ-ONLY and OFF the credential trust path:
  - it imports neither the Evidence Gate nor `mint`;
  - it never mutates the ontology, an edge, or a derivation;
  - nothing it returns is consumed by `EvidenceGate.verify()` or `mint()`.

Two-tier posture (see `.agents/decisions/007-program-insights-fabric-readpath.md`): this in-process
layer is the always-green FLOOR. The live tier — a Fabric data agent over OneLake exposed to a
Foundry agent via `MicrosoftFabricPreviewTool` (OBO identity, paid F2+ or Power BI Premium P1+
capacity) — would serve the same cohort aggregates from governed OneLake when capacity is un-paused.
The aggregates are DEFINED here, so the two tiers reconcile by construction; the Fabric tier changes
where the numbers are read from, never what they are.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from . import derivation as dv
from .models import Ontology, Role, Worker
from .traversal import is_assessable


@dataclass(frozen=True)
class SkillGap:
    """A required skill and how many in-scope workers carry it as a certification gap."""
    skill_id: str
    name: str
    domain: str
    gap_count: int          # workers in scope missing this skill (derived; never raw data)
    assessable: bool        # has certification corpus (== traversal.is_assessable)

    def to_doc(self) -> dict:
        return {"skill_id": self.skill_id, "name": self.name, "domain": self.domain,
                "gap_count": self.gap_count, "assessable": self.assessable}


@dataclass(frozen=True)
class RoleCohort:
    """The cohort of workers targeting one role, and that role's biggest skill bottlenecks."""
    role_id: str
    role_name: str
    n_workers: int
    mean_readiness: float
    median_readiness: float
    bottleneck_skills: tuple[SkillGap, ...]   # required skills, gap_count desc, role order tiebreak
    as_of: str
    derivation_version: str

    def to_doc(self) -> dict:
        return {"role_id": self.role_id, "role_name": self.role_name, "n_workers": self.n_workers,
                "mean_readiness": self.mean_readiness, "median_readiness": self.median_readiness,
                "bottleneck_skills": [s.to_doc() for s in self.bottleneck_skills],
                "as_of": self.as_of, "derivation_version": self.derivation_version}


@dataclass(frozen=True)
class WorkerCohortComparison:
    """How one worker's readiness stands against the cohort targeting the same role."""
    worker_id: str
    role_id: str
    worker_readiness: float
    cohort_mean_readiness: float
    cohort_median_readiness: float
    n_cohort: int
    delta_vs_mean: float            # worker_readiness - cohort_mean (signed)
    rank: int                       # 1 = most ready in the cohort (ties share the better rank)
    percentile: float               # 0..100, share of cohort PEERS this worker outranks (strictly more
                                    #   ready than) — aligned with rank: last place -> ~0, top -> ~100

    def to_doc(self) -> dict:
        return {"worker_id": self.worker_id, "role_id": self.role_id,
                "worker_readiness": self.worker_readiness,
                "cohort_mean_readiness": self.cohort_mean_readiness,
                "cohort_median_readiness": self.cohort_median_readiness,
                "n_cohort": self.n_cohort, "delta_vs_mean": self.delta_vs_mean,
                "rank": self.rank, "percentile": self.percentile}


@dataclass(frozen=True)
class ProgramAggregates:
    """Program-wide rollup across every worker/role — the view the per-item path cannot produce."""
    n_workers: int
    n_roles: int
    overall_mean_readiness: float
    top_bottlenecks: tuple[SkillGap, ...]          # program-wide, gap_count desc
    unassessable_gap_skill_ids: tuple[str, ...]    # gaps with NO certification corpus (e.g. S09)
    as_of: str
    derivation_version: str

    def to_doc(self) -> dict:
        return {"n_workers": self.n_workers, "n_roles": self.n_roles,
                "overall_mean_readiness": self.overall_mean_readiness,
                "top_bottlenecks": [s.to_doc() for s in self.top_bottlenecks],
                "unassessable_gap_skill_ids": list(self.unassessable_gap_skill_ids),
                "as_of": self.as_of, "derivation_version": self.derivation_version}


def _round(x: float) -> float:
    return round(x, 4)


def _cohort_workers(onto: Ontology, role_id: str) -> list[Worker]:
    """Workers whose reskilling TARGET is `role_id`, in stable id order."""
    return [w for w in sorted(onto.workers.values(), key=lambda w: w.id)
            if w.target_role_id == role_id]


def role_cohort(onto: Ontology, role_id: str) -> RoleCohort:
    """Aggregate the cohort targeting `role_id`: cohort readiness (mean/median) and the role's
    skill bottlenecks ranked by how many cohort workers miss each required skill.

    All numbers are derived via `readiness_score` / `cert_gap_skill_ids` — the sole derivation
    source — so this reconciles with the per-worker path by construction."""
    role: Role = onto.roles[role_id]
    workers = _cohort_workers(onto, role_id)
    readiness = [dv.readiness_score(w, role) for w in workers]
    mean_r = _round(statistics.mean(readiness)) if readiness else 0.0
    median_r = _round(statistics.median(readiness)) if readiness else 0.0

    # gap_count per required skill = cohort workers for whom it is a CertGap (missing).
    bottlenecks: list[SkillGap] = []
    for order, sid in enumerate(role.required_skill_ids):
        gap_count = sum(1 for w in workers if sid in dv.cert_gap_skill_ids(w, role))
        skill = onto.skills[sid]
        bottlenecks.append(SkillGap(skill_id=sid, name=skill.name, domain=skill.domain,
                                    gap_count=gap_count, assessable=is_assessable(sid, onto)))
    # rank by gap_count desc, role-required order as the deterministic tiebreak.
    order_index = {sid: i for i, sid in enumerate(role.required_skill_ids)}
    bottlenecks.sort(key=lambda s: (-s.gap_count, order_index[s.skill_id]))

    return RoleCohort(role_id=role_id, role_name=role.name, n_workers=len(workers),
                      mean_readiness=mean_r, median_readiness=median_r,
                      bottleneck_skills=tuple(bottlenecks), as_of=dv.ONTOLOGY_AS_OF,
                      derivation_version=dv.DERIVATION_VERSION)


def worker_vs_cohort(onto: Ontology, worker_id: str) -> WorkerCohortComparison:
    """Compare one worker's readiness against the cohort targeting the same role.

    Rank and percentile use a CONSISTENT tie convention so they never tell contradictory stories:
    rank is 1-based (1 = most ready), ties sharing the better rank; percentile is the share of the
    other cohort members this worker is *strictly more ready than* (outranks). A tied-last worker
    therefore reads as ~0th percentile (matching its low rank), not mid-pack."""
    worker = onto.workers[worker_id]
    role = onto.roles[worker.target_role_id]
    workers = _cohort_workers(onto, role.id)
    readiness = [dv.readiness_score(w, role) for w in workers]
    me = dv.readiness_score(worker, role)
    n = len(workers)
    mean_r = _round(statistics.mean(readiness)) if readiness else 0.0
    median_r = _round(statistics.median(readiness)) if readiness else 0.0
    # rank: 1 + (cohort members strictly MORE ready). percentile: share of PEERS strictly LESS ready
    # (the same strict convention) over n-1 peers -> top=100, bottom=0, ties share the lower value.
    rank = 1 + sum(1 for r in readiness if r > me)
    strictly_below = sum(1 for r in readiness if r < me)
    percentile = _round(100.0 * strictly_below / (n - 1)) if n > 1 else 100.0
    return WorkerCohortComparison(
        worker_id=worker_id, role_id=role.id, worker_readiness=me,
        cohort_mean_readiness=mean_r, cohort_median_readiness=median_r, n_cohort=n,
        delta_vs_mean=_round(me - mean_r), rank=rank, percentile=percentile)


def program_aggregates(onto: Ontology, top_n: int = 8) -> ProgramAggregates:
    """Program-wide rollup across every worker (each scored against their own target role):
    overall mean readiness, the highest-frequency skill gaps program-wide, and the gap skills that
    are structurally UN-assessable (no certification corpus -> the program cannot certify them)."""
    all_workers = [w for w in onto.workers.values() if w.target_role_id in onto.roles]
    readiness = [dv.readiness_score(w, onto.roles[w.target_role_id]) for w in all_workers]
    overall_mean = _round(statistics.mean(readiness)) if readiness else 0.0

    gap_count: dict[str, int] = {}
    for w in all_workers:
        for sid in dv.cert_gap_skill_ids(w, onto.roles[w.target_role_id]):
            gap_count[sid] = gap_count.get(sid, 0) + 1

    gaps = [SkillGap(skill_id=sid, name=onto.skills[sid].name, domain=onto.skills[sid].domain,
                     gap_count=cnt, assessable=is_assessable(sid, onto))
            for sid, cnt in gap_count.items()]
    gaps.sort(key=lambda s: (-s.gap_count, s.skill_id))   # deterministic: count desc, id asc
    unassessable = tuple(sorted(s.skill_id for s in gaps if not s.assessable))

    return ProgramAggregates(
        n_workers=len(all_workers), n_roles=len(onto.roles), overall_mean_readiness=overall_mean,
        top_bottlenecks=tuple(gaps[:top_n]), unassessable_gap_skill_ids=unassessable,
        as_of=dv.ONTOLOGY_AS_OF, derivation_version=dv.DERIVATION_VERSION)
