"""Wraps OllamaClient.embed() for nomic-embed-text's task-prefix convention. Applying the
right "search_document: "/"search_query: " prefix measurably affects nomic's retrieval
quality since it's part of the model's own fine-tuning convention, not optional metadata —
always apply exactly one, never neither."""

from __future__ import annotations

from hermes.core.llm_client import OllamaClient


class EmbeddingClient:
    def __init__(self, llm: OllamaClient, model: str = "nomic-embed-text", batch_size: int = 32):
        self.llm = llm
        self.model = model
        self.batch_size = batch_size

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed_prefixed(texts, "search_document: ")

    async def embed_query(self, text: str) -> list[float]:
        (result,) = await self._embed_prefixed([text], "search_query: ")
        return result

    async def _embed_prefixed(self, texts: list[str], prefix: str) -> list[list[float]]:
        prefixed = [f"{prefix}{t}" for t in texts]
        out: list[list[float]] = []
        for i in range(0, len(prefixed), self.batch_size):
            batch = prefixed[i : i + self.batch_size]
            out.extend(await self.llm.embed(self.model, batch))
        return out
