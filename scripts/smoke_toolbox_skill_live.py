"""Live Foundry Skill/Toolbox smoke.

This is the checklist #4 proof path:

  - `skills/pathforward/SKILL.md` has been registered as the Foundry Skill `pathforward`.
  - `pathforward-toolbox` exposes that Skill through its MCP endpoint as
    `skill://pathforward/SKILL.md`.
  - The smoke calls `tools/list`, `resources/list`, and `resources/read`.
  - The Orchestrator receives the MCP-loaded `/pathforward` skill content at inference time.

It intentionally does NOT fall back to the local file for the live proof. Local files are source;
Foundry MCP readback is the runtime-consumption evidence.

    python scripts/build_toolbox.py --recreate
    python scripts/smoke_toolbox_skill_live.py
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any

import httpx

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.agents.adaptive import AdaptiveController  # noqa: E402
from pathforward.agents.calibration import cold_start_calibrate  # noqa: E402
from pathforward.agents.conductor import Orchestrator  # noqa: E402
from pathforward.agents.critic import Critic  # noqa: E402
from pathforward.agents.curator import Curator  # noqa: E402
from pathforward.agents.evidence_gate import EvidenceGate  # noqa: E402
from pathforward.agents.foundry import FoundryLLMClient, ReasoningFoundryClient  # noqa: E402
from pathforward.agents.generator import Generator  # noqa: E402
from pathforward.agents.insights import ProgramInsightsAgent  # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker  # noqa: E402
from pathforward.agents.orchestrator import run_orchestrated_multiagent  # noqa: E402
from pathforward.agents.planner import Planner  # noqa: E402
from pathforward.config import load_settings  # noqa: E402
from pathforward.credential.mint import mint  # noqa: E402
from pathforward.iq import derivation as dv  # noqa: E402
from pathforward.iq import traversal  # noqa: E402
from pathforward.iq.seed import HERO_WORKER_ID, build_seed  # noqa: E402
from generate_data import _learner_responses  # noqa: E402

TOOLBOX_NAME = "pathforward-toolbox"
SKILL_NAME = "pathforward"
ORCHESTRATOR_AGENT = "pathforward-orchestrator-skill"
CURATOR_AGENT = "pathforward-curator-skill"
PLANNER_AGENT = "pathforward-planner-skill"
CRITIC_AGENT = "pathforward-critic-skill"
INSIGHTS_AGENT = "pathforward-insights-skill"
TOKEN_SCOPE = "https://ai.azure.com/.default"


@dataclass
class McpResponse:
    result: dict[str, Any]
    session_id: str = ""


class ToolboxMcpClient:
    def __init__(self, endpoint: str, toolbox_name: str = TOOLBOX_NAME):
        self.url = f"{endpoint.rstrip('/')}/toolboxes/{toolbox_name}/mcp?api-version=v1"
        self.session_id = ""
        self._next_id = 1

    @staticmethod
    def _token() -> str:
        from azure.identity import DefaultAzureCredential
        return DefaultAzureCredential().get_token(TOKEN_SCOPE).token

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._token()}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Foundry-Features": "Toolboxes=V1Preview",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        return headers

    @staticmethod
    def _parse_response(resp: httpx.Response) -> dict[str, Any]:
        text = resp.text.strip()
        if not text:
            return {}
        if "text/event-stream" in resp.headers.get("content-type", ""):
            payloads = []
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    payloads.append(line.partition(":")[2].strip())
            text = payloads[-1] if payloads else "{}"
        return json.loads(text)

    def call(self, method: str, params: dict[str, Any] | None = None) -> McpResponse:
        rid = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params
        resp = httpx.post(self.url, headers=self._headers(), json=payload, timeout=60.0)
        if resp.status_code >= 400:
            raise RuntimeError(f"MCP {method} failed: HTTP {resp.status_code}: {resp.text[:1000]}")
        if sid := resp.headers.get("mcp-session-id"):
            self.session_id = sid
        parsed = self._parse_response(resp)
        if "error" in parsed:
            raise RuntimeError(f"MCP {method} error: {parsed['error']}")
        return McpResponse(result=parsed.get("result") or {}, session_id=self.session_id)

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        resp = httpx.post(self.url, headers=self._headers(), json=payload, timeout=60.0)
        if resp.status_code >= 400:
            raise RuntimeError(f"MCP notification {method} failed: HTTP {resp.status_code}: {resp.text[:1000]}")

    def initialize(self) -> dict[str, Any]:
        init = self.call("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pathforward-toolbox-skill-smoke", "version": "0.1.0"},
        })
        self.notify("notifications/initialized")
        return init.result


def _read_skill_content(result: dict[str, Any]) -> str:
    contents = result.get("contents") or []
    parts: list[str] = []
    for item in contents:
        text = item.get("text") if isinstance(item, dict) else None
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()


def main() -> int:
    settings = load_settings(os.path.join(_ROOT, ".env"))
    if not settings.foundry_project_endpoint:
        print("SKIP: AZURE_AI_PROJECT_ENDPOINT is blank")
        return 0

    print(f"toolbox={TOOLBOX_NAME} skill={SKILL_NAME}")
    mcp = ToolboxMcpClient(settings.foundry_project_endpoint)
    init = mcp.initialize()
    print(f"initialized: protocol={init.get('protocolVersion') or '(unspecified)'} session={bool(mcp.session_id)}")

    tools = mcp.call("tools/list").result.get("tools") or []
    tool_names = [t.get("name") or t.get("type") or "(unnamed)" for t in tools if isinstance(t, dict)]
    print(f"tools/list: {tool_names}")

    resources = mcp.call("resources/list").result.get("resources") or []
    resource_uris = [r.get("uri") for r in resources if isinstance(r, dict)]
    print(f"resources/list: {resource_uris}")
    expected_prefix = f"skill://{SKILL_NAME}"
    skill_uri = next((uri for uri in resource_uris
                      if uri == expected_prefix or uri == f"{expected_prefix}/SKILL.md"), "")
    if not skill_uri:
        print(f"FAIL: no {expected_prefix} resource listed by toolbox MCP resources")
        return 1

    read = mcp.call("resources/read", {"uri": skill_uri}).result
    skill_content = _read_skill_content(read)
    if "PathForward Orchestrator Skill" not in skill_content:
        print("FAIL: resources/read did not return the expected /pathforward skill body")
        return 1
    print(f"resources/read: {skill_uri} chars={len(skill_content)}")

    orchestrator_client = ReasoningFoundryClient(endpoint=settings.foundry_project_endpoint,
                                                 agent_name=ORCHESTRATOR_AGENT,
                                                 model=settings.model_deployment)
    curator_client = ReasoningFoundryClient(endpoint=settings.foundry_project_endpoint,
                                            agent_name=CURATOR_AGENT,
                                            model=settings.model_deployment)
    planner_client = ReasoningFoundryClient(endpoint=settings.foundry_project_endpoint,
                                            agent_name=PLANNER_AGENT,
                                            model=settings.model_deployment)
    critic_client = ReasoningFoundryClient(endpoint=settings.foundry_project_endpoint,
                                           agent_name=CRITIC_AGENT,
                                           model=settings.model_deployment)
    insights_client = ReasoningFoundryClient(endpoint=settings.foundry_project_endpoint,
                                             agent_name=INSIGHTS_AGENT,
                                             model=settings.model_deployment)
    generator_client = FoundryLLMClient(endpoint=settings.foundry_project_endpoint,
                                        model=settings.model_deployment,
                                        index_name=settings.search_index,
                                        agent_name="pathforward-generator-skill")
    clients = (orchestrator_client, curator_client, planner_client, critic_client,
               insights_client, generator_client)
    try:
        onto = build_seed()
        worker = onto.workers[HERO_WORKER_ID]
        role = onto.roles[worker.target_role_id]
        adaptive = AdaptiveController(calibration=cold_start_calibrate(_learner_responses(onto)))
        edges = dv.build_all_edges(onto)

        result = run_orchestrated_multiagent(
            worker, onto, edges,
            Orchestrator(orchestrator_client, skill_instructions=skill_content),
            Curator(curator_client),
            Generator(generator_client),
            EvidenceGate(LocalNumericChecker()),
            Planner(planner_client, LocalNumericChecker()),
            critic=Critic(critic_client),
            adaptive=adaptive,
            insights=ProgramInsightsAgent(insights_client),
        )
        orch = result.orchestrator or {}
        target = orch.get("selected_target_skill_id", "")
        admissible = [s for s in dv.cert_gap_skill_ids(worker, role) if traversal.is_assessable(s, onto)]
        route_ok = bool(target) and target in admissible
        spine_ok = False
        if result.loop.status == "verified":
            cred = mint(worker, role, result.loop.driving_edge_id, result.loop.targeted_skill_id,
                        result.loop)
            spine_ok = cred.credential_subject["cited_edge_id"] == result.loop.driving_edge_id

        print(f"orchestrator: selected={target or '(none)'} admissible={route_ok}")
        print(f"loop: status={result.loop.status.upper()} attempts={result.loop.attempts}")
        print(f"mint spine: {spine_ok}")
        checks = {
            "toolbox MCP tools listed": bool(tool_names),
            "Foundry skill resource read": bool(skill_content),
            "Orchestrator used MCP-loaded /pathforward skill": route_ok,
            "Evidence Gate verified": result.loop.status == "verified",
            "credential spine intact": spine_ok,
            "insights returned": result.insights is not None,
        }
        for name, ok in checks.items():
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not all(checks.values()):
            return 1
        print("LIVE TOOLBOX SKILL PASS")
        return 0
    finally:
        for client in clients:
            client.close()
        print("agents deleted")


if __name__ == "__main__":
    raise SystemExit(main())
