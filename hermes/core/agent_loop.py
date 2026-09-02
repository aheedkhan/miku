"""The core agent loop — used identically by the main REPL agent and every sub-agent.
A sub-agent is just a fresh Agent instance with a restricted ToolRegistry and a one-shot
scoped prompt; only its run() return value (final text) becomes a single message in the
parent's history, so its internal turns/tool calls/thinking never enter the parent's
context window. See hermes/agents/subagent.py for the spawn helper."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from hermes.core.concurrency import InferenceGate
from hermes.core.context_manager import ContextManager
from hermes.core.llm_client import OllamaClient
from hermes.core.message import Message
from hermes.core.tool_strategy import ToolCallStrategy
from hermes.tools.registry import ToolRegistry

MAX_TURNS_MESSAGE = "[Hermes] Hit max_turns without a final answer — stopping to avoid a runaway tool-calling loop."


@dataclass
class StreamEvent:
    type: str  # "tool_call" | "tool_result" | "final" | "compacted" | "error"
    data: dict[str, Any]


EventSink = Callable[[StreamEvent], None]


class Agent:
    def __init__(
        self,
        *,
        llm: OllamaClient,
        model: str,
        num_ctx: int,
        system_prompt: str,
        tools: ToolRegistry,
        strategy: ToolCallStrategy,
        gate: InferenceGate,
        context: ContextManager | None = None,
        summarizer_model: str | None = None,
        summarizer_num_ctx: int = 8192,
        max_turns: int = 25,
        on_event: EventSink | None = None,
    ):
        self.llm = llm
        self.model = model
        self.num_ctx = num_ctx
        self.tools = tools
        self.strategy = strategy
        self.gate = gate
        self.context = context
        self.summarizer_model = summarizer_model or model
        self.summarizer_num_ctx = summarizer_num_ctx
        self.max_turns = max_turns
        self.on_event = on_event or (lambda _event: None)
        self.messages: list[Message] = [Message(role="system", content=system_prompt)]
        self._last_prompt_eval_count = 0

    async def _maybe_compact(self) -> None:
        if self.context and self.context.should_compact(self._last_prompt_eval_count, self.messages):
            self.messages = await self.context.compact(
                self.messages, self.llm, self.summarizer_model, self.summarizer_num_ctx
            )
            self.on_event(StreamEvent("compacted", {"message_count": len(self.messages)}))

    async def run(self, user_input: str) -> str:
        """Non-streaming: runs the full tool-calling loop, returns only the final text."""
        self.messages.append(Message(role="user", content=user_input))
        await self._maybe_compact()

        schemas = self.tools.as_schemas()
        for _ in range(self.max_turns):
            async with self.gate.acquire_for_model(self.model):
                result = await self.strategy.call(
                    self.llm, self.model, self.messages, schemas, num_ctx=self.num_ctx
                )
            self._last_prompt_eval_count = result.prompt_eval_count

            if not result.message.tool_calls and not result.message.content.strip():
                # Rare sampling flake: model returned a genuinely empty final answer.
                # Retry once without appending the empty turn to history before giving up.
                async with self.gate.acquire_for_model(self.model):
                    result = await self.strategy.call(
                        self.llm, self.model, self.messages, schemas, num_ctx=self.num_ctx
                    )
                self._last_prompt_eval_count = result.prompt_eval_count

            self.messages.append(result.message)

            if not result.message.tool_calls:
                return result.message.content or "(empty response from the model — try rephrasing)"

            for call in result.message.tool_calls:
                self.on_event(StreamEvent("tool_call", {"name": call.name, "arguments": call.arguments}))
                tool_result = await self.tools.dispatch(call)
                self.on_event(
                    StreamEvent(
                        "tool_result",
                        {"name": call.name, "ok": tool_result.ok, "display": tool_result.for_display()},
                    )
                )
                self.messages.append(Message.tool_result(call, tool_result.content))

        return MAX_TURNS_MESSAGE

    async def stream_run(self, user_input: str) -> AsyncIterator[StreamEvent]:
        """Same loop as run(), yielding events for the REPL to render live instead of a
        callback. Tool-calling turns still go through strategy.call non-streamed — most
        tool-calling models don't stream partial tool_calls usefully — only genuinely
        final, tool-free answers stream token-by-token via the underlying stream_chat."""
        self.messages.append(Message(role="user", content=user_input))
        if self.context and self.context.should_compact(self._last_prompt_eval_count, self.messages):
            self.messages = await self.context.compact(
                self.messages, self.llm, self.summarizer_model, self.summarizer_num_ctx
            )
            yield StreamEvent("compacted", {"message_count": len(self.messages)})

        schemas = self.tools.as_schemas()
        for _ in range(self.max_turns):
            async with self.gate.acquire_for_model(self.model):
                result = await self.strategy.call(
                    self.llm, self.model, self.messages, schemas, num_ctx=self.num_ctx
                )
            self._last_prompt_eval_count = result.prompt_eval_count

            if not result.message.tool_calls and not result.message.content.strip():
                # Rare sampling flake: model returned a genuinely empty final answer.
                # Retry once without appending the empty turn to history before giving up.
                async with self.gate.acquire_for_model(self.model):
                    result = await self.strategy.call(
                        self.llm, self.model, self.messages, schemas, num_ctx=self.num_ctx
                    )
                self._last_prompt_eval_count = result.prompt_eval_count

            self.messages.append(result.message)

            if not result.message.tool_calls:
                content = result.message.content or "(empty response from the model — try rephrasing)"
                yield StreamEvent("final", {"content": content, "thinking": result.message.thinking})
                return

            for call in result.message.tool_calls:
                yield StreamEvent("tool_call", {"name": call.name, "arguments": call.arguments})
                tool_result = await self.tools.dispatch(call)
                yield StreamEvent(
                    "tool_result",
                    {"name": call.name, "ok": tool_result.ok, "display": tool_result.for_display()},
                )
                self.messages.append(Message.tool_result(call, tool_result.content))

        yield StreamEvent("error", {"message": MAX_TURNS_MESSAGE})
