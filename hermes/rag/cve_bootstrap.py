"""CVE bootstrap for RAG — pull recent open CVEs across platforms + CISA KEV,
enrich with OSV/NVD, and ingest so rag_query can recall them for research/dev.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from hermes.config import HermesConfig
from hermes.rag.ingest import IngestPipeline
from hermes.tools.cve_tool import (
    PLATFORM_MATCHES,
    fetch_cve,
    format_cve_summary,
    list_cisa_kev,
    list_recent_cves_for_match,
)

_DEFAULT_MAX_PER_PLATFORM = 40
_KEV_MAX = 80
_RELATED_PER_CVE = 2
_NVD_PAUSE_S = 0.7


async def ingest_open_cves(
    config: HermesConfig,
    ingest: IngestPipeline,
    *,
    days: int = 14,
    platforms: list[str] | None = None,
    include_kev: bool = True,
    include_related: bool = True,
    max_per_platform: int = _DEFAULT_MAX_PER_PLATFORM,
    kev_max: int = _KEV_MAX,
) -> dict[str, int]:
    """Fetch + ingest recent platform CVEs and CISA KEV into the vector store."""
    platforms = platforms or list(PLATFORM_MATCHES.keys())
    now = datetime.now(timezone.utc)
    since_iso = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000")
    until_iso = now.strftime("%Y-%m-%dT%H:%M:%S.000")

    summary: dict[str, int] = {
        "platforms_queried": 0,
        "cves_seen": 0,
        "cve_chunks_added": 0,
        "kev_seen": 0,
        "kev_chunks_added": 0,
        "related_seen": 0,
        "related_chunks_added": 0,
    }

    seen: set[str] = set()

    for platform in platforms:
        match = PLATFORM_MATCHES.get(platform)
        if not match:
            continue
        summary["platforms_queried"] += 1
        try:
            cves = await list_recent_cves_for_match(
                config, match, since_iso=since_iso, until_iso=until_iso
            )
        except httpx.HTTPError:
            continue
        for cve in cves[:max_per_platform]:
            cve_id = (cve.get("id") or "").upper()
            if not cve_id or cve_id in seen:
                continue
            seen.add(cve_id)
            summary["cves_seen"] += 1
            added = await _ingest_enriched(config, ingest, cve_id, seed_nvd=cve)
            summary["cve_chunks_added"] += added
            await asyncio.sleep(_NVD_PAUSE_S)

            if include_related:
                related_n, related_added = await _ingest_related(
                    config, ingest, cve_id, cve, seen
                )
                summary["related_seen"] += related_n
                summary["related_chunks_added"] += related_added

    if include_kev:
        try:
            kev_items = await list_cisa_kev(limit=kev_max)
        except httpx.HTTPError:
            kev_items = []
        for item in kev_items:
            cve_id = (item.get("cveID") or "").upper()
            if not cve_id or cve_id in seen:
                continue
            seen.add(cve_id)
            summary["kev_seen"] += 1
            kev_note = _format_kev_card(item)
            added = await ingest.ingest_note_as(
                kev_note, source=f"cve:{cve_id}", source_type="cve"
            )
            enriched = await _ingest_enriched(config, ingest, cve_id)
            summary["kev_chunks_added"] += max(added, enriched)
            await asyncio.sleep(_NVD_PAUSE_S)

    return summary


async def _ingest_enriched(
    config: HermesConfig,
    ingest: IngestPipeline,
    cve_id: str,
    seed_nvd: dict[str, Any] | None = None,
) -> int:
    try:
        merged = await fetch_cve(cve_id, config)
    except Exception:  # noqa: BLE001
        if seed_nvd is None:
            return 0
        merged = {"cve_id": cve_id, "osv": None, "nvd": seed_nvd, "errors": []}

    if merged.get("nvd") is None and seed_nvd is not None:
        merged["nvd"] = seed_nvd

    prose = format_cve_summary(
        merged["cve_id"],
        merged.get("osv"),
        merged.get("nvd"),
        merged.get("errors"),
        develop_hints=True,
    )
    if "not found" in prose.lower() and seed_nvd is None:
        return 0
    return await ingest.ingest_note_as(prose, source=f"cve:{cve_id}", source_type="cve")


async def _ingest_related(
    config: HermesConfig,
    ingest: IngestPipeline,
    cve_id: str,
    nvd_cve: dict[str, Any],
    seen: set[str],
) -> tuple[int, int]:
    cwes: list[str] = []
    for w in nvd_cve.get("weaknesses") or []:
        for d in w.get("description") or []:
            val = (d.get("value") or "").strip()
            if val.startswith("CWE-") and val not in cwes:
                cwes.append(val)
    if not cwes:
        return 0, 0

    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S.000")
    until = now.strftime("%Y-%m-%dT%H:%M:%S.000")
    try:
        hits = await list_recent_cves_for_match(
            config,
            None,
            since_iso=since,
            until_iso=until,
            keyword=cwes[0],
            results_cap=30,
        )
    except httpx.HTTPError:
        return 0, 0

    related_ids: list[str] = []
    for cve in hits:
        rid = (cve.get("id") or "").upper()
        if not rid or rid == cve_id or rid in seen:
            continue
        related_ids.append(rid)
        if len(related_ids) >= _RELATED_PER_CVE:
            break

    added_total = 0
    for rid in related_ids:
        seen.add(rid)
        added_total += await _ingest_enriched(config, ingest, rid)
        await asyncio.sleep(_NVD_PAUSE_S)
    return len(related_ids), added_total


def _format_kev_card(item: dict[str, Any]) -> str:
    cve_id = item.get("cveID", "UNKNOWN")
    lines = [
        f"# {cve_id}",
        "Sources: CISA KEV (Known Exploited Vulnerabilities)",
        f"\nSummary: {item.get('vulnerabilityName') or item.get('shortDescription') or 'n/a'}",
        f"Vendor/Product: {item.get('vendorProject', '?')} / {item.get('product', '?')}",
        f"Date added to KEV: {item.get('dateAdded', '?')}",
        f"Due date: {item.get('dueDate', '?')}",
        f"Known ransomware use: {item.get('knownRansomwareCampaignUse', 'Unknown')}",
        f"Required action: {item.get('requiredAction', 'n/a')}",
        "\nDevelop notes: KEV entry — prioritize lab verification if you own the product. "
        "Build a minimal harness only after reading the vendor advisory + root cause; "
        "pair with detection twin. See workspace/cves/how-to-develop-harness.md.",
    ]
    if item.get("shortDescription"):
        lines.append(f"\nDetails: {item['shortDescription']}")
    return "\n".join(lines)
