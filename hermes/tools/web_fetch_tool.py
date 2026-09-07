"""web_fetch — pull a URL and return readable text (HTML stripped) for advisories,
docs, and raw.githubusercontent.com files. Complements web_search.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from hermes.config import HermesConfig
from hermes.tools.base import Tool, ToolResult, ToolSchema

_MAX_BYTES = 600_000
_MAX_CHARS = 60_000
_TIMEOUT = 25.0

_BLOCKED_HOST_SUFFIXES = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip()
        if text:
            self._chunks.append(text + " ")

    def text(self) -> str:
        raw = "".join(self._chunks)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 — fall back to crude strip
        return re.sub(r"<[^>]+>", " ", html)
    return parser.text()


def _allowed_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except Exception:
        return "invalid URL"
    if parsed.scheme not in {"http", "https"}:
        return "only http/https URLs are allowed"
    host = (parsed.hostname or "").lower()
    if not host:
        return "URL missing host"
    if host in _BLOCKED_HOST_SUFFIXES or host.endswith(".local"):
        return "refusing to fetch local/loopback hosts"
    return None


def build_tools(config: HermesConfig) -> list[Tool]:
    del config  # reserved for future proxy / allowlist config

    async def web_fetch(url: str, max_chars: int = 20000) -> ToolResult:
        url = (url or "").strip()
        if not url:
            return ToolResult.failure("empty_url")
        reason = _allowed_url(url)
        if reason:
            return ToolResult.failure(reason)

        max_chars = max(1000, min(int(max_chars or 20000), _MAX_CHARS))
        headers = {
            "User-Agent": "hermes-miku-research/0.1 (+local security research agent)",
            "Accept": "text/html,application/xhtml+xml,text/plain,application/json;q=0.9,*/*;q=0.8",
        }
        try:
            async with httpx.AsyncClient(
                headers=headers, timeout=_TIMEOUT, follow_redirects=True
            ) as client:
                resp = await client.get(url)
        except httpx.HTTPError as e:
            return ToolResult.failure(f"web_fetch failed: {type(e).__name__}: {e}")

        if resp.status_code >= 400:
            return ToolResult.failure(f"HTTP {resp.status_code} for {url}")

        raw = resp.content[:_MAX_BYTES]
        ctype = (resp.headers.get("content-type") or "").lower()
        try:
            text = raw.decode(resp.encoding or "utf-8", errors="replace")
        except Exception:
            text = raw.decode("utf-8", errors="replace")

        if "html" in ctype or text.lstrip().lower().startswith("<!doctype html") or text.lstrip().lower().startswith("<html"):
            text = _html_to_text(text)
        # JSON/plain left as-is

        truncated = False
        if len(text) > max_chars:
            text = text[:max_chars]
            truncated = True

        footer = f"\n\n---\nsource: {resp.url}\ncontent-type: {ctype or 'unknown'}"
        if truncated:
            footer += f"\ntruncated_to: {max_chars} chars"
        return ToolResult.success(
            text + footer,
            display=f"web_fetch {resp.url} ({len(text)} chars)",
        )

    return [
        Tool(
            schema=ToolSchema(
                name="web_fetch",
                description=(
                    "Fetch a URL and return readable text (HTML stripped). Use after web_search "
                    "to read advisories, docs, blog posts, or raw.githubusercontent.com files. "
                    "Prefer github file_get for repo files when you know owner/repo/path."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "http(s) URL to fetch"},
                        "max_chars": {
                            "type": "integer",
                            "description": "Max characters to return (default 20000, max 60000)",
                        },
                    },
                    "required": ["url"],
                },
            ),
            handler=web_fetch,
        )
    ]
