"""The Tool contract every tool module builds against. Deliberately a plain dataclass
wrapping an async callable — not a Protocol/ABC — so tool modules just write ordinary
async functions and wrap them, no subclassing required."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema: {"type": "object", "properties": {...}, "required": [...]}


@dataclass
class ToolResult:
    ok: bool
    content: str  # sent back to the model verbatim as the tool's return value
    display: str | None = None  # human-facing summary for the REPL; defaults to content
    error: str | None = None

    def for_display(self) -> str:
        return self.display if self.display is not None else self.content

    @classmethod
    def success(cls, content: str, display: str | None = None) -> "ToolResult":
        return cls(ok=True, content=content, display=display)

    @classmethod
    def failure(cls, error: str, content: str | None = None) -> "ToolResult":
        return cls(ok=False, content=content or f"Error: {error}", error=error)


@dataclass
class Tool:
    schema: ToolSchema
    handler: Callable[..., Awaitable[ToolResult]]

    async def __call__(self, **kwargs: Any) -> ToolResult:
        return await self.handler(**kwargs)
