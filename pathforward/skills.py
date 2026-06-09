"""PathForward skill-file helpers.

Foundry Skills use the agentskills.io `SKILL.md` shape: YAML front matter plus Markdown body. Keep
the parser deliberately small so the offline core does not need PyYAML.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillFile:
    name: str
    description: str
    instructions: str
    compatibility: str = ""
    metadata: dict[str, str] | None = None


def _parse_front_matter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---\n"):
        raise ValueError("skill file must start with YAML front matter")
    end = raw.find("\n---", 4)
    if end == -1:
        raise ValueError("skill file front matter is not closed")
    front = raw[4:end].strip()
    body = raw[end + len("\n---"):].lstrip("\r\n")
    meta: dict[str, str] = {}
    for line in front.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"unsupported front matter line: {line!r}")
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, body


def read_skill_file(path: str | Path) -> SkillFile:
    raw = Path(path).read_text(encoding="utf-8")
    meta, body = _parse_front_matter(raw)
    name = meta.get("name", "").strip()
    description = meta.get("description", "").strip()
    if not name:
        raise ValueError("skill file missing required `name`")
    if not description:
        raise ValueError("skill file missing required `description`")
    if not body.strip():
        raise ValueError("skill file body is empty")
    extra = {k: v for k, v in meta.items() if k not in {"name", "description", "compatibility"}}
    return SkillFile(name=name, description=description, instructions=body.strip(),
                     compatibility=meta.get("compatibility", "").strip(),
                     metadata=extra or None)
