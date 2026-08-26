"""Tool-calling strategies. One ToolSchema list drives both native tools=[...] payloads and
the ReAct-prompt fallback's rendered instructions — no per-model special-casing needed.

Verified live (Aug 2026) against every locally pulled model, including the huihui_ai
abliterated variants: native Ollama tool-calling works today. AutoToolStrategy still tries
native first and falls back to parsing a ReAct-style JSON block, as a safety net against
untested cases (parallel tool calls, a future silent template change when a community
`huihui_ai/*` tag gets re-pulled) — not because native calling is currently broken.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from hermes.core.llm_client import ChatResult, OllamaClient
from hermes.core.message import Message, ToolCall
from hermes.tools.base import ToolSchema


def schema_to_ollama_tool(schema: ToolSchema) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": schema.name,
            "description": schema.description,
            "parameters": schema.parameters,
        },
    }


def render_react_instructions(schemas: list[ToolSchema]) -> str:
    lines = [
        "You can call a tool by responding with EXACTLY ONE fenced block in this form, "
        "and nothing else in that response:",
        "```tool_call",
        '{"name": "<tool name>", "arguments": {...}}',
        "```",
        "If no tool call is needed, just answer normally in plain text instead.",
        "Available tools:",
    ]
    for s in schemas:
        lines.append(f"- {s.name}: {s.description} | parameters: {json.dumps(s.parameters)}")
    return "\n".join(lines)


_TOOL_CALL_RE = re.compile(r"```tool_call\s*(\{.*?\})\s*```", re.DOTALL)


def parse_react_tool_call(content: str, call_index: int = 0) -> ToolCall | None:
    match = _TOOL_CALL_RE.search(content or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        return ToolCall(id=f"react_{call_index}", name=data["name"], arguments=data.get("arguments") or {})
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def _looks_like_failed_tool_attempt(content: str, schemas: list[ToolSchema]) -> bool:
    if not content:
        return False
    lowered = content.lower()
    if "```tool_call" in lowered or '"arguments"' in lowered:
        return True
    return any(s.name.lower() in lowered and "{" in content for s in schemas)


class ToolCallStrategy(ABC):
    @abstractmethod
    async def call(
        self,
        client: OllamaClient,
        model: str,
        messages: list[Message],
        schemas: list[ToolSchema],
        *,
        num_ctx: int,
    ) -> ChatResult:
        """One chat turn; result.message.tool_calls is populated whether that came from
        native tool-calling or a parsed ReAct block."""


class NativeToolStrategy(ToolCallStrategy):
    async def call(self, client, model, messages, schemas, *, num_ctx):
        tools = [schema_to_ollama_tool(s) for s in schemas] if schemas else None
        return await client.chat(model, messages, num_ctx=num_ctx, tools=tools)


class ReActPromptStrategy(ToolCallStrategy):
    async def call(self, client, model, messages, schemas, *, num_ctx):
        sent = messages
        if schemas:
            sent = [Message(role="system", content=render_react_instructions(schemas)), *messages]
        result = await client.chat(model, sent, num_ctx=num_ctx)
        if not result.message.tool_calls:
            call = parse_react_tool_call(result.message.content)
            if call:
                result.message.content = _TOOL_CALL_RE.sub("", result.message.content).strip()
                result.message.tool_calls = [call]
        return result


class AutoToolStrategy(ToolCallStrategy):
    def __init__(self, cache_path: Path | None = None):
        self._native = NativeToolStrategy()
        self._react = ReActPromptStrategy()
        self._cache_path = cache_path
        self._verdicts: dict[str, bool] = self._load_cache()

    def _load_cache(self) -> dict[str, bool]:
        if self._cache_path and self._cache_path.is_file():
            try:
                return json.loads(self._cache_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_cache(self) -> None:
        if not self._cache_path:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(self._verdicts))
        except OSError:
            pass

    async def call(self, client, model, messages, schemas, *, num_ctx):
        if not schemas:
            return await client.chat(model, messages, num_ctx=num_ctx)

        if not self._verdicts.get(model, True):
            return await self._react.call(client, model, messages, schemas, num_ctx=num_ctx)

        result = await self._native.call(client, model, messages, schemas, num_ctx=num_ctx)
        if result.message.tool_calls or not _looks_like_failed_tool_attempt(result.message.content, schemas):
            return result

        # This turn looks like a failed native tool-call attempt — try a ReAct-style parse
        # of the same content before giving up, and remember to skip native calling for
        # this model from now on.
        call = parse_react_tool_call(result.message.content)
        if call:
            result.message.tool_calls = [call]
            self._verdicts[model] = False
            self._save_cache()
        return result
