"""Turns files/CVE records/malware reports into embedded, deduped chunks in the VectorStore.

Dedup is entirely content-hash based (VectorStore.has_content_hash) — re-ingesting an
unchanged file/record is a safe, cheap no-op because every one of its chunks hashes the same
as what's already stored. scan_dir() is deliberately dumb (just lists matching files); it does
not itself track "already ingested" state, since content-hash dedup in ingest_file already
makes that redundant and avoids a second, easily-desynced bookkeeping layer.
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
    ) -> int:
        """Chunk, dedup by content hash, embed only the new chunks, and store them. Returns
        the count of chunks actually added (chunks already present by hash are skipped, not
        counted)."""
        if not text or not text.strip():
            return 0

        pieces = self.chunker(text, source)
        new_pieces: list[str] = []
        new_hashes: list[str] = []
        for piece in pieces:
            h = compute_content_hash(piece)
            if self.store.has_content_hash(h):
                continue
            new_pieces.append(piece)
            new_hashes.append(h)

        if not new_pieces:
            return 0

        embeddings = await self.embedder.embed_documents(new_pieces)
        for piece, h, embedding in zip(new_pieces, new_hashes, embeddings):
            self.store.add(
                text=piece,
                embedding=embedding,
                source=source,
                source_type=source_type,
                content_hash=h,
                metadata=metadata,
            )
        return len(new_pieces)

    async def ingest_file(self, path: Path, source_type: str, source: str | None = None) -> int:
        """Ingest one file's text content. `source` defaults to f"{source_type}:{path}" when
        not given; callers that need a specific tag (e.g. a project-relative path) pass it
        explicitly — see ingest_project()/ingest_knowledge_dir() below."""
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return 0
        if source is None:
            source = f"{source_type}:{path}"
        return await self._ingest_text(text, source=source, source_type=source_type, metadata={"path": str(path)})

    async def ingest_cve(self, cve_data: dict[str, Any], cve_id: str) -> int:
        """Format a fetched CVE record into readable prose (reusing cve_tool's own summary
        formatter so the RAG-stored text matches what cve_lookup shows the model directly),
        then chunk+embed+store it. Accepts either shape produced by this codebase:
        - fetch_cve()'s merged {"osv": ..., "nvd": ..., "errors": [...]}  dict, or
        - a raw NVD `cve` object as returned by list_recent_android_cves() (no "osv"/"nvd"
          keys of its own — used as-is as the NVD side, with no OSV side)."""
        if "osv" in cve_data or "nvd" in cve_data:
            osv = cve_data.get("osv")
            nvd = cve_data.get("nvd")
            errors = cve_data.get("errors")
        else:
            osv = None
            nvd = cve_data
            errors = None

        prose = format_cve_summary(cve_id, osv, nvd, errors)
        return await self._ingest_text(prose, source=f"cve:{cve_id}", source_type="cve")

    async def ingest_malware_report(self, mb_info: dict[str, Any], sha256: str) -> int:
        """Format a MalwareBazaar get_info result (family, tags, YARA hits, vendor_intel
        verdicts, code-signing info) into readable prose describing what kind of malware this
        is and how it was detected, then chunk+embed+store it. Report/metadata ingestion only
        — no sample binary is ever downloaded, fetched, or referenced by path here."""
        prose = format_sample_report(mb_info)
        return await self._ingest_text(prose, source=f"malware:{sha256}", source_type="malware_intel")

    async def ingest_note(self, text: str, label: str) -> int:
        """Generic "remember this for later" ingestion — embeds arbitrary text under
        source=f"note:{label}", source_type="knowledge". Used by rag_tool.py's rag_remember
        so the model can call it mid-conversation without reaching into a private method."""
        return await self._ingest_text(text, source=f"note:{label}", source_type="knowledge")

    async def ingest_knowledge_dir(self, config: HermesConfig) -> int:
        """Ingest every matching file under config.knowledge_dir, tagged source_type="knowledge"
        and source=f"knowledge:{relative_path}". HermesConfig has no separate include/exclude
        for knowledge_dir, so this reuses the same DEFAULT_PROJECT_INCLUDE/EXCLUDE globs
        ProjectSource defaults to, per "handle knowledge_dir the same way as projects"."""
        base = config.knowledge_dir
        if not base.is_dir():
            return 0
        total = 0
        for path in scan_dir(base, include_globs=DEFAULT_PROJECT_INCLUDE, exclude_globs=DEFAULT_PROJECT_EXCLUDE):
            rel = path.relative_to(base).as_posix()
            total += await self.ingest_file(path, source_type="knowledge", source=f"knowledge:{rel}")
        return total

    async def ingest_project(self, project: ProjectSource) -> int:
        """Ingest every matching file under one configured ProjectSource, tagged
        source_type="project" and source=f"project:{project.name}:{relative_path}" so
        retrieval can filter to this one project by source_prefix=f"project:{project.name}:"."""
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
    """List files under `path` (recursively) matching any of include_globs and none of
    exclude_globs. Purely a lister over the current on-disk tree (hence "mtime-based": it
    always reflects whatever is on disk right now, with no separate persisted "last seen"
    state of its own) — actual new-vs-unchanged diffing happens downstream in ingest_file via
    content-hash dedup, so re-scanning an unchanged tree is cheap and safe.

    include_globs/exclude_globs match against the file's path relative to `path`, prefixed
    with a leading "/" (so "*/node_modules/*"-style excludes correctly match a top-level
    node_modules/ too, not just a nested one). include_globs=None matches every regular file.
    """
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
