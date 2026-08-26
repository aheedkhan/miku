"""shell_exec — the general-purpose shell escape hatch.

Three tiers, in this order of precedence:
  1. DENY   — a small hardcoded set of regexes for genuinely catastrophic commands
              (fork bombs, `rm -rf /`, `mkfs`/`dd` against a whole raw block device).
              Always refused, no override.
  2. ALLOW  — common, safe, read-only commands (ls, cat, grep, find, pwd, echo, whoami,
              ps, `git status`/`diff`/`log`, plain `nmap`) run immediately.
  3. CONFIRM — everything else. This is the user's own authorized pentest/malware-dev
              box, so the unknown tier is confirm-by-default, not deny-by-default:
              unless config.shell_auto_confirm is set, we block on an interactive
              y/N prompt before running.

Every call is logged to <data_dir>/shell_log.jsonl regardless of tier or outcome.

Tier classification here is a best-effort heuristic, not a security boundary — the real
backstop is DENY (hardcoded, always wins) plus CONFIRM being the default for anything not
explicitly recognized as safe. The ALLOW-tier segment splitting on shell operators
(;, &&, ||, |) is regex-based and not quote-aware, so a pathological quoted string could
in principle confuse it; worst realistic case is an allow-eligible command instead getting
routed to CONFIRM, which just costs the user one extra keypress.
"""

from __future__ import annotations

import asyncio
import json
import re
import shlex
import time
from pathlib import Path

from hermes.config import HermesConfig
from hermes.tools.base import Tool, ToolResult, ToolSchema

_MAX_OUTPUT_CHARS = 8000

DENY_PATTERNS: list[re.Pattern[str]] = [
    # Classic bash fork bomb: :(){ :|:& };:
    re.compile(r":\s*\(\)\s*\{\s*:\s*\|\s*:\s*&?\s*\}\s*;\s*:"),
    # dd writing straight to a raw block device
    re.compile(r"(?i)\bdd\b[^;&|\n]*\bof=/dev/(?:[sh]d[a-z]|nvme\d+n\d+|xvd[a-z]|vd[a-z])\b"),
    # mkfs against a whole raw block device
    re.compile(r"(?i)\bmkfs(?:\.\w+)?\b[^;&|\n]*\s/dev/(?:[sh]d[a-z]|nvme\d+n\d+|xvd[a-z]|vd[a-z])\b"),
    # rm -rf / (or -fr, or split -r -f / -f -r, or --recursive --force), targeting / or /*
    re.compile(
        r"(?i)\brm\b[^;&|\n]*"
        r"(?:-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*"
        r"|-r\s+-f|-f\s+-r|-r\s+--force|--force\s+-r"
        r"|--recursive\s+--force|--force\s+--recursive)"
        r"[^;&|\n]*\s/+(?:\s|$|\*)"
    ),
    re.compile(r"(?i)\brm\b[^;&|\n]*--no-preserve-root"),
]

ALLOW_COMMANDS = {"ls", "cat", "pwd", "echo", "whoami", "ps", "find", "grep", "head", "tail", "wc", "file", "which"}
NMAP_RISKY_SUBSTRINGS = ("--script=dos", "--script dos", "--script=exploit", "--script exploit",
                          "--script=brute", "--script brute")

_SPLIT_RE = re.compile(r"&&|\|\||[;&|]")


def _split_segments(command: str) -> list[str]:
    return [s.strip() for s in _SPLIT_RE.split(command) if s.strip()]


def _segment_allowed(segment: str) -> bool:
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return False  # unbalanced quotes etc — don't guess, fall through to confirm
    if not tokens:
        return False
    head = tokens[0]
    if head == "sudo":
        return False  # privilege escalation always goes through confirm, never auto-allow
    if head == "git":
        return len(tokens) > 1 and tokens[1] in ("status", "diff", "log")
    if head == "nmap":
        joined = segment.lower()
        return not any(bad in joined for bad in NMAP_RISKY_SUBSTRINGS)
    return head in ALLOW_COMMANDS


def _classify(command: str) -> tuple[str, str]:
    """Returns (tier, reason)."""
    for pat in DENY_PATTERNS:
        if pat.search(command):
            return "deny", f"matched deny pattern: {pat.pattern}"

    segments = _split_segments(command)
    if segments and all(_segment_allowed(seg) for seg in segments):
        return "allow", "all segments are on the read-only allow list"

    return "confirm", "not recognized as safe or catastrophic"


def _truncate(text: str) -> str:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    return text[:_MAX_OUTPUT_CHARS] + f"\n... [truncated, {len(text) - _MAX_OUTPUT_CHARS} more chars]"


def _log(config: HermesConfig, entry: dict) -> None:
    try:
        config.data_dir.mkdir(parents=True, exist_ok=True)
        log_path = config.data_dir / "shell_log.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # logging must never take down the actual tool call


def build_tools(config: HermesConfig) -> list[Tool]:
    async def shell_exec(command: str, cwd: str | None = None) -> ToolResult:
        command = (command or "").strip()
        if not command:
            return ToolResult.failure("empty_command: no command given")

        if cwd:
            p = Path(cwd).expanduser()
            resolved_cwd = p if p.is_absolute() else Path.cwd() / p
        else:
            resolved_cwd = Path.cwd()

        tier, reason = _classify(command)
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "command": command,
            "cwd": str(resolved_cwd),
            "tier": tier,
        }

        if tier == "deny":
            entry["outcome"] = "denied"
            _log(config, entry)
            return ToolResult.failure(
                f"Refused: this command matches a hardcoded catastrophic-command pattern ({reason}). "
                "Not running it."
            )

        if not resolved_cwd.is_dir():
            entry["outcome"] = "bad_cwd"
            _log(config, entry)
            return ToolResult.failure(f"bad_cwd: {resolved_cwd} is not a directory")

        if tier == "confirm" and not config.shell_auto_confirm:
            answer = await asyncio.to_thread(input, f"Run: {command}\n[y/N] ")
            if answer.strip().lower() not in ("y", "yes"):
                entry["outcome"] = "declined"
                _log(config, entry)
                return ToolResult.failure("User declined to confirm this shell command; not run.")
            entry["user_confirmed"] = True

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(resolved_cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await proc.communicate()
            exit_code = proc.returncode
        except OSError as e:
            entry["outcome"] = "exec_error"
            entry["error"] = str(e)
            _log(config, entry)
            return ToolResult.failure(f"exec_error: failed to start command: {e}")

        stdout = _truncate(stdout_b.decode(errors="replace"))
        stderr = _truncate(stderr_b.decode(errors="replace"))

        entry["outcome"] = "executed"
        entry["exit_code"] = exit_code
        _log(config, entry)

        content = (
            f"$ {command}\n(cwd: {resolved_cwd}, tier: {tier})\nexit code: {exit_code}\n\n"
            f"--- stdout ---\n{stdout or '(empty)'}\n\n--- stderr ---\n{stderr or '(empty)'}"
        )
        return ToolResult.success(content, display=f"$ {command} -> exit {exit_code}")

    return [
        Tool(
            schema=ToolSchema(
                name="shell_exec",
                description=(
                    "Run a shell command in the current working directory (or a given cwd). "
                    "Catastrophic commands (fork bombs, `rm -rf /`, whole-disk mkfs/dd) are always "
                    "refused. Unrecognized commands may prompt the user for confirmation before running."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The shell command to run."},
                        "cwd": {
                            "type": "string",
                            "description": "Optional working directory, absolute or relative to cwd. Defaults to the current directory.",
                        },
                    },
                    "required": ["command"],
                },
            ),
            handler=shell_exec,
        ),
    ]
