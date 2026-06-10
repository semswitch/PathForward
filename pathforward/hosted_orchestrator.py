"""Hosted Agent entrypoint logic for the PathForward Orchestrator.

This module is intentionally independent of the Foundry hosting adapter. It builds the same
Orchestrator -> Curator -> Generator/Critic/Evidence Gate -> Planner -> Insights route used by the
smoke scripts, then returns a serializable response for the hosted `responses` protocol wrapper.
The hosted wrapper may expose this in Foundry, but the trust-bearing checks stay here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agents.adaptive import AdaptiveController
from .agents.calibration import cold_start_calibrate
from .agents.client import FakeLLMClient
from .agents.conductor import Orchestrator
from .agents.critic import Critic
from .agents.curator import Curator
from .agents.evidence_gate import EvidenceGate
from .agents.generator import Generator
from .agents.insights import ProgramInsightsAgent
from .agents.numeric import LocalNumericChecker
from .agents.orchestrator import run_orchestrated_multiagent
from .agents.planner import Planner
from .config import Settings, load_settings
from .credential.approval import (
    MintApprovalDecision,
    MintApprovalError,
    mint_with_approval,
    request_mint_approval,
)
from .iq import derivation as dv
from .iq.models import Worker
from .iq.seed import HERO_WORKER_ID, build_seed
from .obs.appinsights import emit_custom_event
from .obs import tracing
from .skills import read_skill_file

_ROOT = Path(__file__).resolve().parent.parent
_TOOLBOX_NAME = "pathforward-toolbox"
_SKILL_NAMES = (
    "pathforward",
    "pathforward-curate",
    "pathforward-assess",
    "pathforward-plan",
    "pathforward-insights",
)


@dataclass(frozen=True)
class HostedRequest:
    """A single hosted Orchestrator request.

    `approve_mint` is runtime/user approval, not model approval. Natural-language prompts should
    request an approval packet first; callers may explicitly set this flag only when they are acting
    as the approval surface.
    """

    message: str
    worker_id: str = HERO_WORKER_ID
    approve_mint: bool = False
    deny_mint: bool = False
    approver: str = "hosted-agent-runtime"
    mode: str = "auto"  # auto | live | offline
    abstain_probe: bool = False


class _FabricProgramInsightsAgent(ProgramInsightsAgent):
    """Hosted adapter: make the standard orchestration seam call the Fabric-live method."""

    def analyze(self, worker, role, onto):
        return self.analyze_via_fabric(worker, role, onto)


def _local_skill_bodies() -> dict[str, str]:
    bodies: dict[str, str] = {}
    for name in _SKILL_NAMES:
        bodies[name] = read_skill_file(_ROOT / "skills" / name / "SKILL.md").instructions
    return bodies


def _resolve_mode(settings: Settings, requested: str) -> str:
    mode = (requested or "auto").strip().lower()
    if mode not in {"auto", "live", "offline"}:
        raise ValueError(f"unsupported hosted mode: {requested!r}")
    if mode == "auto":
        return "live" if settings.foundry_project_endpoint else "offline"
    if mode == "live" and not settings.foundry_project_endpoint:
        raise RuntimeError("PATHFORWARD_HOSTED_MODE=live requires FOUNDRY_PROJECT_ENDPOINT")
    return mode


def _load_live_skill_bodies(settings: Settings) -> tuple[dict[str, str], dict[str, Any]]:
    from .toolbox_mcp import read_skills_from_toolbox

    toolbox = os.getenv("PATHFORWARD_TOOLBOX_NAME", _TOOLBOX_NAME)
    bodies, evidence = read_skills_from_toolbox(settings.foundry_project_endpoint,
                                                toolbox, _SKILL_NAMES)
    return bodies, {"source": "foundry-toolbox-mcp", "toolbox": toolbox, **evidence}


def diagnose_live_toolbox(settings: Settings) -> dict[str, Any]:
    """Inspect the hosted runtime's Foundry Toolbox MCP access path."""
    from .toolbox_mcp import diagnose_toolbox_resources

    if not settings.foundry_project_endpoint:
        raise RuntimeError("toolbox diagnostics require FOUNDRY_PROJECT_ENDPOINT")
    toolbox = os.getenv("PATHFORWARD_TOOLBOX_NAME", _TOOLBOX_NAME)
    return {
        "agent": "pathforward-orchestrator",
        "surface": "foundry-hosted-agent",
        "diagnostic": "foundry-toolbox-mcp",
        "toolbox": toolbox,
        **diagnose_toolbox_resources(settings.foundry_project_endpoint, toolbox),
    }


def _build_clients(settings: Settings, mode: str, skill_bodies: dict[str, str]):
    if mode == "offline":
        fake = FakeLLMClient()
        return {
            "orchestrator": fake,
            "curator": fake,
            "generator": fake,
            "critic": fake,
            "planner": fake,
            "insights": fake,
        }, ()

    from .agents.foundry import (
        FabricDataAgentClient,
        FabricInsightsClient,
        FoundryLLMClient,
        ReasoningFoundryClient,
    )

    clients: dict[str, Any] = {
        "orchestrator": ReasoningFoundryClient(settings.foundry_project_endpoint,
                                               "pathforward-hosted-orchestrator",
                                               settings.model_deployment),
        "curator": ReasoningFoundryClient(settings.foundry_project_endpoint,
                                          "pathforward-hosted-curator",
                                          settings.model_deployment),
        "generator": FoundryLLMClient(settings.foundry_project_endpoint,
                                      settings.model_deployment,
                                      index_name=settings.search_index,
                                      agent_name="pathforward-hosted-generator"),
        "critic": ReasoningFoundryClient(settings.foundry_project_endpoint,
                                         "pathforward-hosted-critic",
                                         settings.model_deployment),
        "planner": ReasoningFoundryClient(settings.foundry_project_endpoint,
                                          "pathforward-hosted-planner",
                                          settings.model_deployment),
    }
    if os.getenv("PATHFORWARD_INSIGHTS_TIER", "").strip().lower() == "fabric-live":
        if settings.fabric_data_agent_openai_base:
            clients["insights"] = FabricDataAgentClient(
                settings.fabric_data_agent_openai_base,
                os.getenv("PATHFORWARD_FABRIC_SP_TENANT_ID", ""),
                os.getenv("PATHFORWARD_FABRIC_SP_CLIENT_ID", ""),
                os.getenv("PATHFORWARD_FABRIC_SP_CLIENT_SECRET", ""),
            )
        else:
            if not settings.fabric_connection_name:
                raise RuntimeError(
                    "PATHFORWARD_INSIGHTS_TIER=fabric-live requires either "
                    "FABRIC_DATA_AGENT_OPENAI_BASE or FABRIC_CONNECTION_NAME"
                )
            clients["insights"] = FabricInsightsClient(settings.foundry_project_endpoint,
                                                       settings.fabric_connection_name,
                                                       agent_name="pathforward-hosted-insights-fabric",
                                                       model=settings.model_deployment,
                                                       use_cli_credential=False)
    else:
        clients["insights"] = ReasoningFoundryClient(settings.foundry_project_endpoint,
                                                     "pathforward-hosted-insights",
                                                     settings.model_deployment)
    return clients, tuple(c for c in clients.values() if hasattr(c, "close"))


def _build_insights_agent(client, skill_instructions: str) -> ProgramInsightsAgent:
    if os.getenv("PATHFORWARD_INSIGHTS_TIER", "").strip().lower() == "fabric-live":
        return _FabricProgramInsightsAgent(client, skill_instructions=skill_instructions)
    return ProgramInsightsAgent(client, skill_instructions=skill_instructions)


def run_hosted_orchestrator(request: HostedRequest) -> dict[str, Any]:
    """Run the PathForward hosted Orchestrator route and return a JSON-safe document."""
    settings = load_settings(str(_ROOT / ".env"))
    mode = _resolve_mode(settings, request.mode or os.getenv("PATHFORWARD_HOSTED_MODE", "auto"))
    if mode == "live" and settings.azure_monitor_connection_string:
        tracing.configure_tracing(azure_connection_string=settings.azure_monitor_connection_string,
                                  service_name="pathforward-hosted")

    with tracing.span("hosted.request",
                      **{"pf.surface": "foundry-hosted-agent",
                         "pf.mode": mode,
                         "pf.worker": request.worker_id,
                         "pf.approve_mint": request.approve_mint}) as hosted_span:
        if mode == "live":
            skill_bodies, skill_evidence = _load_live_skill_bodies(settings)
        else:
            skill_bodies = _local_skill_bodies()
            skill_evidence = {"source": "local-skill-files", "skills": list(skill_bodies)}
        hosted_span.set(**{"pf.skill_source": skill_evidence.get("source")})

        clients, closeables = _build_clients(settings, mode, skill_bodies)
        try:
            doc = _run_hosted_orchestrator_inner(request, mode, skill_bodies,
                                                skill_evidence, clients)
            loop = (doc.get("result") or {}).get("loop") or {}
            insights = (doc.get("result") or {}).get("insights") or {}
            hosted_span.set(**{"pf.status": loop.get("status"),
                               "pf.attempts": loop.get("attempts"),
                               "pf.insights_source": insights.get("source"),
                               "pf.approval_requested": bool(doc.get("approval_request")),
                               "pf.credential_issued": bool(doc.get("credential"))})
            emit_custom_event(
                settings.azure_monitor_connection_string,
                "pathforward.hosted.request",
                properties={
                    "service.name": "pathforward-hosted",
                    "pf.surface": "foundry-hosted-agent",
                    "pf.mode": mode,
                    "pf.worker": request.worker_id,
                    "pf.status": loop.get("status"),
                    "pf.skill_id": loop.get("targeted_skill_id"),
                    "pf.insights_source": insights.get("source"),
                    "pf.approval_requested": bool(doc.get("approval_request")),
                    "pf.credential_issued": bool(doc.get("credential")),
                },
                measurements={"pf.attempts": loop.get("attempts") or 0},
            )
            return doc
        except Exception as exc:  # noqa: BLE001
            hosted_span.event("hosted.request_failed",
                              **{"pf.error_type": type(exc).__name__,
                                 "pf.error": str(exc)[:500]})
            emit_custom_event(
                settings.azure_monitor_connection_string,
                "pathforward.hosted.request_failed",
                properties={
                    "service.name": "pathforward-hosted",
                    "pf.surface": "foundry-hosted-agent",
                    "pf.mode": mode,
                    "pf.worker": request.worker_id,
                    "pf.error_type": type(exc).__name__,
                },
            )
            raise
        finally:
            for client in closeables:
                client.close()
            tracing.flush()


def _run_hosted_orchestrator_inner(request: HostedRequest, mode: str,
                                   skill_bodies: dict[str, str],
                                   skill_evidence: dict[str, Any],
                                   clients: dict[str, Any]) -> dict[str, Any]:
    """Implementation body split out so the public entrypoint can own tracing/cleanup."""
    onto = build_seed()
    worker_id = request.worker_id
    if request.abstain_probe:
        worker_id = "EMP-ABSTAIN"
        # Synthetic hosted proof case: the worker is missing only S09 for R-DEVOPS. S09 has no
        # certification corpus in the seed, so the Curator has no assessable gap and the route must
        # return a normal fail-closed ABSTAIN document with no approval request or credential.
        onto.workers[worker_id] = Worker(
            worker_id, "Worker EMP-ABSTAIN", "Synthetic ABSTAIN proof worker", "R-DEVOPS",
            ("S06", "S07", "S08", "S11"), 5.0, (),
        )
    worker = onto.workers.get(worker_id)
    if worker is None:
        raise ValueError(f"unknown worker_id: {worker_id}")
    role = onto.roles[worker.target_role_id]
    edges = dv.build_all_edges(onto)

    # Imported lazily so importing the hosted module does not depend on scripts at test discovery.
    from scripts.generate_data import _learner_responses

    adaptive = AdaptiveController(calibration=cold_start_calibrate(_learner_responses(onto)))
    result = run_orchestrated_multiagent(
        worker, onto, edges,
        Orchestrator(clients["orchestrator"], skill_instructions=skill_bodies["pathforward"]),
        Curator(clients["curator"], skill_instructions=skill_bodies["pathforward-curate"]),
        Generator(clients["generator"], skill_instructions=skill_bodies["pathforward-assess"]),
        EvidenceGate(LocalNumericChecker()),
        Planner(clients["planner"], LocalNumericChecker(),
                skill_instructions=skill_bodies["pathforward-plan"]),
        critic=Critic(clients["critic"], skill_instructions=skill_bodies["pathforward-assess"]),
        adaptive=adaptive,
        insights=_build_insights_agent(
            clients["insights"],
            skill_instructions=skill_bodies["pathforward-insights"],
        ),
    )

    approval = None
    credential = None
    mint_error = ""
    if result.loop.status == "verified":
        approval_request = request_mint_approval(worker, role, result.loop.driving_edge_id,
                                                 result.loop.targeted_skill_id, result.loop)
        approval = approval_request.to_doc()
        if request.approve_mint or request.deny_mint:
            try:
                decision = MintApprovalDecision(approval_request.request_id, request.approve_mint,
                                                request.approver,
                                                "approved by hosted-agent approval surface"
                                                if request.approve_mint
                                                else "denied by hosted-agent approval surface")
                cred = mint_with_approval(worker, role, result.loop.driving_edge_id,
                                          result.loop.targeted_skill_id, result.loop, decision)
                credential = cred.to_doc()
            except MintApprovalError as exc:
                mint_error = str(exc)

    return {
        "agent": "pathforward-orchestrator",
        "surface": "foundry-hosted-agent",
        "mode": mode,
        "message": request.message,
        "worker_id": worker.id,
        "target_role_id": role.id,
        "skill_evidence": skill_evidence,
        "result": result.to_doc(),
        "approval_request": approval,
        "credential": credential,
        "mint_error": mint_error,
    }


def summarize_hosted_response(doc: dict[str, Any]) -> str:
    """Human-readable response text for the Foundry dashboard."""
    result = doc["result"]
    loop = result["loop"]
    orch = result.get("orchestrator") or {}
    target = orch.get("selected_target_skill_id") or loop.get("targeted_skill_id") or "(none)"
    lines = [
        "PathForward Orchestrator completed.",
        f"Surface: {doc['surface']} ({doc['mode']})",
        f"Worker: {doc['worker_id']} -> role {doc['target_role_id']}",
        f"Selected skill: {target}",
        f"Assessment: {loop['status'].upper()} after {loop['attempts']} attempt(s)",
        f"Skill source: {doc['skill_evidence'].get('source')}",
    ]
    if doc.get("approval_request") and not doc.get("credential"):
        lines.append(f"Mint approval required: {doc['approval_request']['request_id']}")
    if doc.get("credential"):
        subject = doc["credential"]["credentialSubject"]
        lines.append(f"Credential minted: cited_edge_id={subject.get('cited_edge_id')}")
    if doc.get("mint_error"):
        lines.append(f"Mint refused: {doc['mint_error']}")
    return "\n".join(lines)
