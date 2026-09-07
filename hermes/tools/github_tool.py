"""One flat `github` tool for PRs/issues **and** repo exploration (search, files, releases).

Prefers `gh` CLI when installed; falls back to GitHub REST via GITHUB_TOKEN / unauthenticated
(public read, lower rate limits). Degrades with a clear message if neither works for the action.
"""

from __future__ import annotations

import asyncio
import base64
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from hermes.config import HermesConfig
from hermes.tools.base import Tool, ToolResult, ToolSchema

_ISSUE_ACTIONS = ("pr_create", "pr_view", "pr_list", "pr_comment", "issue_view", "issue_list", "issue_comment")
_EXPLORE_ACTIONS = (
    "repo_view",
    "search_repos",
    "code_search",
    "contents",
    "file_get",
    "release_list",
    "commit_list",
)
_ACTIONS = _ISSUE_ACTIONS + _EXPLORE_ACTIONS

_SSH_RE = re.compile(r"git@github\.com:(?P<owner>[^/]+)/(?P<repo>.+?)(?:\.git)?$")
_HTTPS_RE = re.compile(r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>.+?)(?:\.git)?/?$")

_NOT_CONFIGURED_MSG = (
    "GitHub write/auth actions need the `gh` CLI or GITHUB_TOKEN. "
    "Public read explore actions work without a token (stricter rate limits). "
    "Install gh (https://cli.github.com) or set GITHUB_TOKEN / GH_TOKEN in .env."
)


async def _infer_repo() -> str | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "remote", "get-url", "origin",
            cwd=str(Path.cwd()),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    url = out.decode(errors="replace").strip()
    for rx in (_SSH_RE, _HTTPS_RE):
        m = rx.search(url)
        if m:
            return f"{m.group('owner')}/{m.group('repo')}"
    return None


def _auth_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "hermes-miku",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _run_gh(args: list[str]) -> ToolResult:
    try:
        proc = await asyncio.create_subprocess_exec(
            "gh", *args,
            cwd=str(Path.cwd()),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
    except OSError as e:
        return ToolResult.failure(f"gh_exec_error: {e}")
    if proc.returncode != 0:
        detail = err.decode(errors="replace").strip() or out.decode(errors="replace").strip()
        return ToolResult.failure(f"gh {' '.join(args)} failed: {detail}")
    content = out.decode(errors="replace").strip() or "(no output)"
    return ToolResult.success(content)


def _gh_issue_args(action: str, repo: str, number: int | None, title: str | None, body: str | None) -> list[str] | None:
    if action == "pr_create":
        args = ["pr", "create", "--repo", repo]
        args += ["--title", title] if title else ["--fill"]
        args += ["--body", body or ""]
        return args
    if action == "pr_view":
        return None if number is None else ["pr", "view", str(number), "--repo", repo, "--comments"]
    if action == "pr_list":
        return ["pr", "list", "--repo", repo]
    if action == "pr_comment":
        return None if number is None or not body else ["pr", "comment", str(number), "--repo", repo, "--body", body]
    if action == "issue_view":
        return None if number is None else ["issue", "view", str(number), "--repo", repo, "--comments"]
    if action == "issue_list":
        return ["issue", "list", "--repo", repo]
    if action == "issue_comment":
        return None if number is None or not body else ["issue", "comment", str(number), "--repo", repo, "--body", body]
    return None


def _format_issue_like(data: dict[str, Any]) -> str:
    return (
        f"#{data.get('number')} {data.get('title')}\n"
        f"state: {data.get('state')}  url: {data.get('html_url')}\n"
        f"author: {(data.get('user') or {}).get('login')}\n\n"
        f"{data.get('body') or '(no description)'}"
    )


def _format_comments(comments: list[dict[str, Any]]) -> str:
    if not comments:
        return "(no comments)"
    parts = []
    for c in comments:
        author = (c.get("user") or {}).get("login", "unknown")
        parts.append(f"--- {author} ---\n{c.get('body', '')}")
    return "\n\n".join(parts)


async def _via_rest_issues(
    action: str, repo: str, number: int | None, title: str | None, body: str | None, token: str
) -> ToolResult:
    headers = _auth_headers(token)
    base = "https://api.github.com"
    try:
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            if action == "pr_create":
                if not title:
                    return ToolResult.failure("pr_create requires 'title' (REST fallback can't --fill from commits)")
                repo_info = await client.get(f"{base}/repos/{repo}")
                if repo_info.status_code != 200:
                    return ToolResult.failure(f"could not look up repo {repo}: HTTP {repo_info.status_code}")
                base_branch = repo_info.json().get("default_branch", "main")
                head_proc = await asyncio.create_subprocess_exec(
                    "git", "rev-parse", "--abbrev-ref", "HEAD",
                    cwd=str(Path.cwd()), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                head_out, _ = await head_proc.communicate()
                head_branch = head_out.decode(errors="replace").strip() or None
                if not head_branch or head_branch == base_branch:
                    return ToolResult.failure(
                        "pr_create (REST) needs a feature branch checked out that differs from "
                        f"default ('{base_branch}')."
                    )
                resp = await client.post(
                    f"{base}/repos/{repo}/pulls",
                    json={"title": title, "body": body or "", "head": head_branch, "base": base_branch},
                )
                if resp.status_code not in (200, 201):
                    return ToolResult.failure(f"pr_create failed: HTTP {resp.status_code}: {resp.text[:500]}")
                return ToolResult.success(_format_issue_like(resp.json()))

            if action == "pr_view":
                if number is None:
                    return ToolResult.failure("pr_view requires 'number'")
                resp = await client.get(f"{base}/repos/{repo}/pulls/{number}")
                if resp.status_code != 200:
                    return ToolResult.failure(f"pr_view failed: HTTP {resp.status_code}")
                comments_resp = await client.get(f"{base}/repos/{repo}/issues/{number}/comments")
                comments = comments_resp.json() if comments_resp.status_code == 200 else []
                return ToolResult.success(
                    _format_issue_like(resp.json()) + "\n\n=== comments ===\n" + _format_comments(comments)
                )

            if action == "pr_list":
                resp = await client.get(f"{base}/repos/{repo}/pulls")
                if resp.status_code != 200:
                    return ToolResult.failure(f"pr_list failed: HTTP {resp.status_code}")
                prs = resp.json()
                if not prs:
                    return ToolResult.success("(no open pull requests)")
                return ToolResult.success("\n".join(f"#{p['number']} {p['title']} ({p['html_url']})" for p in prs))

            if action == "pr_comment":
                if number is None or not body:
                    return ToolResult.failure("pr_comment requires 'number' and 'body'")
                resp = await client.post(f"{base}/repos/{repo}/issues/{number}/comments", json={"body": body})
                if resp.status_code not in (200, 201):
                    return ToolResult.failure(f"pr_comment failed: HTTP {resp.status_code}")
                return ToolResult.success(f"Comment posted: {resp.json().get('html_url')}")

            if action == "issue_view":
                if number is None:
                    return ToolResult.failure("issue_view requires 'number'")
                resp = await client.get(f"{base}/repos/{repo}/issues/{number}")
                if resp.status_code != 200:
                    return ToolResult.failure(f"issue_view failed: HTTP {resp.status_code}")
                comments_resp = await client.get(f"{base}/repos/{repo}/issues/{number}/comments")
                comments = comments_resp.json() if comments_resp.status_code == 200 else []
                return ToolResult.success(
                    _format_issue_like(resp.json()) + "\n\n=== comments ===\n" + _format_comments(comments)
                )

            if action == "issue_list":
                resp = await client.get(f"{base}/repos/{repo}/issues")
                if resp.status_code != 200:
                    return ToolResult.failure(f"issue_list failed: HTTP {resp.status_code}")
                issues = [i for i in resp.json() if "pull_request" not in i]
                if not issues:
                    return ToolResult.success("(no open issues)")
                return ToolResult.success("\n".join(f"#{i['number']} {i['title']} ({i['html_url']})" for i in issues))

            if action == "issue_comment":
                if number is None or not body:
                    return ToolResult.failure("issue_comment requires 'number' and 'body'")
                resp = await client.post(f"{base}/repos/{repo}/issues/{number}/comments", json={"body": body})
                if resp.status_code not in (200, 201):
                    return ToolResult.failure(f"issue_comment failed: HTTP {resp.status_code}")
                return ToolResult.success(f"Comment posted: {resp.json().get('html_url')}")

    except httpx.HTTPError as e:
        return ToolResult.failure(f"github_http_error: {e}")

    return ToolResult.failure(f"unknown_action: {action}")


async def _explore(
    action: str,
    *,
    repo: str | None,
    path: str | None,
    query: str | None,
    ref: str | None,
    limit: int,
    token: str | None,
    has_gh: bool,
) -> ToolResult:
    """Repo exploration — prefer gh api when available, else REST."""
    limit = max(1, min(limit, 30))
    headers = _auth_headers(token)

    # gh shortcuts for a few explore actions
    if has_gh and action == "repo_view" and repo:
        return await _run_gh(["repo", "view", repo])
    if has_gh and action == "release_list" and repo:
        return await _run_gh(["release", "list", "--repo", repo, "--limit", str(limit)])
    if has_gh and action == "search_repos" and query:
        return await _run_gh(["search", "repos", query, "--limit", str(limit)])
    if has_gh and action == "code_search" and query:
        args = ["search", "code", query, "--limit", str(limit)]
        if repo:
            args = ["search", "code", f"repo:{repo} {query}", "--limit", str(limit)]
        return await _run_gh(args)

    base = "https://api.github.com"
    try:
        async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
            if action == "repo_view":
                if not repo:
                    return ToolResult.failure("repo_view requires repo=owner/name")
                resp = await client.get(f"{base}/repos/{repo}")
                if resp.status_code != 200:
                    return ToolResult.failure(f"repo_view failed: HTTP {resp.status_code}: {resp.text[:300]}")
                d = resp.json()
                topics = ", ".join(d.get("topics") or []) or "(none)"
                return ToolResult.success(
                    f"{d.get('full_name')} — {d.get('description') or '(no description)'}\n"
                    f"stars={d.get('stargazers_count')} forks={d.get('forks_count')} "
                    f"lang={d.get('language')} default_branch={d.get('default_branch')}\n"
                    f"topics: {topics}\n"
                    f"license: {(d.get('license') or {}).get('spdx_id')}\n"
                    f"url: {d.get('html_url')}\n"
                    f"clone: {d.get('clone_url')}\n"
                    f"pushed_at: {d.get('pushed_at')}"
                )

            if action == "search_repos":
                if not query:
                    return ToolResult.failure("search_repos requires query")
                resp = await client.get(
                    f"{base}/search/repositories",
                    params={"q": query, "per_page": limit, "sort": "stars", "order": "desc"},
                )
                if resp.status_code != 200:
                    return ToolResult.failure(f"search_repos failed: HTTP {resp.status_code}: {resp.text[:300]}")
                items = resp.json().get("items") or []
                if not items:
                    return ToolResult.success("(no repos found)")
                lines = [
                    f"{i.get('full_name')} ★{i.get('stargazers_count')} — {i.get('description') or ''} "
                    f"({i.get('html_url')})"
                    for i in items
                ]
                return ToolResult.success("\n".join(lines))

            if action == "code_search":
                if not query:
                    return ToolResult.failure("code_search requires query")
                q = f"repo:{repo} {query}" if repo else query
                resp = await client.get(
                    f"{base}/search/code",
                    params={"q": q, "per_page": limit},
                )
                if resp.status_code != 200:
                    return ToolResult.failure(
                        f"code_search failed: HTTP {resp.status_code}: {resp.text[:400]}\n"
                        "Tip: code search often needs GITHUB_TOKEN; try file_get/contents on a known path."
                    )
                items = resp.json().get("items") or []
                if not items:
                    return ToolResult.success("(no code hits)")
                lines = []
                for i in items:
                    repo_name = (i.get("repository") or {}).get("full_name", "?")
                    path = i.get("path", "?")
                    url = i.get("html_url", "")
                    lines.append(f"{repo_name}:{path}\n  {url}")
                return ToolResult.success("\n".join(lines))

            if action == "contents":
                if not repo:
                    return ToolResult.failure("contents requires repo=owner/name")
                p = (path or "").lstrip("/")
                url = f"{base}/repos/{repo}/contents/{p}" if p else f"{base}/repos/{repo}/contents"
                params = {"ref": ref} if ref else None
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    return ToolResult.failure(f"contents failed: HTTP {resp.status_code}: {resp.text[:300]}")
                data = resp.json()
                if isinstance(data, dict) and data.get("type") == "file":
                    return ToolResult.success(
                        f"FILE {data.get('path')} ({data.get('size')} bytes)\n"
                        f"download: {data.get('download_url')}\n"
                        f"html: {data.get('html_url')}\n"
                        "Use action=file_get to read contents."
                    )
                if not isinstance(data, list):
                    return ToolResult.failure("unexpected contents response shape")
                lines = []
                for e in data[:limit]:
                    lines.append(f"{e.get('type', '?'):<4} {e.get('path')}  ({e.get('size', 0)} B)")
                return ToolResult.success("\n".join(lines) or "(empty)")

            if action == "file_get":
                if not repo or not path:
                    return ToolResult.failure("file_get requires repo and path")
                p = path.lstrip("/")
                url = f"{base}/repos/{repo}/contents/{quote(p)}"
                params = {"ref": ref} if ref else None
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    return ToolResult.failure(f"file_get failed: HTTP {resp.status_code}: {resp.text[:300]}")
                data = resp.json()
                if data.get("type") != "file":
                    return ToolResult.failure(f"path is not a file (type={data.get('type')}); use contents")
                size = int(data.get("size") or 0)
                if size > 400_000:
                    return ToolResult.failure(
                        f"file too large ({size} bytes). Use download_url in a browser or clone: "
                        f"{data.get('download_url')}"
                    )
                encoding = data.get("encoding")
                content = data.get("content") or ""
                if encoding == "base64":
                    raw = base64.b64decode(content)
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        return ToolResult.failure("binary file — cannot display as text")
                else:
                    text = str(content)
                # Cap what we dump into the model context
                if len(text) > 80_000:
                    text = text[:80_000] + "\n\n…[truncated]"
                return ToolResult.success(
                    f"# {repo}:{p}" + (f"@{ref}" if ref else "") + f"\n\n{text}",
                    display=f"file_get {repo}:{p} ({size} B)",
                )

            if action == "release_list":
                if not repo:
                    return ToolResult.failure("release_list requires repo")
                resp = await client.get(f"{base}/repos/{repo}/releases", params={"per_page": limit})
                if resp.status_code != 200:
                    return ToolResult.failure(f"release_list failed: HTTP {resp.status_code}")
                rels = resp.json()
                if not rels:
                    return ToolResult.success("(no releases)")
                lines = [
                    f"{r.get('tag_name')} — {r.get('name') or ''} ({r.get('published_at')}) {r.get('html_url')}"
                    for r in rels
                ]
                return ToolResult.success("\n".join(lines))

            if action == "commit_list":
                if not repo:
                    return ToolResult.failure("commit_list requires repo")
                params: dict[str, Any] = {"per_page": limit}
                if ref:
                    params["sha"] = ref
                if path:
                    params["path"] = path.lstrip("/")
                resp = await client.get(f"{base}/repos/{repo}/commits", params=params)
                if resp.status_code != 200:
                    return ToolResult.failure(f"commit_list failed: HTTP {resp.status_code}")
                commits = resp.json()
                if not commits:
                    return ToolResult.success("(no commits)")
                lines = []
                for c in commits:
                    sha = (c.get("sha") or "")[:8]
                    msg = ((c.get("commit") or {}).get("message") or "").split("\n", 1)[0]
                    author = ((c.get("commit") or {}).get("author") or {}).get("name", "?")
                    lines.append(f"{sha}  {author}  {msg}")
                return ToolResult.success("\n".join(lines))

    except httpx.HTTPError as e:
        return ToolResult.failure(f"github_http_error: {e}")

    return ToolResult.failure(f"unknown_action: {action}")


def build_tools(config: HermesConfig) -> list[Tool]:
    async def github(
        action: str,
        repo: str | None = None,
        number: int | None = None,
        title: str | None = None,
        body: str | None = None,
        path: str | None = None,
        query: str | None = None,
        ref: str | None = None,
        limit: int = 10,
    ) -> ToolResult:
        if action not in _ACTIONS:
            return ToolResult.failure(f"unknown_action: '{action}' — expected one of {_ACTIONS}")

        has_gh = shutil.which("gh") is not None
        token = config.github_token

        if action in _EXPLORE_ACTIONS:
            resolved = repo
            if action in ("repo_view", "contents", "file_get", "release_list", "commit_list") and not resolved:
                resolved = await _infer_repo()
            return await _explore(
                action,
                repo=resolved,
                path=path,
                query=query,
                ref=ref,
                limit=int(limit or 10),
                token=token,
                has_gh=has_gh,
            )

        # Issue/PR path
        if not has_gh and not token:
            return ToolResult.failure(_NOT_CONFIGURED_MSG)

        resolved_repo = repo or await _infer_repo()
        if not resolved_repo:
            return ToolResult.failure(
                "Could not determine target repo: pass repo=\"owner/repo\", or run inside a "
                "git checkout with a GitHub origin remote."
            )

        if number is not None:
            try:
                number = int(number)
            except (TypeError, ValueError):
                return ToolResult.failure(f"'number' must be an integer, got {number!r}")

        if has_gh:
            args = _gh_issue_args(action, resolved_repo, number, title, body)
            if args is None:
                return ToolResult.failure(f"{action} is missing required arguments (number and/or body)")
            return await _run_gh(args)

        return await _via_rest_issues(action, resolved_repo, number, title, body, token or "")

    return [
        Tool(
            schema=ToolSchema(
                name="github",
                description=(
                    "GitHub: explore repos AND manage PRs/issues. Explore actions: "
                    "repo_view, search_repos, code_search, contents, file_get, release_list, "
                    "commit_list. PR/issue: pr_create, pr_view, pr_list, pr_comment, "
                    "issue_view, issue_list, issue_comment. "
                    "For security research: search_repos/code_search for prior art (Sliver, "
                    "PoCs), then contents/file_get to read implementation. "
                    "repo defaults to current git origin when omitted."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": list(_ACTIONS)},
                        "repo": {"type": "string", "description": "owner/repo"},
                        "number": {"type": "integer", "description": "PR/issue number"},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "path": {"type": "string", "description": "File or directory path for contents/file_get/commit_list"},
                        "query": {"type": "string", "description": "Search query for search_repos/code_search"},
                        "ref": {"type": "string", "description": "Branch/tag/commit for contents/file_get/commit_list"},
                        "limit": {"type": "integer", "description": "Max results (default 10, max 30)"},
                    },
                    "required": ["action"],
                },
            ),
            handler=github,
        ),
    ]
