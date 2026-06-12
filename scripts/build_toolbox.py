"""Provision scoped Foundry Skills + per-agent Toolboxes.

Registers the repo-local agentskills.io source files under `skills/*/SKILL.md` as versioned Foundry
Skills, then creates one toolbox per product agent. Each toolbox carries only the Skill and tool
surface that its matching agent is allowed to consume:

  - orchestrator: /pathforward
  - curator: /pathforward-curate
  - generator: /pathforward-assess + Azure AI Search
  - critic: /pathforward-assess
  - planner: /pathforward-plan
  - insights: /pathforward-insights + Fabric MCP

Source-verified against azure-ai-projects 2.2.0 (see .agents/decisions/003-foundry-toolbox-
governance.md): beta.skills.create / beta.toolboxes.create_version, with the preview header
(Foundry-Features: {Skills,Toolboxes}=V1Preview) auto-injected by the SDK.

    python scripts/build_toolbox.py --dry-run
    python scripts/build_toolbox.py
    python scripts/build_toolbox.py --rai-policy pathforward-rai
    python scripts/build_toolbox.py --recreate

The RAI policy named by --rai-policy must ALREADY exist and be valid for toolbox consumption;
create_version references it, it does not create it. Default build omits toolbox-level RAI so the
confirmed Skill/Toolbox layer is never blocked on a policy mismatch. Model/deployment RAI remains
separate.
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.agents.versioned import VERSIONED_AGENT_SPECS  # noqa: E402
from pathforward.config import load_settings   # noqa: E402
from pathforward.skills import read_skill_file  # noqa: E402

CONNECTION = "pathforward-search"
SKILL_PATHS = {
    "pathforward": os.path.join(_ROOT, "skills", "pathforward", "SKILL.md"),
    "pathforward-curate": os.path.join(_ROOT, "skills", "pathforward-curate", "SKILL.md"),
    "pathforward-assess": os.path.join(_ROOT, "skills", "pathforward-assess", "SKILL.md"),
    "pathforward-plan": os.path.join(_ROOT, "skills", "pathforward-plan", "SKILL.md"),
    "pathforward-insights": os.path.join(_ROOT, "skills", "pathforward-insights", "SKILL.md"),
}
LEGACY_TOOLBOX_NAME = "pathforward-toolbox"


def build_skill_content(path: str):
    from azure.ai.projects.models import SkillInlineContent
    skill = read_skill_file(path)
    return SkillInlineContent(
        description=skill.description,
        instructions=skill.instructions,
        compatibility=skill.compatibility or None,
        metadata={
            "domain": "workforce-development",
            "ontology": "certgap-edge-driven",
            "source_path": os.path.relpath(path, _ROOT).replace("\\", "/"),
            **(skill.metadata or {}),
        },
    )


def build_search_tool(conn_id: str, index_name: str):
    """The toolbox's azure_ai_search tool — identical ctor shape to the proven GA foundry.py path."""
    from azure.ai.projects.models import (
        AISearchIndexResource, AzureAISearchQueryType, AzureAISearchTool, AzureAISearchToolResource,
    )
    return AzureAISearchTool(
        name="pathforward_search",
        description="Search the PathForward IQ corpus for grounded assessment evidence.",
        azure_ai_search=AzureAISearchToolResource(indexes=[
            AISearchIndexResource(project_connection_id=conn_id, index_name=index_name,
                                  query_type=AzureAISearchQueryType.SEMANTIC)]),
    )


def build_fabric_mcp_tool(conn_id: str, server_url: str):
    from azure.ai.projects.models import MCPTool
    from pathforward.mcp.fabric_server import SERVER_LABEL, TOOL_NAME

    return MCPTool(
        server_label=SERVER_LABEL,
        server_url=server_url,
        require_approval="never",
        allowed_tools=[TOOL_NAME],
        project_connection_id=conn_id,
    )


def build_toolbox_search_tool(role: str):
    from azure.ai.projects.models import ToolboxSearchPreviewTool
    return ToolboxSearchPreviewTool(
        name=f"pathforward_{role}_toolbox_search",
        description=f"Search only the scoped PathForward toolbox for the {role} agent.",
    )


def build_policies(rai_policy_name: str | None):
    if not rai_policy_name:
        return None
    from azure.ai.projects.models import RaiConfig, ToolboxPolicies
    return ToolboxPolicies(rai_config=RaiConfig(rai_policy_name=rai_policy_name))


def _rbac_hint(exc: Exception) -> None:
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    print(f"FAIL: {type(exc).__name__}: {exc}")
    if status in (401, 403):
        print("  -> looks like an RBAC denial. The identity may need the 'Foundry User' role on the "
              "project (in addition to Foundry Project Manager). Surface this scope to the user; do "
              "NOT self-assign roles (auto-mode classifier blocks it).")


def _derived_fabric_mcp_url(settings) -> str:
    if settings.fabric_mcp_url:
        return settings.fabric_mcp_url
    if settings.mcp_mint_url and settings.mcp_mint_url.rstrip("/").endswith("/api/mcp"):
        return settings.mcp_mint_url.rstrip("/")[:-len("/api/mcp")] + "/api/fabric-mcp"
    return ""


def _tools_for_surface(surface: str, *, search_conn_id: str,
                       fabric_mcp_conn_id: str, fabric_mcp_url: str,
                       index_name: str, role: str) -> list:
    if surface == "azure_ai_search":
        return [build_search_tool(conn_id=search_conn_id, index_name=index_name)]
    if surface == "fabric_mcp":
        if not fabric_mcp_conn_id or not fabric_mcp_url:
            raise RuntimeError("Fabric MCP toolbox requires pathforward-fabric-mcp connection and FABRIC_MCP_URL")
        return [build_fabric_mcp_tool(conn_id=fabric_mcp_conn_id, server_url=fabric_mcp_url)]
    return [build_toolbox_search_tool(role)]


def main() -> int:
    ap = argparse.ArgumentParser(description="Provision PathForward Foundry Skills + scoped Toolboxes.")
    ap.add_argument("--dry-run", action="store_true",
                    help="construct skill/tool/toolbox objects offline; make NO Azure calls")
    ap.add_argument("--recreate", action="store_true",
                    help="delete the existing skills + per-agent toolboxes first, then rebuild clean")
    ap.add_argument("--include-legacy-shared", action="store_true",
                    help="also build the old shared pathforward-toolbox compatibility version")
    ap.add_argument("--rai-policy", default=None,
                    help="name of an EXISTING toolbox-valid RAI policy to declare on the toolbox "
                         "version (default: omit toolbox-level RAI)")
    args = ap.parse_args()

    settings = load_settings(os.path.join(_ROOT, ".env"))
    endpoint = (settings.foundry_project_endpoint or "").strip()
    index_name = (settings.search_index or "").strip()
    rai_policy = args.rai_policy or None

    # Validate local Skill files first so --dry-run works on machines without Azure SDK packages.
    skill_files = []
    for expected_name, path in SKILL_PATHS.items():
        skill_file = read_skill_file(path)
        if skill_file.name != expected_name:
            print(f"FAIL: {path} declares name={skill_file.name!r}; expected {expected_name!r}")
            return 1
        skill_files.append(skill_file)
    skill_names = [s.name for s in skill_files]
    print(f"validated: skills {skill_names} + scoped toolboxes "
          f"+ search index '{index_name}' + policies={'RAI:' + rai_policy if rai_policy else 'none'}")
    for spec in VERSIONED_AGENT_SPECS:
        print(f"  scope: {spec.role:12s} toolbox={spec.toolbox_name} "
              f"skill=/{spec.skill_name} tool_surface={spec.tool_surface}")

    if args.dry_run:
        print("DRY RUN: local Skill files validate cleanly; no Azure SDK imports or calls made.")
        return 0

    if not endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT is blank in .env (required for a live build)")
        return 1

    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import ToolboxSkillReference
    from azure.identity import DefaultAzureCredential

    # Construct SDK objects only for a live build. This preserves offline portability while still
    # failing fast on SDK/model-shape errors before making create calls.
    skill_contents = {name: build_skill_content(path) for name, path in SKILL_PATHS.items()}
    placeholder_tool = build_search_tool(conn_id="<resolved-at-runtime>", index_name=index_name)
    policies = build_policies(rai_policy)
    skill_refs = [ToolboxSkillReference(name=name) for name in SKILL_PATHS]
    _ = (placeholder_tool, skill_refs)

    project = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

    try:
        conn_id = project.connections.get(CONNECTION).id
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: could not resolve connection '{CONNECTION}': {type(exc).__name__}: {exc}")
        return 1
    print(f"resolved connection '{CONNECTION}' -> {conn_id}")
    fabric_mcp_url = _derived_fabric_mcp_url(settings)
    fabric_mcp_conn_id = ""
    try:
        fabric_mcp_conn_id = project.connections.get("pathforward-fabric-mcp").id
        print(f"resolved Fabric MCP connection 'pathforward-fabric-mcp' -> {fabric_mcp_conn_id}")
    except Exception as exc:  # noqa: BLE001
        if any(spec.tool_surface == "fabric_mcp" for spec in VERSIONED_AGENT_SPECS):
            print(f"FAIL: could not resolve Fabric MCP connection 'pathforward-fabric-mcp': "
                  f"{type(exc).__name__}: {exc}")
            return 1

    if args.recreate:
        toolbox_names = [spec.toolbox_name for spec in VERSIONED_AGENT_SPECS]
        if args.include_legacy_shared:
            toolbox_names.append(LEGACY_TOOLBOX_NAME)
        delete_ops = [(f"toolbox {name}", lambda n=name: project.beta.toolboxes.delete(n))
                      for name in toolbox_names]
        delete_ops += [(f"skill {name}", lambda n=name: project.beta.skills.delete(n))
                       for name in SKILL_PATHS]
        for label, fn in delete_ops:
            try:
                fn()
                print(f"deleted existing {label} (recreate)")
            except Exception as exc:  # noqa: BLE001
                print(f"(no existing {label} to delete: {type(exc).__name__})")

    # 1) each Skill (default=True -> this version is the one a reference resolves to)
    created_skills = []
    for name in SKILL_PATHS:
        try:
            skill = project.beta.skills.create(name=name, inline_content=skill_contents[name],
                                               default=True)
        except Exception as exc:  # noqa: BLE001
            _rbac_hint(exc)
            return 1
        created_skills.append(skill)
        print(f"SKILL  '{skill.name}' v{skill.version} id={skill.skill_id}")

    created_by_name = {skill.name: skill for skill in created_skills}
    built_toolboxes = []
    for spec in VERSIONED_AGENT_SPECS:
        skills = [ToolboxSkillReference(
            name=spec.skill_name,
            version=created_by_name[spec.skill_name].version,
        )]
        try:
            tools = _tools_for_surface(
                spec.tool_surface,
                search_conn_id=conn_id,
                fabric_mcp_conn_id=fabric_mcp_conn_id,
                fabric_mcp_url=fabric_mcp_url,
                index_name=index_name,
                role=spec.role,
            )
            tb = project.beta.toolboxes.create_version(
                spec.toolbox_name,
                tools=tools,
                description=(
                    f"PathForward scoped toolbox for {spec.role}; "
                    f"skill=/{spec.skill_name}; tool_surface={spec.tool_surface}."
                ),
                metadata={
                    "agent_role": spec.role,
                    "agent_name": spec.agent_name,
                    "skill": spec.skill_name,
                    "tool_surface": spec.tool_surface,
                },
                skills=skills,
                policies=policies,
            )
        except Exception as exc:  # noqa: BLE001
            _rbac_hint(exc)
            return 1
        rai = (tb.policies.rai_config.rai_policy_name
               if tb.policies and tb.policies.rai_config else "none")
        built_toolboxes.append(tb.name)
        print(f"TOOLBOX '{tb.name}' v{tb.version} id={tb.id} tools={len(tb.tools or [])} "
              f"skills={len(tb.skills or [])} rai={rai}")
        try:
            project.beta.toolboxes.update(tb.name, default_version=tb.version)
            print(f"promoted {tb.name} default_version -> v{tb.version}")
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: could not promote {tb.name} default_version: {type(exc).__name__}: {exc}")

    if args.include_legacy_shared:
        legacy_skills = [ToolboxSkillReference(name=name, version=created_by_name[name].version)
                         for name in SKILL_PATHS]
        try:
            legacy_tb = project.beta.toolboxes.create_version(
                LEGACY_TOOLBOX_NAME,
                tools=[build_search_tool(conn_id=conn_id, index_name=index_name)],
                description="Legacy shared PathForward toolbox. Do not use for product agent scope.",
                metadata={"legacy": "true", "replacement": "per-agent-toolboxes"},
                skills=legacy_skills,
                policies=policies,
            )
            project.beta.toolboxes.update(LEGACY_TOOLBOX_NAME,
                                          default_version=legacy_tb.version)
            built_toolboxes.append(legacy_tb.name)
            print(f"LEGACY TOOLBOX '{legacy_tb.name}' v{legacy_tb.version} id={legacy_tb.id}")
        except Exception as exc:  # noqa: BLE001
            _rbac_hint(exc)
            return 1

    # 3) prove the central registry sees them
    tbs = [f"{t.name}" for t in project.beta.toolboxes.list()]
    skl = [f"{s.name}" for s in project.beta.skills.list()]
    print(f"registry toolboxes: {tbs}")
    print(f"registry skills:    {skl}")
    missing_toolboxes = [spec.toolbox_name for spec in VERSIONED_AGENT_SPECS
                         if spec.toolbox_name not in tbs]
    missing_skills = [name for name in SKILL_PATHS if name not in skl]
    if missing_toolboxes or missing_skills:
        print("FAIL: created artifact not visible in the registry listing")
        if missing_toolboxes:
            print(f"missing toolboxes: {missing_toolboxes}")
        if missing_skills:
            print(f"missing skills: {missing_skills}")
        return 1
    print("done. scoped governed seams registered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
