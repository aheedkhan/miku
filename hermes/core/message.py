"""Provider-agnostic message/tool-call types shared by the LLM client, tool strategies,
the agent loop, and every tool module. Keep this file dependency-free."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # set on role == "tool" replies
    name: str | None = None  # tool name, set on role == "tool" replies
    thinking: str | None = None  # optional reasoning trace (display-only, not required by the API)

    def to_ollama(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = [
                {"function": {"name": tc.name, "arguments": tc.arguments}} for tc in self.tool_calls
            ]
        if self.role == "tool" and self.tool_call_id:
            # Verified against live Ollama 0.32.13: {"role": "tool", "tool_call_id": ..., "content": ...}
            # round-trips correctly. Not sending an extra "tool_name" field — untested, and the
            # server may reject unrecognized fields; tool_call_id alone is sufficient for matching.
            msg["tool_call_id"] = self.tool_call_id
        return msg

    @classmethod
    def tool_result(cls, tool_call: ToolCall, content: str) -> "Message":
        return cls(role="tool", content=content, tool_call_id=tool_call.id, name=tool_call.name)
