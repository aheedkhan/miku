"""Bounds concurrent heavy LLM calls across the main agent and every sub-agent.

Verified on this hardware (RTX A2000 Laptop, 4GB VRAM, 62GB RAM): a 20-30B quantized model
runs ~87% CPU / 13% GPU here — inference is CPU/RAM-bound, not VRAM-bound. Two heavy
generations running "concurrently" mostly just halve each other's tokens/sec rather than
running in true parallel, so the default is to serialize them. Sub-agents still buy you a
clean, separate context window — they just don't buy free parallel generation on this class
of hardware. Raise max_concurrent in config if you're running Hermes against a beefier
Ollama host (e.g. a dedicated GPU box or a cloud-ish Ollama VM)."""

from __future__ import annotations

import asyncio


class InferenceGate:
    def __init__(self, max_concurrent: int = 1):
        self._sem = asyncio.Semaphore(max(1, max_concurrent))

    async def __aenter__(self) -> "InferenceGate":
        await self._sem.acquire()
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._sem.release()

    def acquire_for_model(self, model: str) -> "InferenceGate":
        # `model` is accepted for future per-model gating (e.g. different limits for the
        # small "fast" summarizer vs the heavy default model); currently one shared gate.
        return self
