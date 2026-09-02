"""Background RAG refresh scheduler — runs on agent startup and every N hours while the
REPL/TUI/WhatsApp channel is alive. Reuses run_daily_refresh() for the actual work (CVE
delta, malware intel, knowledge/workspace dir, projects, reference corpora)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from hermes.config import HermesConfig
from hermes.core.llm_client import OllamaClient
from hermes.rag.daily_refresh import _get_last_run, _open_state_db, run_daily_refresh
from hermes.rag.ingest import IngestPipeline

_STATE_KEY = "rag_refresh_last_run"
_LEGACY_KEY = "daily_refresh_last_run"


def _read_last_refresh(config: HermesConfig) -> datetime | None:
    conn = _open_state_db(config)
    try:
        raw = _get_last_run(conn, _STATE_KEY) or _get_last_run(conn, _LEGACY_KEY)
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
    finally:
        conn.close()


def refresh_is_due(config: HermesConfig, *, interval_hours: float) -> bool:
    """True when no prior refresh exists or the last one is older than interval_hours."""
    if interval_hours <= 0:
        return False
    last = _read_last_refresh(config)
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last >= timedelta(hours=interval_hours)


async def run_refresh_locked(
    *,
    config: HermesConfig,
    llm: OllamaClient,
    ingest: IngestPipeline,
    lock: asyncio.Lock,
    on_status: Callable[[str], None] | None = None,
) -> dict[str, int] | None:
    """Run one refresh pass under `lock`. Returns summary dict, or None if already running."""
    if lock.locked():
        return None
    async with lock:
        if on_status:
            on_status("running")
        try:
            summary = await run_daily_refresh(config, llm, ingest)
        except Exception as exc:  # noqa: BLE001 - keep the agent alive across a bad refresh
            if on_status:
                on_status(f"error: {type(exc).__name__}: {exc}")
            raise
        if on_status:
            parts = ", ".join(f"{k}={v}" for k, v in summary.items() if v)
            on_status(f"done ({parts or 'no new chunks'})")
        return summary


def start_rag_scheduler(
    *,
    config: HermesConfig,
    llm: OllamaClient,
    ingest: IngestPipeline,
    lock: asyncio.Lock,
    on_status: Callable[[str], None] | None = None,
) -> asyncio.Task | None:
    """Spawn a background task: refresh immediately if due, then every interval_hours."""
    interval_h = config.rag_refresh_interval_hours
    if interval_h <= 0:
        return None

    async def _loop() -> None:
        if refresh_is_due(config, interval_hours=interval_h):
            try:
                await run_refresh_locked(
                    config=config, llm=llm, ingest=ingest, lock=lock, on_status=on_status,
                )
            except Exception:
                pass
        while True:
            await asyncio.sleep(interval_h * 3600)
            try:
                await run_refresh_locked(
                    config=config, llm=llm, ingest=ingest, lock=lock, on_status=on_status,
                )
            except Exception:
                pass

    return asyncio.create_task(_loop(), name="rag-scheduler")
