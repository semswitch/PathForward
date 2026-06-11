"""Code-test LLM client fixtures."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from pathforward.agents.client import (
    CRITIC_TAG,
    CURATOR_TAG,
    GENERATOR_TAG,
    INSIGHTS_TAG,
    LLMResponse,
    ORCHESTRATOR_TAG,
    PLANNER_TAG,
)


@dataclass
class FakeLLMClient:
    """Deterministic stand-in. Counts calls only to mint stable response ids."""

    _n: int = field(default=0)

    def respond(self, instructions: str, input: str, *,
                previous_response_id: Optional[str] = None,
                schema: Optional[dict] = None) -> LLMResponse:
        self._n += 1
        rid = f"resp_fake_{self._n:04d}"
        if GENERATOR_TAG in instructions:
            p = json.loads(input)
            parsed = self._generate(p)
            allowed = list(p.get("allowed_ref_ids", []))
            attempt = int(p.get("attempt", 0))
            retrieved = () if attempt == 0 else tuple(allowed[:1])
            return LLMResponse(rid, json.dumps(parsed), parsed, previous_response_id,
                               retrieved_ref_ids=retrieved)
        if CURATOR_TAG in instructions:
            parsed = self._curate(json.loads(input))
            return LLMResponse(rid, json.dumps(parsed), parsed, previous_response_id)
        if PLANNER_TAG in instructions:
            parsed = self._plan(json.loads(input))
            return LLMResponse(rid, json.dumps(parsed), parsed, previous_response_id)
        if CRITIC_TAG in instructions:
            parsed = self._critique(json.loads(input))
            return LLMResponse(rid, json.dumps(parsed), parsed, previous_response_id)
        if INSIGHTS_TAG in instructions:
            try:
                payload = json.loads(input)
            except json.JSONDecodeError:
                payload = {"question": input}
            parsed = self._insights(payload)
            return LLMResponse(rid, json.dumps(parsed), parsed, previous_response_id)
        if ORCHESTRATOR_TAG in instructions:
            parsed = self._orchestrate(json.loads(input))
            return LLMResponse(rid, json.dumps(parsed), parsed, previous_response_id)
        return LLMResponse(rid, "", {"note": "fake-default"}, previous_response_id)

    _BAND_HOURS = {"foundational": (8, 4), "core": (18, 6), "stretch": (30, 10)}

    @staticmethod
    def _generate(p: dict) -> dict:
        skill = p.get("skill_name", "the target skill")
        edge = p.get("driving_edge_id", "")
        allowed = list(p.get("allowed_ref_ids", []))
        attempt = int(p.get("attempt", 0))
        if attempt == 0:
            return {
                "stem": f"Which approach best demonstrates competency in {skill}?",
                "options": [f"A plausible-sounding answer about {skill}",
                            "An unrelated distractor", "Another distractor"],
                "answer_index": 0,
                "cited_ref_ids": [],
                "numeric_claim": None,
            }
        practice, review = FakeLLMClient._BAND_HOURS.get(p.get("difficulty_band") or "core",
                                                         FakeLLMClient._BAND_HOURS["core"])
        total = practice + review
        return {
            "stem": (f"A learner studied for {skill}. Given a recommended {total} study hours "
                     f"split as {practice} hours of practice and {review} hours of review, "
                     f"what is the total?"),
            "options": [f"{total - 4} hours", f"{total} hours", f"{total + 6} hours"],
            "answer_index": 1,
            "cited_ref_ids": allowed[:1] or [edge],
            "numeric_claim": f"{practice} + {review} == {total}",
        }

    @staticmethod
    def _curate(p: dict) -> dict:
        candidates = list(p.get("candidate_skill_ids", []))
        has = list(p.get("has_skill_ids", []))
        head = has[0] if has else "S99"
        ranking = [head] + candidates
        rationale = {head: "(over-reach) suggested a skill the worker already holds"}
        for s in candidates:
            rationale[s] = f"gap skill {s}: prioritized by adjacency and certification coverage"
        return {"ranking": ranking, "rationale": rationale}

    @staticmethod
    def _critique(p: dict) -> dict:
        cited = list(p.get("cited_ref_ids", []))
        if not cited:
            return {
                "recommendation": "reject",
                "concerns": [{"criterion_name": "answerable_from_evidence", "severity": "high"},
                             {"criterion_name": "citation_relevance", "severity": "high"}],
                "advisory_notes": "No cited evidence - not answerable from sources (advisory only).",
            }
        return {
            "recommendation": "pass",
            "concerns": [{"criterion_name": "ambiguity", "severity": "low"}],
            "advisory_notes": "Grounded and answerable; minor option-phrasing ambiguity (advisory).",
        }

    @staticmethod
    def _insights(p: dict) -> dict:
        wc = p.get("worker_comparison", {}) or {}
        rc = p.get("role_cohort", {}) or {}
        prog = p.get("program", {}) or {}
        bottlenecks = rc.get("bottleneck_skills", []) or []
        top = bottlenecks[0]["name"] if bottlenecks else "the role's required skills"
        narrative = (
            f"This worker sits at rank {wc.get('rank', '?')} of {wc.get('n_cohort', '?')} in the "
            f"{rc.get('role_name', 'target')} cohort (readiness {wc.get('worker_readiness')} vs a "
            f"cohort mean of {wc.get('cohort_mean_readiness')}). The biggest bottleneck across this "
            f"cohort is {top}, which is why the reskilling path leads there first. Program-wide mean "
            f"readiness is {prog.get('overall_mean_readiness')}. (Cohort reasoning is advisory and "
            f"read-only - it never enters the credential decision.)"
        )
        return {"narrative": narrative}

    @staticmethod
    def _plan(p: dict) -> dict:
        capacity = float(p.get("weekly_capacity_hours", 0) or 0)
        gap = [g.get("id") for g in p.get("gap_skills", [])]
        return {
            "sequence": gap,
            "weekly_hours": capacity * 3 if capacity else 99,
            "accessibility_adaptations": ["unlimited tutor hours", "high-contrast materials"],
            "rationale": "Front-load the highest-priority gap, then proceed in adjacency order.",
        }

    @staticmethod
    def _orchestrate(p: dict) -> dict:
        admissible = list(p.get("admissible_skill_ids", []))
        target = p.get("curator_chosen_skill_id") or (admissible[0] if admissible else "")
        steps = [{"action": "curate", "rationale": "rank admissible gaps before assessing"}]
        if target:
            steps.append({"action": "assess", "target_skill_id": target,
                          "rationale": "assess the highest-priority admissible gap"})
            steps.append({"action": "plan", "rationale": "produce advisory learning plan"})
            steps.append({"action": "insights", "rationale": "add read-only cohort/program context"})
            steps.append({"action": "mint_if_verified",
                          "rationale": "request deterministic mint only after gate verification"})
        else:
            steps.append({"action": "abstain", "rationale": "no assessable gap is available"})
        return {
            "steps": steps,
            "rationale": "Use agents for route reasoning; deterministic code validates and notarizes.",
        }
