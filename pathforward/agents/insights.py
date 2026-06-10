"""Program Insights agent — read-only cohort / program-level reasoning, OFF the credential trust path.

This is the "agents reason, code notarizes" shape applied to analytics: deterministic code
(`iq/cohort.py`, over the single derivation source) computes every TRUST-BEARING NUMBER — the
worker's standing in their role cohort, the cohort's skill bottlenecks, the program-wide rollup —
and the agent only NARRATES them ("why this path", cohort framing). The agent's prose is
display-only; it is never trusted, never gates anything, and structurally cannot change a statistic
(the loop reads the code-computed aggregates, not the model's JSON, for every number).

Why it is additive (distinct from the per-item grounding path the Generator uses): the Generator's
Azure AI Search retrieval grounds ONE item against ONE skill's corpus. It cannot answer cohort/
program questions — "how does this worker compare to peers targeting the same role?", "which skills
are the biggest bottlenecks across the cohort?", "which gaps can't even be certified?". Those are
the cross-worker aggregates this agent reasons over.

Two tiers (verified facts + scope in `.agents/decisions/007-program-insights-fabric-readpath.md`):
  - FLOOR (`analyze`, source="derivation-floor"): the agent NARRATES code-computed aggregates over a
    tool-less reasoning client (`FakeLLMClient` offline / `ReasoningFoundryClient` live). Zero Fabric.
  - FABRIC-LIVE (`analyze_via_fabric`, source="fabric-live"): the agent ANSWERS the cohort question by
    querying a published Fabric data agent over OneLake (NL2SQL, OBO) via `FabricInsightsClient`
    (`MicrosoftFabricPreviewTool` on a `PromptAgentDefinition`, same Responses-API `agent_reference`
    shape the other clients use; OBO identity; paid F2+/P1+; preview). `cohort.py` stays the
    reconciliation ANCHOR — a Fabric answer that diverges from derivation is flagged, never trusted to
    gate anything. Both tiers stay OFF the mint path.

Trust posture: constructed with ONLY an `LLMClient` — no handle to the Evidence Gate, `mint`, or a
`LoopResult`; imports neither the gate nor `mint`.
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

# The Fabric-live tier: the model MUST consult the Fabric data agent (it owns the numbers here),
# unlike the floor tier where code owns the numbers and the model only narrates them.
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


def derivation_floor_insights(worker: Worker, role: Role, onto: Ontology, *,
                              reason: str = "") -> ProgramInsights:
    """Deterministic advisory fallback when a live Fabric narrative is unavailable."""
    rc = cohort.role_cohort(onto, role.id)
    wc = cohort.worker_vs_cohort(onto, worker.id)
    prog = cohort.program_aggregates(onto)
    bottlenecks = rc.to_doc().get("bottleneck_skills", [])
    names = ", ".join(str(b.get("name", b.get("skill_id", ""))) for b in bottlenecks[:3])
    reason_note = f" Fabric-live was unavailable ({reason});" if reason else ""
    narrative = (
        f"{reason_note} using derivation-floor cohort facts instead. Worker {worker.id} has "
        f"readiness {wc.worker_readiness} for {role.name} versus a cohort mean of "
        f"{wc.cohort_mean_readiness}. Top cohort bottlenecks: {names or 'none'}."
    ).strip()
    return ProgramInsights(
        worker_id=worker.id, role_id=role.id,
        role_cohort=rc.to_doc(), worker_comparison=wc.to_doc(), program=prog.to_doc(),
        narrative=narrative, source="derivation-floor",
    )


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
        """FABRIC-LIVE tier: the model answers the cohort question by querying the published Fabric
        data agent (NL2SQL over OneLake, OBO). Use with a `FabricInsightsClient`. The code-owned
        `cohort.py` aggregates are still computed and returned as the reconciliation ANCHOR — Fabric is
        advisory and never gates anything (this method never touches the Evidence Gate or mint)."""
        # Reconciliation anchor (single derivation source) — returned alongside the live narrative.
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
