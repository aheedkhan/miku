"""Numpy flat matrix (cosine similarity via one BLAS matmul) + sqlite3 for text/metadata,
joined by row index. Deliberately not chromadb/lancedb/sqlite-vec: at personal-RAG scale
(thousands-tens of thousands of chunks) brute-force search is single-digit milliseconds,
and this avoids every Python-3.14 wheel/compiled-extension risk those options carry.

Soft-delete only: delete_by_source marks sqlite rows deleted, excluding them from search,
but doesn't compact the .npy matrix (row_index positions must stay stable). Fine at this
scale — wasted vector-matrix space, never wrong results.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

# Cosine floor for nomic-embed-text — below this, hits are usually unrelated filler.
# Tuned against live queries: on-topic RAT/Defender ~0.63+, random junk ~0.50–0.56.
DEFAULT_MIN_SCORE = 0.58


@dataclass
class Chunk:
    id: int
    text: str
    source: str  # e.g. "knowledge:notes.md", "cve:CVE-2024-1234", "malware:<sha256>", "project:<name>:path"
    source_type: str  # "knowledge" | "cve" | "malware_intel" | "project" | "web_cache" | "skill"
    metadata: dict[str, Any]


@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float


class VectorStore:
    def __init__(self, data_dir: Path, dim: int = 768):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.dim = dim
        self._matrix_path = self.data_dir / "embeddings.npy"
        self._db_path = self.data_dir / "chunks.sqlite3"
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()
        self._matrix = self._load_matrix()
        self._dirty = False

    def _init_db(self) -> None:
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS chunks (
                row_index INTEGER PRIMARY KEY,
                text TEXT NOT NULL,
                source TEXT NOT NULL,
                source_type TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0
            )"""
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON chunks(source)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_source_type ON chunks(source_type)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON chunks(content_hash)")
        self._conn.commit()

    def _load_matrix(self) -> np.ndarray:
        if self._matrix_path.is_file():
            arr = np.load(self._matrix_path)
            if arr.shape[0] and arr.shape[1] != self.dim:
                self.dim = arr.shape[1]  # trust what's on disk over the constructor default
            return arr
        return np.zeros((0, self.dim), dtype=np.float32)

    def _save_matrix(self) -> None:
        np.save(self._matrix_path, self._matrix)
        self._dirty = False

    def flush(self) -> None:
        """Persist pending matrix writes (call after a batch of add())."""
        if self._dirty:
            self._save_matrix()
        self._conn.commit()

    def has_content_hash(self, content_hash: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM chunks WHERE content_hash = ? AND deleted = 0 LIMIT 1", (content_hash,)
        ).fetchone()
        return row is not None

    def hashes_for_source(self, source: str) -> set[str]:
        rows = self._conn.execute(
            "SELECT content_hash FROM chunks WHERE source = ? AND deleted = 0", (source,)
        ).fetchall()
        return {r["content_hash"] for r in rows}

    def active_count(self) -> int:
        return int(
            self._conn.execute("SELECT COUNT(*) FROM chunks WHERE deleted = 0").fetchone()[0]
        )

    def stats_by_source_type(self) -> list[tuple[str, int]]:
        rows = self._conn.execute(
            "SELECT source_type, COUNT(*) AS n FROM chunks WHERE deleted = 0 "
            "GROUP BY source_type ORDER BY source_type"
        ).fetchall()
        return [(r["source_type"], int(r["n"])) for r in rows]

    def add(
        self,
        text: str,
        embedding: list[float],
        source: str,
        source_type: str,
        content_hash: str,
        metadata: dict[str, Any] | None = None,
        *,
        defer_flush: bool = False,
    ) -> int:
        vec = np.asarray(embedding, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        row_index = self._matrix.shape[0]
        self._matrix = np.vstack([self._matrix, vec[None, :]])
        self._conn.execute(
            "INSERT INTO chunks (row_index, text, source, source_type, content_hash, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row_index, text, source, source_type, content_hash, json.dumps(metadata or {}), time.time()),
        )
        self._dirty = True
        if defer_flush:
            return row_index
        self._conn.commit()
        self._save_matrix()
        return row_index

    def delete_by_source(self, source: str) -> int:
        cur = self._conn.execute(
            "UPDATE chunks SET deleted = 1 WHERE source = ? AND deleted = 0", (source,)
        )
        self._conn.commit()
        return cur.rowcount

    def search(
        self,
        query_embedding: list[float],
        k: int = 5,
        source_type: str | None = None,
        source_prefix: str | None = None,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> list[ScoredChunk]:
        if self._matrix.shape[0] == 0:
            return []
        q = np.asarray(query_embedding, dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm

        clauses = ["deleted = 0"]
        params: list[Any] = []
        if source_type:
            clauses.append("source_type = ?")
            params.append(source_type)
        if source_prefix:
            clauses.append("source LIKE ?")
            params.append(f"{source_prefix}%")
        where = " AND ".join(clauses)
        rows = self._conn.execute(f"SELECT * FROM chunks WHERE {where}", params).fetchall()
        if not rows:
            return []

        indices = np.array([r["row_index"] for r in rows])
        sims = self._matrix[indices] @ q  # cosine similarity: both sides pre-normalized
        # Fetch a wider candidate window, then apply the relevance floor.
        cand = min(max(k * 4, k), len(sims))
        top = np.argsort(-sims)[:cand]

        results: list[ScoredChunk] = []
        for i in top:
            score = float(sims[int(i)])
            if score < min_score:
                continue
            row = rows[int(i)]
            chunk = Chunk(
                id=row["row_index"],
                text=row["text"],
                source=row["source"],
                source_type=row["source_type"],
                metadata=json.loads(row["metadata"]),
            )
            results.append(ScoredChunk(chunk=chunk, score=score))
            if len(results) >= k:
                break
        return results

    def close(self) -> None:
        self.flush()
        self._conn.close()
