"""web_search — DuckDuckGo (via the `ddgs` package) by default, or a self-hosted SearXNG
instance if config.search_backend == "searxng" and config.searxng_url is set.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from hermes.config import HermesConfig
from hermes.tools.base import Tool, ToolResult, ToolSchema


def _format_results(results: list[dict[str, str]]) -> str:
    if not results:
        return "(no results)"
    lines = []
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}")
    return "\n\n".join(lines)


def _ddgs_search_sync(query: str, max_results: int) -> list[dict[str, Any]]:
    try:
        from ddgs import DDGS  # current package name
    except ImportError:
        from duckduckgo_search import DDGS  # older package name, same API shape

    with DDGS() as d:
        return list(d.text(query, max_results=max_results))


async def _search_ddgs(query: str, max_results: int) -> ToolResult:
    try:
        raw = await asyncio.to_thread(_ddgs_search_sync, query, max_results)
    except ImportError:
        return ToolResult.failure(
            "web_search backend 'ddgs' is unavailable: neither the `ddgs` nor `duckduckgo_search` "
            "package is installed. Run: pip install ddgs"
        )
    except Exception as e:  # ddgs raises its own exception hierarchy (RatelimitException, etc.)
        return ToolResult.failure(f"web_search (ddgs) failed: {type(e).__name__}: {e}")

    results = [
        {
            "title": r.get("title") or "(untitled)",
            "url": r.get("href") or r.get("url") or "",
            "snippet": r.get("body") or r.get("snippet") or "",
        }
        for r in raw
    ]
    return ToolResult.success(_format_results(results), display=f"web_search: {len(results)} results for {query!r}")


async def _search_searxng(query: str, max_results: int, searxng_url: str) -> ToolResult:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{searxng_url.rstrip('/')}/search",
                params={"q": query, "format": "json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        return ToolResult.failure(f"web_search (searxng at {searxng_url}) failed: {e}")

    raw = (data.get("results") or [])[:max_results]
    results = [
        {
            "title": r.get("title") or "(untitled)",
            "url": r.get("url") or "",
            "snippet": r.get("content") or "",
        }
        for r in raw
    ]
    return ToolResult.success(_format_results(results), display=f"web_search: {len(results)} results for {query!r}")


def build_tools(config: HermesConfig) -> list[Tool]:
    async def web_search(query: str, max_results: int = 5) -> ToolResult:
        query = (query or "").strip()
        if not query:
            return ToolResult.failure("empty_query: no search query given")
        max_results = max(1, min(int(max_results), 25))

        backend = config.search_backend or "ddgs"
        if backend == "searxng":
            if not config.searxng_url:
                return ToolResult.failure(
                    "search_backend is 'searxng' but searxng_url is not set in config.yaml. "
                    "Either set searxng_url, or switch search_backend back to 'ddgs' (key-free default)."
                )
            return await _search_searxng(query, max_results, config.searxng_url)

        return await _search_ddgs(query, max_results)

    return [
        Tool(
            schema=ToolSchema(
                name="web_search",
                description="Search the web (DuckDuckGo by default, or a configured SearXNG instance) and return titles/URLs/snippets.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query."},
                        "max_results": {"type": "integer", "description": "Max number of results, default 5."},
                    },
                    "required": ["query"],
                },
            ),
            handler=web_search,
        ),
    ]
