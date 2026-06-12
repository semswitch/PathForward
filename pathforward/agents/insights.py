"""Program Insights agent data contracts.

`analyze` is code-test/reconciliation only and returns `source="derivation-floor"`.
`analyze_via_fabric` returns `source="fabric-live"` through the injected live Fabric client.
This module imports neither the Evidence Gate nor mint.
"""
from __future__ import annotations

import json

from ..iq import cohort
from ..iq.models import Ontology, Role, Worker
from .client import INSIGHTS_TAG, LLMClient
from .types import ProgramInsights

INS_INSTRUCTIONS = (
    f"{INSIGHTS_TAG} You are the Program Insights analyst. You are given PRE-COMPUTED, authoritative "
    "cohort and program aggregates (worker_comparison, role_cohort, program). Do NOT recompute, "
    "restate as different numbers, or invent any statistic — reason ONLY over the numbers provided. "
    "Write a concise `narrative` that explains, in plain language, how this worker stands relative to "
    "the cohort targeting the same role, what the cohort's biggest skill bottlenecks are, and why the "
    "chosen reskilling path is reasonable. The narrative is advisory and read-only."
)

# Fabric-live instructions for the Foundry Insights specialist and MCP-backed client.
FABRIC_INS_INSTRUCTIONS = (
    f"{INSIGHTS_TAG} You are the PathForward Program Insights analyst with a Microsoft Fabric data "
    "agent tool over the reskilling ontology (workers, skills, roles, certifications and their edges, "
    "plus derived certgap and readiness, as a OneLake star-schema). For cohort/program questions, "
    "ALWAYS query Fabric via the tool and base your answer ONLY on what it returns — do not guess "
    "numbers. Write a concise, plain-language narrative. This output is advisory and read-only."
)

# strict=False on the live reasoning client, so the single-property schema is accepted as-is.
INSIGHTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"narrative": {"type": "string"}},
    "required": ["narrative"],
}


class ProgramInsightsAgent:
    def __init__(self, client: LLMClient, skill_instructions: str = ""):
        self.client = client
        self.skill_instructions = skill_instructions.strip()

    def _instructions(self, base: str, skill_name: str) -> str:
        if not self.skill_instructions:
            return base
        return (
            f"{base}\n\n"
            f"Loaded Foundry Skill `{skill_name}`:\n"
            f"{self.skill_instructions}\n\n"
            "Follow the loaded skill. Program Insights is advisory, read-only, and off the "
            "credential trust path."
        )

    def analyze(self, worker: Worker, role: Role, onto: Ontology) -> ProgramInsights:
        # Deterministic, code-owned facts (single derivation source). The agent cannot change these.
        rc = cohort.role_cohort(onto, role.id)
        wc = cohort.worker_vs_cohort(onto, worker.id)
        prog = cohort.program_aggregates(onto)

        payload = {
            "worker_id": worker.id,
            "role_id": role.id,
            "worker_comparison": wc.to_doc(),
            "role_cohort": rc.to_doc(),
            "program": prog.to_doc(),
        }
        resp = self.client.respond(self._instructions(INS_INSTRUCTIONS, "/pathforward-insights"),
                                   json.dumps(payload), schema=INSIGHTS_SCHEMA)
        parsed = resp.parsed or {}
        # GATE: we read ONLY the narrative from the model. Every number comes from the code-computed
        # aggregates above — anything numeric the model returns is ignored, so it cannot fabricate.
        narrative = str(parsed.get("narrative", ""))

        return ProgramInsights(
            worker_id=worker.id, role_id=role.id,
            role_cohort=rc.to_doc(), worker_comparison=wc.to_doc(), program=prog.to_doc(),
            narrative=narrative, source="derivation-floor",
        )

    def analyze_via_fabric(self, worker: Worker, role: Role, onto: Ontology) -> ProgramInsights:
        """Fabric-live tier. The injected client must query the published Fabric data agent."""
        # Reconciliation anchor; never used for product Fabric claims.
        rc = cohort.role_cohort(onto, role.id)
        wc = cohort.worker_vs_cohort(onto, worker.id)
        prog = cohort.program_aggregates(onto)

        question = (
            f"Using the connected Fabric data, analyze the cohort of workers targeting the role "
            f"'{role.name}' (role id {role.id}). Report: (1) how many workers target this role; "
            f"(2) their average readiness, where readiness = covered required skills / total required "
            f"skills per worker; (3) the required skills missing for the most workers (top "
            f"bottlenecks). Then state how worker {worker.id} compares to that cohort."
        )
        resp = self.client.respond(self._instructions(FABRIC_INS_INSTRUCTIONS,
                                                      "/pathforward-insights"), question)
        parsed = resp.parsed or {}
        # The Fabric tier returns free-text NL2SQL answers; take the narrative (parsed.narrative if a
        # schema was used, else the raw output). The numbers below remain the code-owned anchor.
        narrative = str(parsed.get("narrative") or resp.output_text or "")

        return ProgramInsights(
            worker_id=worker.id, role_id=role.id,
            role_cohort=rc.to_doc(), worker_comparison=wc.to_doc(), program=prog.to_doc(),
            narrative=narrative, source="fabric-live",
        )
