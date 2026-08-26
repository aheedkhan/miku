"""Context-window compaction. Uses Ollama's own exact prompt_eval_count from the previous
call as the token baseline (rather than reinventing a tokenizer), plus a coarse chars/4
estimate for anything appended since. num_ctx is deliberately NOT defaulted to a model's
advertised maximum — prompt-eval cost scales with it on CPU-bound hardware, so start
conservative (see config.example.yaml) and raise it once you've benchmarked tokens/sec."""

from __future__ import annotations

from dataclasses import dataclass

from hermes.core.llm_client import OllamaClient
from hermes.core.message import Message


@dataclass
class ContextManager:
    num_ctx: int
    reserve_for_output: int = 1024
    compact_threshold: float = 0.75
    keep_recent: int = 6  # most recent non-system messages kept verbatim through compaction

    def _estimate_tokens(self, messages: list[Message]) -> int:
        return sum(len(m.content) for m in messages) // 4

    def should_compact(self, last_prompt_eval_count: int, messages: list[Message]) -> bool:
        budget = self.num_ctx - self.reserve_for_output
        estimate = last_prompt_eval_count + self._estimate_tokens(messages[-2:])
        return estimate > budget * self.compact_threshold

    async def compact(
        self,
        messages: list[Message],
        llm: OllamaClient,
        summarizer_model: str,
        summarizer_num_ctx: int,
    ) -> list[Message]:
        system = [m for m in messages if m.role == "system"]
        rest = [m for m in messages if m.role != "system"]
        if len(rest) <= self.keep_recent:
            return messages

        older, recent = rest[: -self.keep_recent], rest[-self.keep_recent :]
        transcript = "\n\n".join(f"{m.role.upper()}: {m.content}" for m in older if m.content)
        if not transcript.strip():
            return messages

        prompt = (
            "Summarize the following conversation concisely, preserving concrete facts, "
            "decisions, file paths, commands run, and open threads. This summary replaces "
            "the original messages in an ongoing conversation — write it as working context "
            "the assistant will need next, not as a message to a user.\n\n" + transcript
        )
        result = await llm.chat(
            summarizer_model, [Message(role="user", content=prompt)], num_ctx=summarizer_num_ctx
        )
        summary = Message(role="system", content=f"[Earlier conversation summary]\n{result.message.content}")
        return [*system, summary, *recent]
