"""Simple whitespace-token chunking — no tokenizer dependency needed at this scale. "Tokens"
here just means whitespace-split words, which is close enough to real LLM tokens for sizing
RAG chunks sanely without pulling in tiktoken/sentencepiece/etc."""

from __future__ import annotations

import hashlib


def chunk_text(text: str, source: str, chunk_size: int = 450, overlap_ratio: float = 0.12) -> list[str]:
    """Split `text` into ~chunk_size-word chunks with ~overlap_ratio overlap between
    consecutive chunks. `source` is accepted for symmetry with the rest of the ingest
    pipeline's signatures and future use (e.g. source-aware splitting heuristics); it does
    not currently affect the output. Returns [] for empty/whitespace-only text."""
    words = text.split()
    if not words:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    overlap = int(chunk_size * overlap_ratio)
    overlap = max(0, min(overlap, chunk_size - 1))
    step = chunk_size - overlap

    chunks: list[str] = []
    i = 0
    n = len(words)
    while i < n:
        piece = words[i : i + chunk_size]
        chunks.append(" ".join(piece))
        if i + chunk_size >= n:
            break
        i += step
    return chunks


def compute_content_hash(text: str) -> str:
    """sha256 hex digest of the exact chunk text, used for dedup against
    VectorStore.has_content_hash — re-ingesting an unchanged chunk is then a safe no-op."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
