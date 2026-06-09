"""Provision the governed seam: a Foundry Skill + Toolbox.

Registers the repo-local agentskills.io source files under `skills/*/SKILL.md` as versioned Foundry
Skills, then attaches them to `pathforward-toolbox` alongside the governed Azure AI Search tool. The
toolbox MCP endpoint is the intended load-bearing skill/tool seam for the Orchestrator and
specialist-agent paths; direct-attached tools remain fallback/test seams.

Source-verified against azure-ai-projects 2.2.0 (see .agents/decisions/003-foundry-toolbox-
governance.md): beta.skills.create / beta.toolboxes.create_version, with the preview header
(Foundry-Features: {Skills,Toolboxes}=V1Preview) auto-injected by the SDK.

    python scripts/build_toolbox.py --dry-run                 # validate local Skill files, NO Azure
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

TOOLBOX_NAME = "pathforward-toolbox"
CONNECTION = "pathforward-search"
SKILLS = (
    ("pathforward", os.path.join(_ROOT, "skills", "pathforward", "SKILL.md")),
    ("pathforward-curate", os.path.join(_ROOT, "skills", "pathforward-curate", "SKILL.md")),
    ("pathforward-assess", os.path.join(_ROOT, "skills", "pathforward-assess", "SKILL.md")),
    ("pathforward-plan", os.path.join(_ROOT, "skills", "pathforward-plan", "SKILL.md")),
    ("pathforward-insights", os.path.join(_ROOT, "skills", "pathforward-insights", "SKILL.md")),
)


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

    # Validate local Skill files first so --dry-run works on machines without Azure SDK packages.
    skill_files = []
    for expected_name, path in SKILLS:
        skill_file = read_skill_file(path)
        if skill_file.name != expected_name:
            print(f"FAIL: {path} declares name={skill_file.name!r}; expected {expected_name!r}")
            return 1
        skill_files.append(skill_file)
    skill_names = [s.name for s in skill_files]
    print(f"validated: skills {skill_names} "
          f"+ azure_ai_search tool over index '{index_name}' "
          f"+ policies={'RAI:' + rai_policy if rai_policy else 'none'}")

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
    skill_contents = {name: build_skill_content(path) for name, path in SKILLS}
    placeholder_tool = build_search_tool(conn_id="<resolved-at-runtime>", index_name=index_name)
    policies = build_policies(rai_policy)
    skill_refs = [ToolboxSkillReference(name=name) for name, _ in SKILLS]
    _ = (placeholder_tool, skill_refs)

    project = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

    try:
        conn_id = project.connections.get(CONNECTION).id
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: could not resolve connection '{CONNECTION}': {type(exc).__name__}: {exc}")
        return 1
    print(f"resolved connection '{CONNECTION}' -> {conn_id}")

    if args.recreate:
        delete_ops = [("toolbox", lambda: project.beta.toolboxes.delete(TOOLBOX_NAME))]
        delete_ops += [(f"skill {name}", lambda n=name: project.beta.skills.delete(n))
                       for name, _ in SKILLS]
        for label, fn in delete_ops:
            try:
                fn()
                print(f"deleted existing {label} (recreate)")
            except Exception as exc:  # noqa: BLE001
                print(f"(no existing {label} to delete: {type(exc).__name__})")

    # 1) each Skill (default=True -> this version is the one a reference resolves to)
    created_skills = []
    for name, _ in SKILLS:
        try:
            skill = project.beta.skills.create(name=name, inline_content=skill_contents[name],
                                               default=True)
        except Exception as exc:  # noqa: BLE001
            _rbac_hint(exc)
            return 1
        created_skills.append(skill)
        print(f"SKILL  '{skill.name}' v{skill.version} id={skill.skill_id}")

    # 2) the toolbox version: GA search tool + the skill reference (+ optional RAI policy)
    tool = build_search_tool(conn_id=conn_id, index_name=index_name)
    created_by_name = {skill.name: skill for skill in created_skills}
    skills = [ToolboxSkillReference(name=name, version=created_by_name[name].version)
              for name, _ in SKILLS]
    try:
        tb = project.beta.toolboxes.create_version(
            TOOLBOX_NAME,
            tools=[tool],
            description="PathForward governed seam: agentic search + PathForward skill family.",
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
    missing_skills = [name for name, _ in SKILLS if name not in skl]
    if TOOLBOX_NAME not in tbs or missing_skills:
        print("FAIL: created artifact not visible in the registry listing")
        if missing_skills:
            print(f"missing skills: {missing_skills}")
        return 1
    print("done. governed seam registered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
