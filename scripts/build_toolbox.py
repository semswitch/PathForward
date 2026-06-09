"""Provision the governed seam: a Foundry Skill + Toolbox.

Registers the repo-local agentskills.io source file `skills/pathforward/SKILL.md` as the versioned
Foundry Skill named `pathforward`, then attaches it to `pathforward-toolbox` alongside the governed
Azure AI Search tool. The toolbox MCP endpoint is the intended load-bearing skill/tool seam for the
Orchestrator path; direct-attached tools remain fallback/test seams.

Source-verified against azure-ai-projects 2.2.0 (see .agents/decisions/003-foundry-toolbox-
governance.md): beta.skills.create / beta.toolboxes.create_version, with the preview header
(Foundry-Features: {Skills,Toolboxes}=V1Preview) auto-injected by the SDK.

    python scripts/build_toolbox.py --dry-run                 # construct objects offline, NO Azure
    python scripts/build_toolbox.py                           # live: create skill + toolbox v1 (no toolbox RAI)
    python scripts/build_toolbox.py --rai-policy pathforward-rai   # explicitly attach an EXISTING toolbox RAI policy
    python scripts/build_toolbox.py --recreate               # delete skill+toolbox first, rebuild clean

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

from pathforward.config import load_settings   # noqa: E402
from pathforward.skills import read_skill_file  # noqa: E402

SKILL_NAME = "pathforward"
TOOLBOX_NAME = "pathforward-toolbox"
CONNECTION = "pathforward-search"
SKILL_PATH = os.path.join(_ROOT, "skills", "pathforward", "SKILL.md")


def build_skill_content():
    from azure.ai.projects.models import SkillInlineContent
    skill = read_skill_file(SKILL_PATH)
    return SkillInlineContent(
        description=skill.description,
        instructions=skill.instructions,
        compatibility=skill.compatibility or None,
        metadata={
            "domain": "workforce-development",
            "ontology": "certgap-edge-driven",
            "source_path": "skills/pathforward/SKILL.md",
            **(skill.metadata or {}),
        },
    )


def build_search_tool(conn_id: str, index_name: str):
    """The toolbox's azure_ai_search tool — identical ctor shape to the proven GA foundry.py path."""
    from azure.ai.projects.models import (
        AISearchIndexResource, AzureAISearchQueryType, AzureAISearchTool, AzureAISearchToolResource,
    )
    return AzureAISearchTool(azure_ai_search=AzureAISearchToolResource(indexes=[
        AISearchIndexResource(project_connection_id=conn_id, index_name=index_name,
                              query_type=AzureAISearchQueryType.SEMANTIC)]))


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


def main() -> int:
    ap = argparse.ArgumentParser(description="Provision the PathForward Foundry Skill + Toolbox.")
    ap.add_argument("--dry-run", action="store_true",
                    help="construct skill/tool/toolbox objects offline; make NO Azure calls")
    ap.add_argument("--recreate", action="store_true",
                    help="delete the existing skill + toolbox first, then rebuild clean")
    ap.add_argument("--rai-policy", default=None,
                    help="name of an EXISTING toolbox-valid RAI policy to declare on the toolbox "
                         "version (default: omit toolbox-level RAI)")
    args = ap.parse_args()

    settings = load_settings(os.path.join(_ROOT, ".env"))
    endpoint = (settings.foundry_project_endpoint or "").strip()
    index_name = (settings.search_index or "").strip()
    rai_policy = args.rai_policy or None

    # Construct everything offline first so a model/schema error surfaces even in --dry-run.
    skill_file = read_skill_file(SKILL_PATH)
    if skill_file.name != SKILL_NAME:
        print(f"FAIL: {SKILL_PATH} declares name={skill_file.name!r}; expected {SKILL_NAME!r}")
        return 1
    skill_content = build_skill_content()
    placeholder_tool = build_search_tool(conn_id="<resolved-at-runtime>", index_name=index_name)
    policies = build_policies(rai_policy)
    from azure.ai.projects.models import ToolboxSkillReference
    skill_ref = ToolboxSkillReference(name=SKILL_NAME)  # version filled after the skill is created
    print(f"constructed: skill '{SKILL_NAME}' from skills/pathforward/SKILL.md "
          f"+ azure_ai_search tool over index '{index_name}' + skill_ref "
          f"+ policies={'RAI:' + rai_policy if policies else 'none'}")
    _ = (skill_content, placeholder_tool, skill_ref)

    if args.dry_run:
        print("DRY RUN: objects construct cleanly; no Azure calls made.")
        return 0

    if not endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT is blank in .env (required for a live build)")
        return 1

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

    try:
        conn_id = project.connections.get(CONNECTION).id
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: could not resolve connection '{CONNECTION}': {type(exc).__name__}: {exc}")
        return 1
    print(f"resolved connection '{CONNECTION}' -> {conn_id}")

    if args.recreate:
        for label, fn in (("toolbox", lambda: project.beta.toolboxes.delete(TOOLBOX_NAME)),
                          ("skill", lambda: project.beta.skills.delete(SKILL_NAME))):
            try:
                fn()
                print(f"deleted existing {label} (recreate)")
            except Exception as exc:  # noqa: BLE001
                print(f"(no existing {label} to delete: {type(exc).__name__})")

    # 1) the 'pathforward' Skill (default=True -> this version is the one a reference resolves to)
    try:
        skill = project.beta.skills.create(name=SKILL_NAME, inline_content=skill_content, default=True)
    except Exception as exc:  # noqa: BLE001
        _rbac_hint(exc)
        return 1
    print(f"SKILL  '{skill.name}' v{skill.version} id={skill.skill_id}")

    # 2) the toolbox version: GA search tool + the skill reference (+ optional RAI policy)
    tool = build_search_tool(conn_id=conn_id, index_name=index_name)
    skills = [ToolboxSkillReference(name=SKILL_NAME, version=skill.version)]
    try:
        tb = project.beta.toolboxes.create_version(
            TOOLBOX_NAME,
            tools=[tool],
            description="PathForward Phase 2 governed seam: agentic search + the pathforward skill.",
            metadata={"phase": "2", "search_index": index_name},
            skills=skills,
            policies=policies,
        )
    except Exception as exc:  # noqa: BLE001
        _rbac_hint(exc)
        return 1
    rai = (tb.policies.rai_config.rai_policy_name if tb.policies and tb.policies.rai_config else "none")
    print(f"TOOLBOX '{tb.name}' v{tb.version} id={tb.id} tools={len(tb.tools)} "
          f"skills={len(tb.skills or [])} rai={rai}")

    # 2b) promote the just-built version to default (build -> promote; also exercises versioning)
    try:
        project.beta.toolboxes.update(TOOLBOX_NAME, default_version=tb.version)
        print(f"promoted default_version -> v{tb.version}")
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: could not promote default_version: {type(exc).__name__}: {exc}")

    # 3) prove the central registry sees them
    tbs = [f"{t.name}" for t in project.beta.toolboxes.list()]
    skl = [f"{s.name}" for s in project.beta.skills.list()]
    print(f"registry toolboxes: {tbs}")
    print(f"registry skills:    {skl}")
    if TOOLBOX_NAME not in tbs or SKILL_NAME not in skl:
        print("FAIL: created artifact not visible in the registry listing")
        return 1
    print("done. governed seam registered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
