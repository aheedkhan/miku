"""Discovers markdown Skills -- reusable playbooks for a task or domain, one directory per
skill under `skills_dir`, each holding a `SKILL.md` (YAML frontmatter with name/description,
then plain markdown instructions). Same shape Claude Code itself uses for its own skills.

Only name+description get put in front of the model at all times (see cli.py's system-prompt
wiring) -- cheap regardless of how many skills exist. A skill's full body is only read into
context when actually selected, via the `use_skill` tool (hermes/tools/skill_tool.py) or the
`/skill <name>` REPL command.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    body: str


def _parse_skill_md(path: Path) -> Skill | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    _, sep1, rest = text.partition("---")
    frontmatter_raw, sep2, body = rest.partition("---")
    if not sep1 or not sep2:
        return None
    meta = yaml.safe_load(frontmatter_raw) or {}
    name = meta.get("name") or path.parent.name
    return Skill(name=name, description=meta.get("description", ""), path=path, body=body.strip())


def discover_skills(skills_dir: Path) -> dict[str, Skill]:
    """Returns {skill_name: Skill}, sorted by name, skipping any SKILL.md that fails to parse."""
    skills: dict[str, Skill] = {}
    if not skills_dir.is_dir():
        return skills
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            skill = _parse_skill_md(skill_md)
        except (OSError, yaml.YAMLError):
            continue
        if skill is not None:
            skills[skill.name] = skill
    return skills


def format_skill_index(skills: dict[str, Skill]) -> str:
    """One line per skill, name + description -- what stays loaded in the system prompt."""
    return "\n".join(f"- {s.name}: {s.description}" for s in skills.values())
