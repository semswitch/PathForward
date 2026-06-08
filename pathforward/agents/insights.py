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

Trust posture (verified facts + scope in `.agents/decisions/007-program-insights-fabric-readpath.md`):
  - constructed with ONLY an `LLMClient` — no handle to the Evidence Gate, `mint`, or a `LoopResult`;
  - imports neither the gate nor `mint`;
  - the live swap-in is `ReasoningFoundryClient` (tool-less reasoning agent), identical seam to the
    Curator/Planner. The Fabric-live tier (a Fabric data agent over OneLake via
    `MicrosoftFabricPreviewTool` attached to a `PromptAgentDefinition`, consumed over the same
    Responses-API `agent_reference` shape these clients use; OBO identity; paid F2+ or P1+ capacity —
    preview) would change `source` to 'fabric-live' and serve the same aggregates from governed
    OneLake; the numbers are defined in `cohort.py` so the tiers reconcile.
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

# strict=False on the live reasoning client, so the single-property schema is accepted as-is.
INSIGHTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"narrative": {"type": "string"}},
    "required": ["narrative"],
}


class ProgramInsightsAgent:
    def __init__(self, client: LLMClient):
        self.client = client

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
        resp = self.client.respond(INS_INSTRUCTIONS, json.dumps(payload), schema=INSIGHTS_SCHEMA)
        parsed = resp.parsed or {}
        # GATE: we read ONLY the narrative from the model. Every number comes from the code-computed
        # aggregates above — anything numeric the model returns is ignored, so it cannot fabricate.
        narrative = str(parsed.get("narrative", ""))

        return ProgramInsights(
            worker_id=worker.id, role_id=role.id,
            role_cohort=rc.to_doc(), worker_comparison=wc.to_doc(), program=prog.to_doc(),
            narrative=narrative, source="derivation-floor",
        )
