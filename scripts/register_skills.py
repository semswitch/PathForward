"""Register the PathForward Foundry Skills (portal-visible, baked into agents at provision time).

Registers the repo-local agentskills.io source files under `skills/*/SKILL.md` as versioned Foundry
Skills so each `/pathforward*` Skill is visible in the Foundry portal and satisfies the architecture
contract (a Skill must be registered in Foundry — local-only Markdown is not approved).

Skills are NOT delivered to the agents through toolboxes. PathForward declarative Prompt Agents
cannot consume toolbox Skill resources at runtime, so `provision_foundry_specialist_agents.py`
injects each Skill body directly into the agent's instructions at version-create time and attaches
the tool surface directly to the agent definition. This script's only job is the portal-visible
Skills registry.

Source-verified against azure-ai-projects 2.2.0 (see .agents/decisions/003-foundry-toolbox-
governance.md): beta.skills.create, with the preview header (Foundry-Features: Skills=V1Preview)
auto-injected by the SDK. `skills.create` is additive — each run creates a new default version.

    python scripts/register_skills.py --dry-run
    python scripts/register_skills.py
    python scripts/register_skills.py --recreate
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.config import load_settings  # noqa: E402
from pathforward.skills import read_skill_file  # noqa: E402

SKILL_PATHS = {
    "pathforward": os.path.join(_ROOT, "skills", "pathforward", "SKILL.md"),
    "pathforward-curate": os.path.join(_ROOT, "skills", "pathforward-curate", "SKILL.md"),
    "pathforward-assess": os.path.join(_ROOT, "skills", "pathforward-assess", "SKILL.md"),
    "pathforward-critic": os.path.join(_ROOT, "skills", "pathforward-critic", "SKILL.md"),
    "pathforward-plan": os.path.join(_ROOT, "skills", "pathforward-plan", "SKILL.md"),
    "pathforward-insights": os.path.join(_ROOT, "skills", "pathforward-insights", "SKILL.md"),
}


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


def _rbac_hint(exc: Exception) -> None:
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    print(f"FAIL: {type(exc).__name__}: {exc}")
    if status in (401, 403):
        print("  -> looks like an RBAC denial. The identity may need the 'Foundry User' role on the "
              "project (in addition to Foundry Project Manager). Surface this scope to the user; do "
              "NOT self-assign roles (auto-mode classifier blocks it).")


def main() -> int:
    ap = argparse.ArgumentParser(description="Register PathForward Foundry Skills (no toolboxes).")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate the local Skill files offline; make NO Azure calls")
    ap.add_argument("--recreate", action="store_true",
                    help="delete the existing skills first, then re-register them clean")
    args = ap.parse_args()

    settings = load_settings(os.path.join(_ROOT, ".env"))
    endpoint = (settings.foundry_project_endpoint or "").strip()

    # Validate local Skill files first so --dry-run works on machines without the Azure SDK.
    for expected_name, path in SKILL_PATHS.items():
        skill_file = read_skill_file(path)
        if skill_file.name != expected_name:
            print(f"FAIL: {path} declares name={skill_file.name!r}; expected {expected_name!r}")
            return 1
    skill_names = list(SKILL_PATHS)
    print(f"validated: skills {skill_names}")

    if args.dry_run:
        print("DRY RUN: local Skill files validate cleanly; no Azure SDK imports or calls made.")
        return 0

    if not endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT is blank in .env (required for a live register)")
        return 1

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    # Construct SDK objects only for a live register, preserving offline portability while still
    # failing fast on SDK/model-shape errors before making create calls.
    skill_contents = {name: build_skill_content(path) for name, path in SKILL_PATHS.items()}
    project = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

    if args.recreate:
        for name in SKILL_PATHS:
            try:
                project.beta.skills.delete(name)
                print(f"deleted existing skill {name} (recreate)")
            except Exception as exc:  # noqa: BLE001
                print(f"(no existing skill {name} to delete: {type(exc).__name__})")

    # Register each Skill (default=True -> this version is the one an agent provision reads/bakes).
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

    # Prove the central registry sees them (portal visibility).
    skl = [s.name for s in project.beta.skills.list()]
    print(f"registry skills: {skl}")
    missing_skills = [name for name in SKILL_PATHS if name not in skl]
    if missing_skills:
        print(f"FAIL: created skill not visible in the registry listing: {missing_skills}")
        return 1
    print("done. PathForward Skills registered and portal-visible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
