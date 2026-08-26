"""CVE lookup: OSV.dev (primary, key-free) + NVD (enrichment, key-free but rate-limited
without an API key) merged into one readable summary citing both sources, plus a plain
NVD-backed "recent Android CVEs" feed.

Every fetch function is a plain importable async function separate from the Tool/build_tools
wrapping (fetch_cve, list_recent_android_cves) so hermes/rag/daily_refresh.py can call them
directly without going through ToolRegistry dispatch.

Live-verified (2026-08-26) against the real APIs:
- GET https://api.osv.dev/v1/vulns/CVE-2024-3094 -> 200, real xz-backdoor data, no key needed.
- GET https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2024-3094 -> 200, works
  keyless (just rate-limited to 5 req/30s vs 50 with an apiKey).
- NVD's `cpeName` param REJECTS wildcards (`cpe:2.3:o:google:android:*:...` -> 404 "Invalid
  cpeName parameter"). The wildcard-search parameter NVD actually documents for this is
  `virtualMatchString`, confirmed live to return real, current Android-related CVEs
  (Chrome-on-Android, AOSP, etc.) for a lastModStartDate/lastModEndDate window. This module
  uses virtualMatchString — see list_recent_android_cves — that's a corrected param name
  versus the literal `cpeName=...` suggested in the original task text, not a design choice.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from hermes.config import HermesConfig
from hermes.tools.base import Tool, ToolResult, ToolSchema

OSV_URL = "https://api.osv.dev/v1/vulns/{cve_id}"
NVD_CVE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
ANDROID_VIRTUAL_MATCH_STRING = "cpe:2.3:o:google:android"

_HTTP_TIMEOUT = 30.0
_NVD_PAGE_SIZE = 200
_NVD_MAX_PAGES = 10  # safety cap: 10 * 200 = 2000 CVEs is far more than any daily/weekly delta


def _nvd_headers(config: HermesConfig) -> dict[str, str] | None:
    return {"apiKey": config.nvd_api_key} if config.nvd_api_key else None


async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    max_retries: int = 1,
) -> httpx.Response:
    """GET with one retry + backoff on HTTP 429, honoring Retry-After when present."""
    attempt = 0
    while True:
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code == 429 and attempt < max_retries:
            try:
                wait = float(resp.headers.get("Retry-After", "6"))
            except ValueError:
                wait = 6.0
            await asyncio.sleep(max(wait, 1.0))
            attempt += 1
            continue
        return resp


async def fetch_osv(cve_id: str) -> dict[str, Any] | None:
    """Raw OSV.dev record for a CVE/GHSA id, or None if OSV has no record (404)."""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await _get_with_retry(client, OSV_URL.format(cve_id=cve_id))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


async def fetch_nvd(cve_id: str, config: HermesConfig) -> dict[str, Any] | None:
    """Raw NVD `cve` object for a single CVE id, or None if NVD has no record."""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await _get_with_retry(
            client, NVD_CVE_URL, params={"cveId": cve_id}, headers=_nvd_headers(config)
        )
    resp.raise_for_status()
    data = resp.json()
    vulns = data.get("vulnerabilities") or []
    return vulns[0]["cve"] if vulns else None


async def fetch_cve(cve_id: str, config: HermesConfig) -> dict[str, Any]:
    """Fetch one CVE from OSV.dev (primary) and NVD (enrichment). Never raises for a
    not-found/unreachable single source — records the problem in "errors" instead, so a
    partial result (e.g. OSV has it, NVD is down) is still useful."""
    cve_id = cve_id.strip().upper()
    osv_data: dict[str, Any] | None = None
    nvd_data: dict[str, Any] | None = None
    errors: list[str] = []

    try:
        osv_data = await fetch_osv(cve_id)
    except httpx.HTTPError as e:
        errors.append(f"OSV.dev: {type(e).__name__}: {e}")

    try:
        nvd_data = await fetch_nvd(cve_id, config)
    except httpx.HTTPError as e:
        errors.append(f"NVD: {type(e).__name__}: {e}")

    return {"cve_id": cve_id, "osv": osv_data, "nvd": nvd_data, "errors": errors}


def _osv_cvss(osv: dict[str, Any]) -> str | None:
    for sev in osv.get("severity") or []:
        if "CVSS" in (sev.get("type") or ""):
            return sev.get("score")
    return None


def _nvd_cvss(nvd: dict[str, Any]) -> tuple[str | None, float | None]:
    metrics = nvd.get("metrics") or {}
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        arr = metrics.get(key)
        if arr:
            data = arr[0].get("cvssData", {})
            return data.get("baseSeverity"), data.get("baseScore")
    return None, None


def format_cve_summary(cve_id: str, osv: dict[str, Any] | None, nvd: dict[str, Any] | None,
                        errors: list[str] | None = None) -> str:
    """Readable prose summary of a merged CVE record, citing which source(s) it came from.
    Shared by the cve_lookup tool and rag/ingest.py's ingest_cve()."""
    if osv is None and nvd is None:
        msg = f"{cve_id}: not found in OSV.dev or NVD."
        if errors:
            msg += " Errors: " + "; ".join(errors)
        return msg

    lines = [f"# {cve_id}"]
    sources = []
    if osv is not None:
        sources.append("OSV.dev")
    if nvd is not None:
        sources.append("NVD")
    lines.append(f"Sources: {', '.join(sources)}")

    summary = None
    details = None
    if osv is not None:
        summary = osv.get("summary")
        details = osv.get("details")
    if not summary and nvd is not None:
        for d in nvd.get("descriptions") or []:
            if d.get("lang") == "en":
                summary = d.get("value")
                break

    if summary:
        lines.append(f"\nSummary: {summary}")
    if details and details != summary:
        lines.append(f"\nDetails (OSV.dev): {details}")

    if osv is not None:
        cvss = _osv_cvss(osv)
        if cvss:
            lines.append(f"\nCVSS (OSV.dev): {cvss}")
        published = osv.get("published")
        modified = osv.get("modified")
        if published:
            lines.append(f"Published (OSV.dev): {published}")
        if modified:
            lines.append(f"Last modified (OSV.dev): {modified}")
        aliases = osv.get("aliases") or []
        if aliases:
            lines.append(f"Aliases: {', '.join(aliases)}")
        affected = osv.get("affected") or []
        if affected:
            pkgs = []
            for a in affected[:10]:
                pkg = a.get("package", {}).get("name") or a.get("package", {}).get("ecosystem")
                if pkg:
                    pkgs.append(pkg)
            if pkgs:
                lines.append(f"Affected packages (OSV.dev): {', '.join(pkgs)}")

    if nvd is not None:
        severity, score = _nvd_cvss(nvd)
        if severity or score is not None:
            lines.append(f"\nCVSS (NVD): {severity or '?'} ({score if score is not None else '?'})")
        vuln_status = nvd.get("vulnStatus")
        if vuln_status:
            lines.append(f"NVD status: {vuln_status}")
        published = nvd.get("published")
        modified = nvd.get("lastModified")
        if published:
            lines.append(f"Published (NVD): {published}")
        if modified:
            lines.append(f"Last modified (NVD): {modified}")
        weaknesses = []
        for w in nvd.get("weaknesses") or []:
            for d in w.get("description") or []:
                if d.get("lang") == "en" and d.get("value"):
                    weaknesses.append(d["value"])
        if weaknesses:
            lines.append(f"Weaknesses (CWE): {', '.join(dict.fromkeys(weaknesses))}")

    refs: list[str] = []
    if osv is not None:
        for r in (osv.get("references") or [])[:5]:
            url = r.get("url")
            if url:
                refs.append(url)
    if nvd is not None:
        for r in (nvd.get("references") or [])[:5]:
            url = r.get("url")
            if url and url not in refs:
                refs.append(url)
    if refs:
        lines.append("\nReferences:")
        lines.extend(f"  - {u}" for u in refs[:8])

    if errors:
        lines.append(f"\n(Partial data — {'; '.join(errors)})")

    return "\n".join(lines)


async def list_recent_android_cves(
    config: HermesConfig,
    since_iso: str | None = None,
    until_iso: str | None = None,
) -> list[dict[str, Any]]:
    """Recently-modified Android-related CVEs from NVD (virtualMatchString wildcard search
    over cpe:2.3:o:google:android, filtered by lastModStartDate/lastModEndDate). Returns the
    raw NVD `cve` objects. since_iso/until_iso are NVD's expected `%Y-%m-%dT%H:%M:%S.000` UTC
    strings (no "Z" suffix — that's what the live API accepts); when omitted, defaults to "the
    last 7 days up to now"."""
    now = datetime.now(timezone.utc)
    if until_iso is None:
        until_iso = now.strftime("%Y-%m-%dT%H:%M:%S.000")
    if since_iso is None:
        since_iso = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.000")

    results: list[dict[str, Any]] = []
    start_index = 0
    headers = _nvd_headers(config)

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        for _ in range(_NVD_MAX_PAGES):
            params = {
                "virtualMatchString": ANDROID_VIRTUAL_MATCH_STRING,
                "lastModStartDate": since_iso,
                "lastModEndDate": until_iso,
                "resultsPerPage": _NVD_PAGE_SIZE,
                "startIndex": start_index,
            }
            resp = await _get_with_retry(client, NVD_CVE_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            vulns = data.get("vulnerabilities") or []
            results.extend(v["cve"] for v in vulns if "cve" in v)

            total = data.get("totalResults", len(results))
            start_index += len(vulns)
            if start_index >= total or not vulns:
                break
            await asyncio.sleep(0.6)  # be polite to NVD's rate limiter across pages

    return results


def _format_android_cve_list(cves: list[dict[str, Any]], since_iso: str, until_iso: str) -> str:
    if not cves:
        return f"No Android-related CVEs modified between {since_iso} and {until_iso} (NVD)."
    lines = [f"{len(cves)} Android-related CVE(s) modified {since_iso} .. {until_iso} (NVD):"]
    for c in cves:
        severity, score = _nvd_cvss(c)
        desc = ""
        for d in c.get("descriptions") or []:
            if d.get("lang") == "en":
                desc = d.get("value", "")
                break
        desc = (desc[:160] + "...") if len(desc) > 160 else desc
        sev_str = f"{severity} {score}" if severity else "unscored"
        lines.append(f"- {c.get('id')} [{sev_str}] modified {c.get('lastModified')}: {desc}")
    return "\n".join(lines)


def build_tools(config: HermesConfig) -> list[Tool]:
    async def cve_lookup(
        cve_id: str | None = None,
        android_recent_days: int | None = None,
    ) -> ToolResult:
        if not cve_id and not android_recent_days:
            return ToolResult.failure(
                "missing_argument",
                "cve_lookup needs either cve_id (e.g. 'CVE-2024-3094') or android_recent_days "
                "(e.g. 7) — neither was given.",
            )

        if cve_id:
            try:
                merged = await fetch_cve(cve_id, config)
            except Exception as e:  # noqa: BLE001 - surface as a tool failure, never crash the loop
                return ToolResult.failure(f"cve_lookup_error: {type(e).__name__}: {e}")
            summary = format_cve_summary(
                merged["cve_id"], merged["osv"], merged["nvd"], merged["errors"]
            )
            if merged["osv"] is None and merged["nvd"] is None:
                return ToolResult.failure("not_found", summary)
            return ToolResult.success(summary)

        try:
            days = int(android_recent_days)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return ToolResult.failure("bad_argument", "android_recent_days must be an integer number of days.")
        if days <= 0:
            return ToolResult.failure("bad_argument", "android_recent_days must be a positive integer.")

        now = datetime.now(timezone.utc)
        since_iso = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000")
        until_iso = now.strftime("%Y-%m-%dT%H:%M:%S.000")
        try:
            cves = await list_recent_android_cves(config, since_iso=since_iso, until_iso=until_iso)
        except httpx.HTTPError as e:
            return ToolResult.failure(f"nvd_error: {type(e).__name__}: {e}")
        return ToolResult.success(_format_android_cve_list(cves, since_iso, until_iso))

    schema = ToolSchema(
        name="cve_lookup",
        description=(
            "Look up a specific CVE by id (queries OSV.dev + NVD, merges into one summary), "
            "OR list recently-modified Android-related CVEs from NVD over the last N days. "
            "Pass exactly one of cve_id / android_recent_days."
        ),
        parameters={
            "type": "object",
            "properties": {
                "cve_id": {
                    "type": "string",
                    "description": "A CVE id to look up, e.g. 'CVE-2024-3094'.",
                },
                "android_recent_days": {
                    "type": "integer",
                    "description": "Instead of cve_id: list Android CVEs NVD modified in the last N days.",
                },
            },
        },
    )
    return [Tool(schema=schema, handler=cve_lookup)]
