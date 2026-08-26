"""Filesystem tools: read_file, write_file, edit_file, list_dir, grep.

Mirrors the shape of Claude Code's own Read/Edit/Grep tools deliberately — small local
models already have some exposure to that convention. All paths are resolved relative to
Path.cwd() at call time (never a path hardcoded to this repo), so Hermes operates on
whatever project the user launched it from, unless an absolute path is given.
"""

from __future__ import annotations

import asyncio
import fnmatch
import os
import re
import shutil
from pathlib import Path

from hermes.config import HermesConfig
from hermes.tools.base import Tool, ToolResult, ToolSchema

# Directories we never want to wade into for a recursive grep — matches the spirit of
# config.DEFAULT_PROJECT_EXCLUDE without importing it (that list is glob-pattern shaped,
# this is a plain directory-name skip-set for os.walk pruning).
_SKIP_DIRS = {".git", "node_modules", "build", "out", ".venv", "venv", "vendor", "dist", "__pycache__"}

_MAX_READ_CHARS = 300_000  # guard against a single read_file blowing the whole context window
_MAX_GREP_MATCHES = 200


def _resolve(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def build_tools(config: HermesConfig) -> list[Tool]:
    async def read_file(path: str) -> ToolResult:
        target = _resolve(path)
        if not target.exists():
            return ToolResult.failure(f"not_found: {target} does not exist")
        if target.is_dir():
            return ToolResult.failure(f"is_a_directory: {target} is a directory, not a file")
        try:
            data = target.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return ToolResult.failure(f"read_error: {e}")
        truncated = False
        if len(data) > _MAX_READ_CHARS:
            data = data[:_MAX_READ_CHARS]
            truncated = True
        numbered = "\n".join(f"{i + 1}\t{line}" for i, line in enumerate(data.splitlines()))
        if truncated:
            numbered += f"\n... [truncated at {_MAX_READ_CHARS} chars, file is larger]"
        return ToolResult.success(numbered, display=f"Read {target} ({len(data)} chars)")

    async def write_file(path: str, content: str) -> ToolResult:
        target = _resolve(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as e:
            return ToolResult.failure(f"write_error: {e}")
        return ToolResult.success(
            f"Wrote {len(content)} chars to {target}", display=f"Wrote {target} ({len(content)} chars)"
        )

    async def edit_file(path: str, old_string: str, new_string: str) -> ToolResult:
        target = _resolve(path)
        if not target.exists():
            return ToolResult.failure(f"not_found: {target} does not exist")
        if target.is_dir():
            return ToolResult.failure(f"is_a_directory: {target} is a directory, not a file")
        if old_string == new_string:
            return ToolResult.failure("no_op: old_string and new_string are identical")
        try:
            data = target.read_text(encoding="utf-8")
        except OSError as e:
            return ToolResult.failure(f"read_error: {e}")

        count = data.count(old_string)
        if count == 0:
            return ToolResult.failure(f"not_found: old_string does not appear in {target}")
        if count > 1:
            return ToolResult.failure(
                f"ambiguous: old_string appears {count} times in {target} — "
                "include more surrounding context so it matches exactly once"
            )

        new_data = data.replace(old_string, new_string, 1)
        try:
            target.write_text(new_data, encoding="utf-8")
        except OSError as e:
            return ToolResult.failure(f"write_error: {e}")
        return ToolResult.success(f"Edited {target} (1 replacement)")

    async def list_dir(path: str = ".") -> ToolResult:
        target = _resolve(path)
        if not target.exists():
            return ToolResult.failure(f"not_found: {target} does not exist")
        if not target.is_dir():
            return ToolResult.failure(f"not_a_directory: {target} is not a directory")
        try:
            entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError as e:
            return ToolResult.failure(f"list_error: {e}")

        lines = []
        for entry in entries:
            try:
                if entry.is_dir():
                    lines.append(f"{entry.name}/")
                else:
                    size = entry.stat().st_size
                    lines.append(f"{entry.name}\t{size}B")
            except OSError:
                lines.append(f"{entry.name}\t(stat failed)")
        content = "\n".join(lines) if lines else "(empty directory)"
        return ToolResult.success(content, display=f"{target}: {len(entries)} entries")

    async def grep(pattern: str, path: str = ".", glob: str | None = None) -> ToolResult:
        target = _resolve(path)
        if not target.exists():
            return ToolResult.failure(f"not_found: {target} does not exist")

        if shutil.which("rg"):
            return await _grep_ripgrep(pattern, target, glob)
        return await _grep_python(pattern, target, glob)

    async def _grep_ripgrep(pattern: str, target: Path, glob: str | None) -> ToolResult:
        args = ["rg", "-n", "--no-heading", "--color=never"]
        if glob:
            args += ["--glob", glob]
        args += [pattern, str(target)]
        try:
            proc = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            out, err = await proc.communicate()
        except OSError as e:
            return ToolResult.failure(f"rg_exec_error: {e}")

        if proc.returncode == 1:  # rg: no matches found — not an error
            return ToolResult.success("(no matches)")
        if proc.returncode not in (0, 1):
            return ToolResult.failure(f"rg exited {proc.returncode}: {err.decode(errors='replace').strip()}")

        lines = out.decode(errors="replace").splitlines()
        truncated = len(lines) > _MAX_GREP_MATCHES
        lines = lines[:_MAX_GREP_MATCHES]
        content = "\n".join(lines) if lines else "(no matches)"
        if truncated:
            content += f"\n... [truncated at {_MAX_GREP_MATCHES} matches]"
        return ToolResult.success(content)

    async def _grep_python(pattern: str, target: Path, glob: str | None) -> ToolResult:
        try:
            rx = re.compile(pattern)
        except re.error as e:
            return ToolResult.failure(f"bad_pattern: {e}")

        matches: list[str] = []
        truncated = False

        def _scan_file(fp: Path) -> bool:
            """Returns True if the match cap was hit (caller should stop)."""
            nonlocal truncated
            if glob and not fnmatch.fnmatch(fp.name, glob):
                return False
            try:
                text = fp.read_text(encoding="utf-8", errors="strict")
            except (OSError, UnicodeDecodeError):
                return False  # skip binary/unreadable files, same spirit as rg's default behavior
            for lineno, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    try:
                        rel = fp.relative_to(Path.cwd())
                    except ValueError:
                        rel = fp
                    matches.append(f"{rel}:{lineno}:{line}")
                    if len(matches) >= _MAX_GREP_MATCHES:
                        truncated = True
                        return True
            return False

        if target.is_file():
            _scan_file(target)
        else:
            for root, dirnames, filenames in os.walk(target):
                dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
                stop = False
                for fname in filenames:
                    if _scan_file(Path(root) / fname):
                        stop = True
                        break
                if stop:
                    break

        content = "\n".join(matches) if matches else "(no matches)"
        if truncated:
            content += f"\n... [truncated at {_MAX_GREP_MATCHES} matches]"
        return ToolResult.success(content)

    return [
        Tool(
            schema=ToolSchema(
                name="read_file",
                description="Read a text file's contents, with line numbers, relative to the current working directory.",
                parameters={
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "File path, absolute or relative to cwd."}},
                    "required": ["path"],
                },
            ),
            handler=read_file,
        ),
        Tool(
            schema=ToolSchema(
                name="write_file",
                description="Write (create or overwrite) a text file, creating parent directories as needed.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path, absolute or relative to cwd."},
                        "content": {"type": "string", "description": "Full file content to write."},
                    },
                    "required": ["path", "content"],
                },
            ),
            handler=write_file,
        ),
        Tool(
            schema=ToolSchema(
                name="edit_file",
                description=(
                    "Replace an exact, unique substring in a file. old_string must appear exactly once — "
                    "include enough surrounding context to disambiguate it."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path, absolute or relative to cwd."},
                        "old_string": {"type": "string", "description": "Exact text to find, must be unique in the file."},
                        "new_string": {"type": "string", "description": "Replacement text."},
                    },
                    "required": ["path", "old_string", "new_string"],
                },
            ),
            handler=edit_file,
        ),
        Tool(
            schema=ToolSchema(
                name="list_dir",
                description="List the immediate contents of a directory (not recursive). Directories first, then files.",
                parameters={
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "Directory path, defaults to cwd."}},
                    "required": [],
                },
            ),
            handler=list_dir,
        ),
        Tool(
            schema=ToolSchema(
                name="grep",
                description=(
                    "Regex search over a file or directory tree. Uses ripgrep if installed, "
                    "else a pure-Python fallback."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Regular expression to search for."},
                        "path": {"type": "string", "description": "File or directory to search, defaults to cwd."},
                        "glob": {"type": "string", "description": "Optional filename glob filter, e.g. '*.py'."},
                    },
                    "required": ["pattern"],
                },
            ),
            handler=grep,
        ),
    ]
