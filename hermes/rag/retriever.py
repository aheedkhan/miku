"""Query-side of the RAG pipeline: embed a query, search the vector store, and format the
hits into a character-budgeted prompt block so small local models' num_ctx doesn't get
blown out by RAG context."""

from __future__ import annotations

from hermes.rag.embeddings import EmbeddingClient
from hermes.rag.store import DEFAULT_MIN_SCORE, ScoredChunk, VectorStore


class RAGRetriever:
    def __init__(
        self,
        embedder: EmbeddingClient,
        store: VectorStore,
        min_score: float = DEFAULT_MIN_SCORE,
    ):
        self.embedder = embedder
        self.store = store
        self.min_score = min_score

    async def query(
        self,
        text: str,
        k: int = 5,
        source_type: str | None = None,
        source_prefix: str | None = None,
        min_score: float | None = None,
    ) -> list[ScoredChunk]:
        query_embedding = await self.embedder.embed_query(text)
        return self.store.search(
            query_embedding,
            k=k,
            source_type=source_type,
            source_prefix=source_prefix,
            min_score=self.min_score if min_score is None else min_score,
        )

    def format_for_prompt(self, chunks: list[ScoredChunk], max_chars: int = 3000) -> str:
        """Dedupe near-identical chunks, cite each with its source, truncate to a budget."""
        if not chunks:
            return ""

        seen: set[str] = set()
        deduped: list[ScoredChunk] = []
        for sc in chunks:
            key = " ".join(sc.chunk.text.split()).lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(sc)

        parts: list[str] = []
        used = 0
        for sc in deduped:
            block = f"[source: {sc.chunk.source} | score: {sc.score:.3f}]\n{sc.chunk.text.strip()}"
            sep_len = 2 if parts else 0
            if used + sep_len + len(block) > max_chars:
                if not parts:
                    parts.append(block[: max(0, max_chars)])
                break
            parts.append(block)
            used += sep_len + len(block)

        return "\n\n".join(parts)
