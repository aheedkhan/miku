"""The spawn_subagent tool: lets the main agent delegate a self-contained side task to a
fresh, scoped sub-agent and get back only its final answer, keeping its own tool calls and
reasoning out of the caller's context window.

Different `build_tools` signature than every other tool module by design (per the task
spec): this one takes a pre-bound `spawn_fn` rather than a HermesConfig, because spawning a
sub-agent needs live objects (an OllamaClient, the process's live ToolRegistry, the shared
InferenceGate) that a plain config can't supply. The wiring that partially-applies
hermes.agents.subagent.spawn_subagent's other keyword args down to this narrow
(role, task, extra_context) -> str shape happens in integration code elsewhere, not here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from hermes.agents.roles import ROLE_PRESETS
from hermes.tools.base import Tool, ToolResult, ToolSchema

SpawnFn = Callable[..., Awaitable[str]]


def build_tools(spawn_fn: SpawnFn) -> list[Tool]:
    role_names = ", ".join(sorted(ROLE_PRESETS))

    async def _spawn_subagent(role: str, task: str, extra_context: str | None = None) -> ToolResult:
        result = await spawn_fn(role, task, extra_context=extra_context)
        return ToolResult.success(result)

    schema = ToolSchema(
        name="spawn_subagent",
        description=(
            "Delegate a self-contained task to a fresh, scoped sub-agent and get back only its "
            "final answer — the sub-agent's own tool calls and intermediate reasoning never "
            "enter your context. Use this to keep your context window clean when a task is a "
            f"well-defined side quest with its own tool needs. Available roles: {role_names}. "
            "An unrecognized role falls back to a general-purpose sub-agent with the full tool "
            "set and the default model."
        ),
        parameters={
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "description": f"Which sub-agent role to spawn. One of: {role_names}.",
                },
                "task": {
                    "type": "string",
                    "description": "The self-contained task or question for the sub-agent to "
                    "complete. Should include everything it needs — it starts with no memory "
                    "of this conversation beyond what you put here and in extra_context.",
                },
                "extra_context": {
                    "type": "string",
                    "description": "Optional extra context to hand the sub-agent (e.g. relevant "
                    "findings so far, file paths, constraints). Omit if not needed.",
                },
            },
            "required": ["role", "task"],
        },
    )

    return [Tool(schema=schema, handler=_spawn_subagent)]
