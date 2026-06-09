"""Orchestrator / Conductor agent — bounded control-flow reasoning.

The Conductor is the model-backed agent that reasons over *what should happen next* in the
multi-agent workflow. It never verifies an assessment, never sets `status="verified"`, and never
mints a credential. Its output is a typed route plan that deterministic code validates before any
step runs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from ..iq import derivation as dv
from ..iq import traversal
from ..iq.models import Ontology, Role, Worker
from .client import LLMClient, ORCHESTRATOR_TAG

ALLOWED_ACTIONS = (
    "curate",
    "assess",
    "reflect_retry",
    "plan",
    "insights",
    "request_approval",
    "mint_if_verified",
    "abstain",
)

FORBIDDEN_ACTIONS = (
    "mint",
    "verify",
    "set_verified",
    "override_gate",
    "issue_credential",
)

CONDUCTOR_INSTRUCTIONS = (
    f"{ORCHESTRATOR_TAG} You are the PathForward Orchestrator. Reason over the allowed route for "
    "the worker's competency-verification workflow. You may propose only bounded actions from "
    "`allowed_actions`. You NEVER verify, mint, issue credentials, set status='verified', or override "
    "the deterministic Evidence Gate. Return a JSON plan with `steps` and a short `rationale`. "
    "Each step has `action`, optional `target_skill_id`, and `rationale`."
)

CONDUCTOR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {"type": "string", "enum": list(ALLOWED_ACTIONS)},
                    "target_skill_id": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["action", "rationale"],
            },
        },
        "rationale": {"type": "string"},
    },
    "required": ["steps", "rationale"],
}


class OrchestratorPlanError(ValueError):
    """Raised when the Conductor proposes a route that code refuses to execute."""


@dataclass(frozen=True)
class OrchestratorStep:
    action: str
    target_skill_id: str = ""
    rationale: str = ""

    def to_doc(self) -> dict:
        return {"action": self.action, "target_skill_id": self.target_skill_id,
                "rationale": self.rationale}


@dataclass(frozen=True)
class OrchestratorPlan:
    worker_id: str
    role_id: str
    admissible_skill_ids: tuple[str, ...]
    steps: tuple[OrchestratorStep, ...]
    rationale: str = ""
    corrected: bool = False

    def to_doc(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "role_id": self.role_id,
            "admissible_skill_ids": list(self.admissible_skill_ids),
            "steps": [s.to_doc() for s in self.steps],
            "rationale": self.rationale,
            "corrected": self.corrected,
        }

    def first_target_skill_id(self) -> str:
        for step in self.steps:
            if step.action == "assess" and step.target_skill_id:
                return step.target_skill_id
        return ""


class OrchestratorValidator:
    """Deterministic route validator. The Conductor may propose; this class decides what is allowed."""

    def validate(self, plan: OrchestratorPlan, *, require_assessment: bool = True) -> OrchestratorPlan:
        admissible = set(plan.admissible_skill_ids)
        if not plan.steps:
            raise OrchestratorPlanError("orchestrator plan contains no steps")

        corrected = plan.corrected
        seen_curate = False
        seen_assess = False
        seen_terminal = False
        clean: list[OrchestratorStep] = []

        for step in plan.steps:
            action = step.action.strip()
            if action in FORBIDDEN_ACTIONS or action not in ALLOWED_ACTIONS:
                raise OrchestratorPlanError(f"orchestrator proposed forbidden action: {action}")
            if seen_terminal:
                raise OrchestratorPlanError("orchestrator proposed steps after a terminal action")
            if step.target_skill_id and step.target_skill_id not in admissible:
                raise OrchestratorPlanError(
                    f"orchestrator target {step.target_skill_id!r} is outside admissible set")
            if action == "curate":
                seen_curate = True
            if action == "assess":
                if not admissible:
                    raise OrchestratorPlanError("orchestrator proposed assessment with no admissible gaps")
                if not seen_curate:
                    raise OrchestratorPlanError("orchestrator must curate before assessment")
                if not step.target_skill_id:
                    raise OrchestratorPlanError("orchestrator assessment step must name target_skill_id")
                seen_assess = True
            if action == "reflect_retry" and not seen_assess:
                raise OrchestratorPlanError("orchestrator cannot reflect before assessment")
            if action == "mint_if_verified" and not seen_assess:
                raise OrchestratorPlanError("orchestrator cannot request mint before assessment")
            if action == "abstain":
                seen_terminal = True
            clean.append(step)

        if require_assessment and admissible and not any(s.action == "assess" for s in clean):
            raise OrchestratorPlanError("orchestrator omitted assessment despite admissible gaps")
        if not admissible and not any(s.action == "abstain" for s in clean):
            raise OrchestratorPlanError("orchestrator must abstain when no admissible gaps exist")

        if clean != list(plan.steps):
            corrected = True
        return OrchestratorPlan(worker_id=plan.worker_id, role_id=plan.role_id,
                                admissible_skill_ids=plan.admissible_skill_ids,
                                steps=tuple(clean), rationale=plan.rationale,
                                corrected=corrected)


class Orchestrator:
    """Model-backed route reasoner, bounded by `OrchestratorValidator`."""

    def __init__(self, client: LLMClient, validator: OrchestratorValidator | None = None,
                 skill_instructions: str = ""):
        self.client = client
        self.validator = validator or OrchestratorValidator()
        self.skill_instructions = skill_instructions.strip()

    def _instructions(self) -> str:
        if not self.skill_instructions:
            return CONDUCTOR_INSTRUCTIONS
        return (
            f"{CONDUCTOR_INSTRUCTIONS}\n\n"
            "Loaded Foundry Skill `/pathforward`:\n"
            f"{self.skill_instructions}\n\n"
            "Follow the loaded `/pathforward` skill, but the structured output schema and "
            "deterministic validator remain authoritative."
        )

    def plan(self, worker: Worker, role: Role, onto: Ontology, *,
             curator_chosen_skill_id: str = "", prior_loop_status: str = "",
             require_assessment: bool = True) -> OrchestratorPlan:
        admissible = tuple(s for s in dv.cert_gap_skill_ids(worker, role)
                           if traversal.is_assessable(s, onto))
        payload = {
            "worker_id": worker.id,
            "role_id": role.id,
            "target_role": role.name,
            "has_skill_ids": list(worker.has_skill_ids),
            "admissible_skill_ids": list(admissible),
            "curator_chosen_skill_id": curator_chosen_skill_id,
            "prior_loop_status": prior_loop_status,
            "allowed_actions": list(ALLOWED_ACTIONS),
            "forbidden_actions": list(FORBIDDEN_ACTIONS),
        }
        resp = self.client.respond(self._instructions(), json.dumps(payload),
                                   schema=CONDUCTOR_SCHEMA)
        parsed = resp.parsed or {}
        steps = tuple(
            OrchestratorStep(action=str(s.get("action", "")),
                             target_skill_id=str(s.get("target_skill_id", "")),
                             rationale=str(s.get("rationale", "")))
            for s in (parsed.get("steps") or []) if isinstance(s, dict)
        )
        plan = OrchestratorPlan(worker_id=worker.id, role_id=role.id,
                                admissible_skill_ids=admissible, steps=steps,
                                rationale=str(parsed.get("rationale", "")))
        return self.validator.validate(plan, require_assessment=require_assessment)
