from __future__ import annotations

from collections.abc import Iterable

from hermes.core.message import ToolCall
from hermes.tools.base import Tool, ToolResult, ToolSchema


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        if tools:
            self.register_all(tools)

    def register(self, tool: Tool) -> None:
        self._tools[tool.schema.name] = tool

    def register_all(self, tools: Iterable[Tool]) -> None:
        for tool in tools:
            self.register(tool)

    def names(self) -> list[str]:
        return list(self._tools)

    def subset(self, names: list[str]) -> "ToolRegistry":
        """Used to build a restricted tool set for a sub-agent role. Unknown names are skipped
        rather than raising, since role presets are static and tool availability can vary
        (e.g. android_tool only registers actions for binaries that are actually installed)."""
        return ToolRegistry(t for name, t in self._tools.items() if name in names)

    def as_schemas(self) -> list[ToolSchema]:
        return [t.schema for t in self._tools.values()]

    async def dispatch(self, call: ToolCall) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult.failure(f"unknown_tool:{call.name}", f"No such tool: {call.name}")
        try:
            return await tool(**call.arguments)
        except TypeError as e:
            return ToolResult.failure("bad_arguments", f"{call.name} got bad arguments: {e}")
        except Exception as e:  # tool implementations own their own error handling; this is a backstop
            return ToolResult.failure(type(e).__name__, f"{call.name} raised {type(e).__name__}: {e}")

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
