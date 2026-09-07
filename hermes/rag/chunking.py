"""Simple whitespace-token chunking with markdown-aware section splits.

"Tokens" here means whitespace-split words — close enough for sizing RAG chunks
without pulling in tiktoken/sentencepiece.
"""

from __future__ import annotations

import hashlib
import re


_HEADER_RE = re.compile(r"(?m)^(#{1,6}\s.+)$")


def chunk_text(text: str, source: str, chunk_size: int = 450, overlap_ratio: float = 0.12) -> list[str]:
    """Split `text` into ~chunk_size-word chunks with overlap.

    Markdown sources (`.md` in `source` or ATX headers in the body) are first split on
    heading boundaries so each section stays together when possible, then oversized
    sections are windowed with overlap.
    """
    if not text or not text.strip():
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    sections = _split_markdown_sections(text) if _looks_markdown(text, source) else [text.strip()]
    chunks: list[str] = []
    for section in sections:
        chunks.extend(_window_words(section, chunk_size, overlap_ratio))
    return chunks


def _looks_markdown(text: str, source: str) -> bool:
    src = (source or "").lower()
    if (
        src.endswith(".md")
        or src.startswith("skill:")
        or "/skills/" in src
        or (src.startswith("knowledge:") and ".md" in src)
    ):
        return True
    return bool(_HEADER_RE.search(text))


def _split_markdown_sections(text: str) -> list[str]:
    """Split on ATX headings, keeping the heading line with its body."""
    parts = _HEADER_RE.split(text)
    if len(parts) == 1:
        return [text.strip()] if text.strip() else []

    sections: list[str] = []
    # parts alternates: preamble, header, body, header, body, ...
    preamble = parts[0].strip()
    if preamble:
        sections.append(preamble)
    i = 1
    while i < len(parts):
        header = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        block = f"{header}\n{body}".strip() if body else header
        if block:
            sections.append(block)
        i += 2
    return sections


def _window_words(text: str, chunk_size: int, overlap_ratio: float) -> list[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= chunk_size:
        return [" ".join(words)]

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
    """sha256 hex digest of the exact chunk text — used for dedup / change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
