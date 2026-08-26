"""Async HTTP client for Ollama's documented JSON API, verified directly against a live
Ollama 0.32.13 server (POST /api/chat with tools+tool results round-trips correctly;
embeddings live at /api/embed, not the legacy /api/embeddings). No ollama-python dependency —
plain httpx keeps exactly what's on the wire visible and avoids being coupled to that
package's object model.

num_ctx is REQUIRED on every chat() call. Verified: Ollama silently caps context at 4096
tokens regardless of a model's advertised maximum unless options.num_ctx is passed explicitly.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from hermes.core.message import Message, ToolCall


@dataclass
class ChatResult:
    message: Message
    prompt_eval_count: int
    eval_count: int
    done_reason: str | None


class OllamaClient:
    def __init__(self, host: str, timeout: float = 300.0):
        self.host = host.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.host, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OllamaClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        num_ctx: int,
        tools: list[dict[str, Any]] | None = None,
        **extra_options: Any,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": model,
            "stream": False,
            "messages": [m.to_ollama() for m in messages],
            "options": {"num_ctx": num_ctx, **extra_options},
        }
        if tools:
            payload["tools"] = tools
        resp = await self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        return self._parse_chat(resp.json())

    async def stream_chat(
        self,
        model: str,
        messages: list[Message],
        *,
        num_ctx: int,
        tools: list[dict[str, Any]] | None = None,
        **extra_options: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yields raw NDJSON chunks. Prefer chat() when tools are involved — tool-calling
        models generally don't stream partial tool_calls usefully."""
        payload: dict[str, Any] = {
            "model": model,
            "stream": True,
            "messages": [m.to_ollama() for m in messages],
            "options": {"num_ctx": num_ctx, **extra_options},
        }
        if tools:
            payload["tools"] = tools
        async with self._client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.strip():
                    yield json.loads(line)

    def _parse_chat(self, data: dict[str, Any]) -> ChatResult:
        msg_data = data.get("message", {}) or {}
        tool_calls = [
            ToolCall(
                id=tc.get("id") or f"call_{i}",
                name=tc["function"]["name"],
                arguments=tc["function"].get("arguments", {}) or {},
            )
            for i, tc in enumerate(msg_data.get("tool_calls") or [])
        ]
        message = Message(
            role="assistant",
            content=msg_data.get("content") or "",
            tool_calls=tool_calls,
            thinking=msg_data.get("thinking"),
        )
        return ChatResult(
            message=message,
            prompt_eval_count=data.get("prompt_eval_count", 0),
            eval_count=data.get("eval_count", 0),
            done_reason=data.get("done_reason"),
        )

    async def embed(self, model: str, inputs: list[str]) -> list[list[float]]:
        resp = await self._client.post("/api/embed", json={"model": model, "input": inputs})
        resp.raise_for_status()
        return resp.json()["embeddings"]

    async def list_models(self) -> list[dict[str, Any]]:
        resp = await self._client.get("/api/tags")
        resp.raise_for_status()
        return resp.json().get("models", [])

    async def show(self, model: str) -> dict[str, Any]:
        resp = await self._client.post("/api/show", json={"model": model})
        resp.raise_for_status()
        return resp.json()

    async def supports_tools(self, model: str) -> bool:
        try:
            info = await self.show(model)
        except httpx.HTTPError:
            return False
        return "tools" in (info.get("capabilities") or [])

    async def ps(self) -> list[dict[str, Any]]:
        resp = await self._client.get("/api/ps")
        resp.raise_for_status()
        return resp.json().get("models", [])

    async def version(self) -> str:
        resp = await self._client.get("/api/version")
        resp.raise_for_status()
        return resp.json().get("version", "unknown")

    async def ping(self) -> bool:
        try:
            await self.version()
            return True
        except httpx.HTTPError:
            return False
