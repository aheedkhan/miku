"""One flat `github` tool. Prefers shelling out to the `gh` CLI when it's installed;
falls back to raw GitHub REST calls via httpx using config.github_token as a Bearer token
when it isn't. If neither is available, degrades to a clear, actionable failure instead
of hanging or raising a raw HTTP error.
"""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from typing import Any

import httpx

from hermes.config import HermesConfig
from hermes.tools.base import Tool, ToolResult, ToolSchema

_ACTIONS = ("pr_create", "pr_view", "pr_list", "pr_comment", "issue_view", "issue_list", "issue_comment")

_SSH_RE = re.compile(r"git@github\.com:(?P<owner>[^/]+)/(?P<repo>.+?)(?:\.git)?$")
_HTTPS_RE = re.compile(r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>.+?)(?:\.git)?/?$")

_NOT_CONFIGURED_MSG = (
    "GitHub integration is not available: the `gh` CLI is not installed and no GITHUB_TOKEN is "
    "configured. Install gh (e.g. `sudo dnf install gh` on Fedora, or see https://cli.github.com) "
    "or set GITHUB_TOKEN (or GH_TOKEN) in your environment or .env file."
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


def _gh_args(action: str, repo: str, number: int | None, title: str | None, body: str | None) -> list[str] | None:
    if action == "pr_create":
        args = ["pr", "create", "--repo", repo]
        args += ["--title", title] if title else ["--fill"]
        args += ["--body", body or ""]
        return args
    if action == "pr_view":
        if number is None:
            return None
        return ["pr", "view", str(number), "--repo", repo, "--comments"]
    if action == "pr_list":
        return ["pr", "list", "--repo", repo]
    if action == "pr_comment":
        if number is None or not body:
            return None
        return ["pr", "comment", str(number), "--repo", repo, "--body", body]
    if action == "issue_view":
        if number is None:
            return None
        return ["issue", "view", str(number), "--repo", repo, "--comments"]
    if action == "issue_list":
        return ["issue", "list", "--repo", repo]
    if action == "issue_comment":
        if number is None or not body:
            return None
        return ["issue", "comment", str(number), "--repo", repo, "--body", body]
    return None


async def _rest_call(
    client: httpx.AsyncClient, method: str, url: str, json_body: dict[str, Any] | None = None
) -> httpx.Response:
    return await client.request(method, url, json=json_body)


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


async def _via_rest(
    action: str, repo: str, number: int | None, title: str | None, body: str | None, token: str
) -> ToolResult:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = "https://api.github.com"
    try:
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            if action == "pr_create":
                if not title:
                    return ToolResult.failure("pr_create requires 'title' (REST fallback can't --fill from commits)")
                repo_info = await _rest_call(client, "GET", f"{base}/repos/{repo}")
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
                        "pr_create (REST fallback) needs a pushed feature branch checked out that "
                        f"differs from the repo's default branch ('{base_branch}'); could not infer one."
                    )
                resp = await _rest_call(
                    client, "POST", f"{base}/repos/{repo}/pulls",
                    {"title": title, "body": body or "", "head": head_branch, "base": base_branch},
                )
                if resp.status_code not in (200, 201):
                    return ToolResult.failure(f"pr_create failed: HTTP {resp.status_code}: {resp.text[:500]}")
                return ToolResult.success(_format_issue_like(resp.json()))

            if action == "pr_view":
                if number is None:
                    return ToolResult.failure("pr_view requires 'number'")
                resp = await _rest_call(client, "GET", f"{base}/repos/{repo}/pulls/{number}")
                if resp.status_code != 200:
                    return ToolResult.failure(f"pr_view failed: HTTP {resp.status_code}: {resp.text[:500]}")
                comments_resp = await _rest_call(client, "GET", f"{base}/repos/{repo}/issues/{number}/comments")
                comments = comments_resp.json() if comments_resp.status_code == 200 else []
                return ToolResult.success(_format_issue_like(resp.json()) + "\n\n=== comments ===\n" + _format_comments(comments))

            if action == "pr_list":
                resp = await _rest_call(client, "GET", f"{base}/repos/{repo}/pulls")
                if resp.status_code != 200:
                    return ToolResult.failure(f"pr_list failed: HTTP {resp.status_code}: {resp.text[:500]}")
                prs = resp.json()
                if not prs:
                    return ToolResult.success("(no open pull requests)")
                return ToolResult.success("\n".join(f"#{p['number']} {p['title']} ({p['html_url']})" for p in prs))

            if action == "pr_comment":
                if number is None or not body:
                    return ToolResult.failure("pr_comment requires 'number' and 'body'")
                resp = await _rest_call(client, "POST", f"{base}/repos/{repo}/issues/{number}/comments", {"body": body})
                if resp.status_code not in (200, 201):
                    return ToolResult.failure(f"pr_comment failed: HTTP {resp.status_code}: {resp.text[:500]}")
                return ToolResult.success(f"Comment posted: {resp.json().get('html_url')}")

            if action == "issue_view":
                if number is None:
                    return ToolResult.failure("issue_view requires 'number'")
                resp = await _rest_call(client, "GET", f"{base}/repos/{repo}/issues/{number}")
                if resp.status_code != 200:
                    return ToolResult.failure(f"issue_view failed: HTTP {resp.status_code}: {resp.text[:500]}")
                comments_resp = await _rest_call(client, "GET", f"{base}/repos/{repo}/issues/{number}/comments")
                comments = comments_resp.json() if comments_resp.status_code == 200 else []
                return ToolResult.success(_format_issue_like(resp.json()) + "\n\n=== comments ===\n" + _format_comments(comments))

            if action == "issue_list":
                resp = await _rest_call(client, "GET", f"{base}/repos/{repo}/issues")
                if resp.status_code != 200:
                    return ToolResult.failure(f"issue_list failed: HTTP {resp.status_code}: {resp.text[:500]}")
                issues = [i for i in resp.json() if "pull_request" not in i]
                if not issues:
                    return ToolResult.success("(no open issues)")
                return ToolResult.success("\n".join(f"#{i['number']} {i['title']} ({i['html_url']})" for i in issues))

            if action == "issue_comment":
                if number is None or not body:
                    return ToolResult.failure("issue_comment requires 'number' and 'body'")
                resp = await _rest_call(client, "POST", f"{base}/repos/{repo}/issues/{number}/comments", {"body": body})
                if resp.status_code not in (200, 201):
                    return ToolResult.failure(f"issue_comment failed: HTTP {resp.status_code}: {resp.text[:500]}")
                return ToolResult.success(f"Comment posted: {resp.json().get('html_url')}")

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
    ) -> ToolResult:
        if action not in _ACTIONS:
            return ToolResult.failure(f"unknown_action: '{action}' — expected one of {_ACTIONS}")

        has_gh = shutil.which("gh") is not None
        has_token = bool(config.github_token)

        if not has_gh and not has_token:
            return ToolResult.failure(_NOT_CONFIGURED_MSG)

        resolved_repo = repo or await _infer_repo()
        if not resolved_repo:
            return ToolResult.failure(
                "Could not determine target repo: pass repo=\"owner/repo\" explicitly, or run this "
                "from inside a git checkout with a GitHub 'origin' remote configured."
            )

        if number is not None:
            try:
                number = int(number)
            except (TypeError, ValueError):
                return ToolResult.failure(f"'number' must be an integer, got {number!r}")

        if has_gh:
            args = _gh_args(action, resolved_repo, number, title, body)
            if args is None:
                return ToolResult.failure(f"{action} is missing required arguments (number and/or body)")
            return await _run_gh(args)

        return await _via_rest(action, resolved_repo, number, title, body, config.github_token or "")

    return [
        Tool(
            schema=ToolSchema(
                name="github",
                description=(
                    "GitHub operations: pr_create, pr_view, pr_list, pr_comment, issue_view, "
                    "issue_list, issue_comment. Uses the `gh` CLI if installed, else the GitHub REST "
                    "API with GITHUB_TOKEN. repo defaults to the current directory's 'origin' remote."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": list(_ACTIONS)},
                        "repo": {"type": "string", "description": "owner/repo, inferred from git remote origin if omitted."},
                        "number": {"type": "integer", "description": "PR or issue number, required by *_view/*_comment actions."},
                        "title": {"type": "string", "description": "PR title, for pr_create."},
                        "body": {"type": "string", "description": "Body text, for pr_create/*_comment."},
                    },
                    "required": ["action"],
                },
            ),
            handler=github,
        ),
    ]
