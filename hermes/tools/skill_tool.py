"""The use_skill tool: lets the agent pull a Skill's full playbook into context on demand.
Skill names + one-line descriptions are already in the system prompt (see cli.py), so the
model knows what exists without spending any context on bodies it never ends up using --
same cheap-index / on-demand-body split Claude Code itself uses for its own skills.
"""

from __future__ import annotations

from hermes.config import HermesConfig
from hermes.skills import discover_skills
from hermes.tools.base import Tool, ToolResult, ToolSchema


def build_tools(config: HermesConfig) -> list[Tool]:
    skills = discover_skills(config.skills_dir)

    async def _use_skill(name: str) -> ToolResult:
        skill = skills.get(name)
        if skill is None:
            available = ", ".join(sorted(skills)) or "(none found)"
            return ToolResult.failure(f"No skill named {name!r}. Available: {available}")
        return ToolResult.success(skill.body, display=f"loaded skill '{name}'")

    schema = ToolSchema(
        name="use_skill",
        description=(
            "Load the full playbook for one of your available skills (see the skill index in "
            "your system prompt for names + descriptions) into context. Use this before "
            "starting a task one of those skills covers, instead of guessing the approach."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Exact skill name from the index."},
            },
            "required": ["name"],
        },
    )
    return [Tool(schema=schema, handler=_use_skill)]
