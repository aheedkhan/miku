"""Daily background refresh: pull the Android-CVE delta from NVD, pull recent MalwareBazaar
Android samples (metadata only, skipped cleanly with no key configured), and re-scan every
configured project + the knowledge dir — all via IngestPipeline, so dedup is the same
content-hash mechanism used everywhere else in the RAG layer.

Last-run bookkeeping lives in a tiny key/value table inside config.state_db_path (stdlib
sqlite3 — no new dependency, and it's the same file the rest of Hermes's state lives in).
The timestamp is only updated after every step completes without raising, so a crash
mid-refresh naturally retries the same window next time instead of silently skipping it.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from hermes.config import HermesConfig
from hermes.core.llm_client import OllamaClient
from hermes.rag.fetch_references import ingest_references
from hermes.rag.ingest import IngestPipeline
from hermes.tools.cve_tool import list_recent_android_cves
from hermes.tools.malware_bazaar_tool import mb_get_recent

_STATE_KEY = "daily_refresh_last_run"

# MalwareBazaar tags pulled daily for cross-platform sample intel (metadata only — see
# malware_bazaar_tool.py's module docstring). File-type tags (exe/dll/elf) are more reliable
# than platform-name tags since they're closer to how samples actually get auto-tagged.
_MALWARE_TAGS = ["android", "apk", "exe", "dll", "elf"]


def _open_state_db(config: HermesConfig) -> sqlite3.Connection:
    config.state_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.state_db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS kv_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    conn.commit()
    return conn


def _get_last_run(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT value FROM kv_state WHERE key = ?", (_STATE_KEY,)).fetchone()
    return row[0] if row else None


def _set_last_run(conn: sqlite3.Connection, value: str) -> None:
    conn.execute(
        "INSERT INTO kv_state (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (_STATE_KEY, value),
    )
    conn.commit()


async def run_daily_refresh(
    config: HermesConfig,
    llm: OllamaClient,
    retriever_ingest: IngestPipeline,
) -> dict[str, int]:
    """Runs one refresh pass; returns a summary of counts. `llm` is accepted per the required
    signature (kept available for a future step that wants a live model call, e.g.
    summarizing the day's CVE delta) but the current steps only need retriever_ingest, whose
    embedder already owns its own OllamaClient."""
    del llm  # not needed by any current step; kept for interface stability, see docstring

    conn = _open_state_db(config)
    try:
        last_run_iso = _get_last_run(conn)
        now = datetime.now(timezone.utc)
        if last_run_iso:
            try:
                since = datetime.fromisoformat(last_run_iso)
            except ValueError:
                since = now - timedelta(days=7)
        else:
            since = now - timedelta(days=7)

        since_iso = since.strftime("%Y-%m-%dT%H:%M:%S.000")
        until_iso = now.strftime("%Y-%m-%dT%H:%M:%S.000")

        summary: dict[str, int] = {
            "android_cves_found": 0,
            "android_cve_chunks_added": 0,
            "malware_samples_found": 0,
            "malware_chunks_added": 0,
            "project_chunks_added": 0,
            "knowledge_chunks_added": 0,
            "reference_chunks_added": 0,
        }

        # (a) Android CVE delta from NVD.
        cves = await list_recent_android_cves(config, since_iso=since_iso, until_iso=until_iso)
        summary["android_cves_found"] = len(cves)
        for cve in cves:
            cve_id = cve.get("id")
            if not cve_id:
                continue
            summary["android_cve_chunks_added"] += await retriever_ingest.ingest_cve(cve, cve_id)

        # (b) MalwareBazaar recent samples across platforms (Android + Windows PE/DLL + Linux
        # ELF) — metadata only, skipped cleanly (not an error) when no Auth-Key is configured.
        if config.malwarebazaar_auth_key:
            seen_hashes: set[str] = set()
            for tag in _MALWARE_TAGS:
                samples = await mb_get_recent(config, tag=tag)
                for sample in samples:
                    sha256 = sample.get("sha256_hash")
                    if not sha256 or sha256 in seen_hashes:
                        continue
                    seen_hashes.add(sha256)
                    summary["malware_samples_found"] += 1
                    summary["malware_chunks_added"] += await retriever_ingest.ingest_malware_report(sample, sha256)
        # else: no key configured — cleanly skipped, summary counts stay at 0.

        # (c) Every configured project, plus the knowledge dir.
        for project in config.projects:
            summary["project_chunks_added"] += await retriever_ingest.ingest_project(project)
        summary["knowledge_chunks_added"] += await retriever_ingest.ingest_knowledge_dir(config)

        # (d) Reference corpora (Win32 API docs, Linux kernel docs, MITRE ATT&CK) — only
        # ingests what's already been fetched via `python -m hermes.rag.fetch_references`;
        # never fetches on its own (see that module's docstring).
        reference_counts = await ingest_references(config, retriever_ingest)
        summary["reference_chunks_added"] = sum(reference_counts.values())

        # Only advance the watermark once every step above has completed without raising.
        _set_last_run(conn, now.strftime("%Y-%m-%dT%H:%M:%S.%f"))
        return summary
    finally:
        conn.close()


def _cli() -> None:
    """Standalone entrypoint for cron/systemd-timer use: `python -m hermes.rag.daily_refresh`.
    Builds its own OllamaClient/embedder/store/IngestPipeline rather than reusing a REPL's,
    since this runs as its own short-lived process with no interactive session around it."""
    import asyncio

    from hermes.config import load_config
    from hermes.core.llm_client import OllamaClient
    from hermes.rag.embeddings import EmbeddingClient
    from hermes.rag.ingest import IngestPipeline
    from hermes.rag.store import VectorStore

    async def _main() -> None:
        config = load_config()
        llm = OllamaClient(config.ollama_host)
        try:
            embedder = EmbeddingClient(llm, model=config.model("embed").name)
            store = VectorStore(config.rag_dir, dim=768)
            try:
                ingest = IngestPipeline(embedder, store)
                summary = await run_daily_refresh(config, llm, ingest)
                for key, value in summary.items():
                    print(f"{key}: {value}")
            finally:
                store.close()
        finally:
            await llm.aclose()

    asyncio.run(_main())


if __name__ == "__main__":
    _cli()
