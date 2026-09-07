"""Turns files/CVE records/malware reports into embedded, deduped chunks in the VectorStore.

Per-source replace on change: if a file's chunk hashes differ from what's stored for that
source, old chunks are soft-deleted and the file is re-embedded. Unchanged files are a
cheap no-op (hash-set compare, no Ollama call).
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hermes.config import DEFAULT_PROJECT_EXCLUDE, DEFAULT_PROJECT_INCLUDE, HermesConfig, ProjectSource
from hermes.rag.chunking import chunk_text, compute_content_hash
from hermes.rag.embeddings import EmbeddingClient
from hermes.rag.store import VectorStore
from hermes.tools.cve_tool import format_cve_summary
from hermes.tools.malware_bazaar_tool import format_sample_report

Chunker = Callable[..., list[str]]


class IngestPipeline:
    def __init__(
        self,
        embedder: EmbeddingClient,
        store: VectorStore,
        chunker: Chunker = chunk_text,
    ):
        self.embedder = embedder
        self.store = store
        self.chunker = chunker

    async def _ingest_text(
        self,
        text: str,
        source: str,
        source_type: str,
        metadata: dict[str, Any] | None = None,
        *,
        replace: bool = True,
    ) -> int:
        """Chunk + embed into the store.

        When `replace` is True (default), if the new chunk-hash set differs from what's
        already active for `source`, soft-delete the old rows and re-add. Unchanged content
        returns 0 without calling the embedder.
        """
        if not text or not text.strip():
            return 0

        pieces = self.chunker(text, source)
        if not pieces:
            return 0

        # Dedupe identical pieces inside one file so hash-set compare stays stable.
        unique_pieces: list[str] = []
        seen_local: set[str] = set()
        for piece in pieces:
            h = compute_content_hash(piece)
            if h in seen_local:
                continue
            seen_local.add(h)
            unique_pieces.append(piece)
        pieces = unique_pieces
        new_hashes = [compute_content_hash(piece) for piece in pieces]
        existing = self.store.hashes_for_source(source)
        if existing == set(new_hashes):
            return 0

        if replace and existing:
            self.store.delete_by_source(source)

        # Always attach chunks to this source (duplicates across sources are OK).
        # Skipping on global hash made multi-source shared text fail idempotent re-index.
        embeddings = await self.embedder.embed_documents(pieces)
        for piece, h, embedding in zip(pieces, new_hashes, embeddings):
            self.store.add(
                text=piece,
                embedding=embedding,
                source=source,
                source_type=source_type,
                content_hash=h,
                metadata=metadata,
                defer_flush=True,
            )
        self.store.flush()
        return len(pieces)

    async def ingest_file(self, path: Path, source_type: str, source: str | None = None) -> int:
        """Ingest one file's text content. `source` defaults to f"{source_type}:{path}"."""
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return 0
        if source is None:
            source = f"{source_type}:{path}"
        return await self._ingest_text(
            text, source=source, source_type=source_type, metadata={"path": str(path)}
        )

    async def ingest_cve(self, cve_data: dict[str, Any], cve_id: str) -> int:
        if "osv" in cve_data or "nvd" in cve_data:
            osv = cve_data.get("osv")
            nvd = cve_data.get("nvd")
            errors = cve_data.get("errors")
        else:
            osv = None
            nvd = cve_data
            errors = None

        prose = format_cve_summary(cve_id, osv, nvd, errors, develop_hints=True)
        return await self._ingest_text(prose, source=f"cve:{cve_id}", source_type="cve")

    async def ingest_malware_report(self, mb_info: dict[str, Any], sha256: str) -> int:
        prose = format_sample_report(mb_info)
        return await self._ingest_text(prose, source=f"malware:{sha256}", source_type="malware_intel")

    async def ingest_note(self, text: str, label: str) -> int:
        """Remember arbitrary text under source=note:{label} (replaces prior note with same label)."""
        return await self._ingest_text(text, source=f"note:{label}", source_type="knowledge")

    async def ingest_note_as(self, text: str, *, source: str, source_type: str) -> int:
        """Ingest prose under an explicit source tag (used by CVE bootstrap)."""
        return await self._ingest_text(text, source=source, source_type=source_type)

    async def ingest_knowledge_dir(self, config: HermesConfig) -> int:
        """Ingest every matching file under config.knowledge_dir."""
        base = config.knowledge_dir
        if not base.is_dir():
            return 0
        total = 0
        for path in scan_dir(base, include_globs=DEFAULT_PROJECT_INCLUDE, exclude_globs=DEFAULT_PROJECT_EXCLUDE):
            rel = path.relative_to(base).as_posix()
            total += await self.ingest_file(path, source_type="knowledge", source=f"knowledge:{rel}")
        return total

    async def ingest_skills_dir(self, config: HermesConfig) -> int:
        """Ingest each skills/<name>/SKILL.md so playbooks are searchable via rag_query."""
        base = config.skills_dir
        if not base.is_dir():
            return 0
        total = 0
        for skill_md in sorted(base.glob("*/SKILL.md")):
            name = skill_md.parent.name
            total += await self.ingest_file(
                skill_md, source_type="skill", source=f"skill:{name}"
            )
        return total

    async def ingest_project(self, project: ProjectSource) -> int:
        base = project.path
        if not base.is_dir():
            return 0
        total = 0
        for path in scan_dir(base, include_globs=project.include, exclude_globs=project.exclude):
            rel = path.relative_to(base).as_posix()
            total += await self.ingest_file(
                path, source_type="project", source=f"project:{project.name}:{rel}"
            )
        return total


def _matches_any(rel_posix_with_lead_slash: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel_posix_with_lead_slash, pat) for pat in patterns)


def scan_dir(
    path: Path,
    include_globs: list[str] | None,
    exclude_globs: list[str] | None,
) -> list[Path]:
    """List files under `path` matching include_globs and none of exclude_globs."""
    path = Path(path)
    if not path.is_dir():
        return []

    matches: list[Path] = []
    for candidate in sorted(path.rglob("*")):
        if not candidate.is_file():
            continue
        rel = candidate.relative_to(path).as_posix()
        rel_slashed = f"/{rel}"

        if exclude_globs and _matches_any(rel_slashed, exclude_globs):
            continue
        if include_globs and not _matches_any(candidate.name, include_globs) and not _matches_any(rel_slashed, include_globs):
            continue

        matches.append(candidate)
    return matches
