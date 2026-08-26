"""One flat `git` tool over the real git binary, operating in Path.cwd() — whatever
project directory Hermes was launched from, never a path hardcoded to this repo."""

from __future__ import annotations

import asyncio
from pathlib import Path

from hermes.config import HermesConfig
from hermes.tools.base import Tool, ToolResult, ToolSchema

_ACTIONS = ("status", "diff", "add", "commit", "log")


async def _run_git(args: list[str]) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=str(Path.cwd()),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return 127, "", "git binary not found on PATH"
    out, err = await proc.communicate()
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")


def build_tools(config: HermesConfig) -> list[Tool]:
    async def git(
        action: str,
        staged: bool = False,
        paths: list[str] | None = None,
        message: str | None = None,
        n: int = 10,
    ) -> ToolResult:
        if action not in _ACTIONS:
            return ToolResult.failure(f"unknown_action: '{action}' — expected one of {_ACTIONS}")

        if action == "status":
            args = ["status"]

        elif action == "diff":
            args = ["diff"] + (["--staged"] if staged else [])

        elif action == "add":
            if not paths:
                return ToolResult.failure(
                    "add requires 'paths': a non-empty list of specific files/dirs to stage "
                    "(no implicit `git add -A`/`.` — pass paths explicitly, e.g. paths=['.'] if you "
                    "really mean everything)."
                )
            args = ["add", "--", *paths]

        elif action == "commit":
            if not message:
                return ToolResult.failure("commit requires 'message'")
            args = ["commit", "-m", message]

        else:  # log
            try:
                n_int = max(1, int(n))
            except (TypeError, ValueError):
                n_int = 10
            args = ["log", f"--max-count={n_int}", "--pretty=format:%h - %an, %ar : %s"]

        exit_code, out, err = await _run_git(args)

        if exit_code != 0:
            detail = err.strip() or out.strip() or f"git exited {exit_code}"
            return ToolResult.failure(f"git {action} failed: {detail}", content=f"{out}\n{err}".strip())

        content = out.strip() or "(no output)"
        return ToolResult.success(content, display=f"git {action}: {len(content)} chars")

    return [
        Tool(
            schema=ToolSchema(
                name="git",
                description=(
                    "Run git operations in the current working directory: status, diff (optionally "
                    "--staged), add (specific paths), commit (with a message), or log (last n commits)."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": list(_ACTIONS)},
                        "staged": {"type": "boolean", "description": "For 'diff': show staged changes instead of the working tree."},
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "For 'add': explicit list of paths to stage.",
                        },
                        "message": {"type": "string", "description": "For 'commit': the commit message."},
                        "n": {"type": "integer", "description": "For 'log': number of commits to show, default 10."},
                    },
                    "required": ["action"],
                },
            ),
            handler=git,
        ),
    ]
