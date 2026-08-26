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


@dataclass
class Chunk:
    id: int
    text: str
    source: str  # e.g. "knowledge:notes.md", "cve:CVE-2024-1234", "malware:<sha256>", "project:fyp-mdm:path"
    source_type: str  # "knowledge" | "cve" | "malware_intel" | "project" | "web_cache"
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

    def has_content_hash(self, content_hash: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM chunks WHERE content_hash = ? AND deleted = 0 LIMIT 1", (content_hash,)
        ).fetchone()
        return row is not None

    def add(
        self,
        text: str,
        embedding: list[float],
        source: str,
        source_type: str,
        content_hash: str,
        metadata: dict[str, Any] | None = None,
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
        self._conn.commit()
        self._save_matrix()
        return row_index

    def delete_by_source(self, source: str) -> int:
        cur = self._conn.execute("UPDATE chunks SET deleted = 1 WHERE source = ?", (source,))
        self._conn.commit()
        return cur.rowcount

    def search(
        self,
        query_embedding: list[float],
        k: int = 5,
        source_type: str | None = None,
        source_prefix: str | None = None,
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
        top = np.argsort(-sims)[:k]

        results = []
        for i in top:
            row = rows[int(i)]
            chunk = Chunk(
                id=row["row_index"],
                text=row["text"],
                source=row["source"],
                source_type=row["source_type"],
                metadata=json.loads(row["metadata"]),
            )
            results.append(ScoredChunk(chunk=chunk, score=float(sims[int(i)])))
        return results

    def close(self) -> None:
        self._conn.close()
