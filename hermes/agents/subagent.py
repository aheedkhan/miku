"""Spawns a fresh, role-scoped sub-agent for one task and returns only its final text.

Used by hermes/tools/subagent_tool.py (the spawn_subagent tool the main agent calls) but
kept independent of it so other integration code (e.g. a slash command) can call it
directly too. See hermes/core/agent_loop.py's module docstring for why only the return
string — never the sub-agent's own message history or tool calls — ever reaches the
caller's context.
"""

from __future__ import annotations

from hermes.agents.roles import GENERAL_PRESET, ROLE_PRESETS
from hermes.config import HermesConfig
from hermes.core.agent_loop import Agent
from hermes.core.concurrency import InferenceGate
from hermes.core.context_manager import ContextManager
from hermes.core.llm_client import OllamaClient
from hermes.core.tool_strategy import AutoToolStrategy
from hermes.persona.loader import load_system_prompt
from hermes.tools.registry import ToolRegistry


async def spawn_subagent(
    role: str,
    task: str,
    *,
    llm: OllamaClient,
    tools: ToolRegistry,
    config: HermesConfig,
    gate: InferenceGate,
    context_cls: type[ContextManager] | None = None,
    extra_context: str | None = None,
) -> str:
    """Run `task` through a fresh, role-restricted sub-agent and return only its final
    answer. An unrecognized `role` falls back to the "general" preset (full tool registry,
    default model) rather than raising — role names may originate from a small local model's
    tool-call arguments, and a typo/hallucinated role shouldn't blow up the whole turn.

    The sub-agent shares the parent's InferenceGate (`gate`) so total concurrent heavy LLM
    calls across the whole process — main agent plus every sub-agent — stay bounded by one
    limit; it must never construct its own gate. It gets its own ToolRegistry subset, its
    own ContextManager sized to its own model's num_ctx, and its own AutoToolStrategy
    instance backed by the same on-disk cache path as everything else in the process, so
    per-model native/ReAct verdicts learned by one agent are reused by all.
    """
    preset = ROLE_PRESETS.get(role, GENERAL_PRESET)

    model_profile = config.model(preset["model_role"])

    tool_names = preset["tool_names"]
    scoped_tools = tools if tool_names is None else tools.subset(tool_names)

    suffix_parts = [preset["system_prompt_suffix"]]
    if extra_context:
        suffix_parts.append(extra_context)
    system_prompt = load_system_prompt(extra_context="\n\n---\n\n".join(suffix_parts))

    context_manager_cls = context_cls or ContextManager
    context = context_manager_cls(num_ctx=model_profile.num_ctx)

    strategy = AutoToolStrategy(cache_path=config.tool_strategy_cache_path)

    agent = Agent(
        llm=llm,
        model=model_profile.name,
        num_ctx=model_profile.num_ctx,
        system_prompt=system_prompt,
        tools=scoped_tools,
        strategy=strategy,
        gate=gate,
        context=context,
    )

    return await agent.run(task)
