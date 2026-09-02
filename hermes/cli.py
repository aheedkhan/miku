"""The REPL entrypoint: wires config, the Ollama client, the RAG store/retriever/ingest
pipeline, every tool module, the persona, and the main Agent together, then runs an
interactive chat loop with a handful of slash commands. Both `hermes` (the console script)
and `python -m hermes` land here.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from hermes.agents.subagent import spawn_subagent as _spawn_subagent_impl
from hermes.config import DEFAULT_PROJECT_EXCLUDE, DEFAULT_PROJECT_INCLUDE, HermesConfig, load_config
from hermes.core.agent_loop import Agent, StreamEvent
from hermes.core.concurrency import InferenceGate
from hermes.core.context_manager import ContextManager
from hermes.core.llm_client import OllamaClient
from hermes.core.tool_strategy import AutoToolStrategy
from hermes.persona.loader import load_banner, load_system_prompt
from hermes.skills import discover_skills, format_skill_index
from hermes.rag.daily_refresh import run_daily_refresh
from hermes.rag.scheduler import refresh_is_due, run_refresh_locked, start_rag_scheduler
from hermes.rag.embeddings import EmbeddingClient
from hermes.rag.fetch_references import REFERENCE_SOURCES, fetch_all, ingest_references
from hermes.rag.ingest import IngestPipeline, scan_dir
from hermes.rag.retriever import RAGRetriever
from hermes.rag.store import VectorStore
from hermes.tools import (
    android_tool,
    cve_tool,
    fs_tools,
    git_tool,
    github_tool,
    malware_bazaar_tool,
    rag_tool,
    shell_tool,
    skill_tool,
    subagent_tool,
    web_search_tool,
)
from hermes.tools.registry import ToolRegistry

DIM = 768  # nomic-embed-text's dimensionality (verified live) — VectorStore self-corrects
# from whatever's already on disk if a different-dimension embed model was used instead.

_DIMMED = "\033[2m{}\033[0m"
_RED = "\033[31m{}\033[0m"


def _set_terminal_title(title: str) -> None:
    """Set the terminal tab/window title (OSC 0 — works in most modern terminals)."""
    print(f"\033]0;{title}\007", end="", flush=True)


_WIFU_NAME_RE = re.compile(r"\bmiku\b", re.IGNORECASE)
_WIFU_STRETCH_RE = re.compile(r"(.)\1{2,}")
_WIFU_ELONGATED_HI_RE = re.compile(r"\bh+i{2,}\b", re.IGNORECASE)
_WIFU_ELONGATED_HEY_RE = re.compile(r"\bhey{2,}\b", re.IGNORECASE)
_WIFU_ELONGATED_HELLO_RE = re.compile(r"\bhe+\w*l+\w*o+\w*\b", re.IGNORECASE)

_WIFU_NUDGE = (
    "[Wifu mode ON for this turn: aheedi/heedi, chaotic romantic energy, emoji flood; "
    "thinking = creative inner voice, not a guideline audit; "
    "NEW flirt joke/pun/gotcha every time — never reuse lines from prior turns or persona examples.]"
)


def _has_wifu_cue(text: str) -> bool:
    """Name call or stretched greeting (hiiii, heyyyy, hehllloooo, …) → wifu."""
    if _WIFU_NAME_RE.search(text):
        return True
    if _WIFU_ELONGATED_HI_RE.search(text) or _WIFU_ELONGATED_HEY_RE.search(text):
        return True
    hello = _WIFU_ELONGATED_HELLO_RE.search(text)
    return bool(hello and _WIFU_STRETCH_RE.search(hello.group(0)))


def _prepare_user_turn(line: str) -> str:
    """Runtime nudge for wifu cues — backs up persona triggers the model sometimes ignores."""
    if _has_wifu_cue(line):
        return f"{line}\n\n{_WIFU_NUDGE}"
    return line

MIKU_COLOR = "#3DC5C9"
MIKU_BG = "#123536"  # dark teal -- bright teal text stays readable on top of it
USER_COLOR = "#FAF2EF"
USER_BG = "#2B2A28"  # dark warm gray -- distinct from Miku's bg, same readability logic

MIKU_QUOTES = [
    "Segfaults are just the universe asking for a stack trace.",
    "root is a responsibility, not a flex.",
    "grep first, panic later.",
    "Every 'quick fix' is a future incident report.",
    "The bug is always in the last place you look — mostly because you stop looking there.",
    "Read the man page. Then read it again.",
    "If it's not reproducible, it's not fixed.",
    "Compiles doesn't mean correct.",
    "The best exploit is the one you understand completely, not the one that just works.",
    "Documentation is a love letter to your future self.",
    "A watched build never finishes; an unwatched one always fails.",
    "Ctrl+Z is a time machine. Use it wisely.",
]


def _read_specs_fallback() -> str:
    """Bare /proc-based CPU/RAM/GPU one-liner -- used only if fastfetch isn't installed."""
    cpu = "n/a"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    cores = os.cpu_count() or 0

    ram = "n/a"
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                kb = int(line.split()[1])
                ram = f"{kb / 1024 / 1024:.0f}GB"
                break
    except (OSError, ValueError, IndexError):
        pass

    gpu = "n/a"
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0 and out.stdout.strip():
            gpu = out.stdout.strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError):
        pass

    return f"{cpu} ({cores}C) · {ram} RAM · {gpu}"


def _read_hw_lines() -> list[str]:
    """OS/host/hardware info for the startup panel, sourced from fastfetch (JSON, no logo
    -- Miku's own art already fills that role) so it's real, current info rather than
    hand-parsed guesses. Falls back to a bare one-liner if fastfetch isn't installed."""
    try:
        out = subprocess.run(
            ["fastfetch", "--format", "json", "--logo", "none"],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(out.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError):
        return [_read_specs_fallback()]

    by_type = {item.get("type"): item.get("result") for item in data if item.get("result") is not None}
    lines: list[str] = []

    lines.append("mania0day")

    os_info = by_type.get("OS")
    if os_info:
        lines.append(f"OS      {os_info.get('prettyName', 'n/a')}")

    cpu = by_type.get("CPU")
    if cpu:
        freq = (cpu.get("frequency") or {}).get("max")
        freq_str = f" @ {freq / 1000:.2f}GHz" if freq else ""
        logical = (cpu.get("cores") or {}).get("logical", "?")
        lines.append(f"CPU     {cpu.get('cpu', 'n/a')} ({logical}){freq_str}")

    gpus = by_type.get("GPU") or []
    if gpus:
        gpu = gpus[0]
        label = f"{gpu.get('vendor', '')} {gpu.get('name', 'n/a')}".strip()
        lines.append(f"GPU     {label}")

    return lines or [_read_specs_fallback()]


_last_cpu_jiffies: tuple[int, int] | None = None  # (idle, total) -- for delta-based CPU%


def _sample_cpu_percent() -> float | None:
    """Instantaneous CPU% via /proc/stat deltas (classic top/htop technique) -- returns
    None on the very first call (needs two samples) or if /proc/stat is unreadable."""
    global _last_cpu_jiffies
    try:
        fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        values = [int(v) for v in fields]
    except (OSError, ValueError, IndexError):
        return None
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    prev = _last_cpu_jiffies
    _last_cpu_jiffies = (idle, total)
    if prev is None:
        return None
    prev_idle, prev_total = prev
    total_delta = total - prev_total
    idle_delta = idle - prev_idle
    if total_delta <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (1 - idle_delta / total_delta)))


def _read_cpu_temp() -> str | None:
    """CPU package temp -- prefers the x86_pkg_temp thermal zone (the actual CPU package
    sensor on Intel), falls back to `sensors` (lm_sensors) output if that zone is absent."""
    try:
        for zone in Path("/sys/class/thermal").glob("thermal_zone*"):
            type_path = zone / "type"
            if type_path.is_file() and type_path.read_text().strip() == "x86_pkg_temp":
                temp_c = int((zone / "temp").read_text().strip()) / 1000
                return f"{temp_c:.0f}°C"
    except (OSError, ValueError):
        pass
    try:
        out = subprocess.run(["sensors", "-u"], capture_output=True, text=True, timeout=2)
        if out.returncode == 0:
            lines = out.stdout.splitlines()
            for i, line in enumerate(lines):
                if any(k in line for k in ("Package id 0", "Tctl", "Tdie")):
                    for follow in lines[i:i + 3]:
                        if "_input" in follow:
                            return f"{float(follow.split(':')[1].strip()):.0f}°C"
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass
    return None


def _read_live_stats() -> list[str]:
    """btop-style live readout: CPU%/temp, RAM used/total, GPU%/mem/temp, battery, uptime.
    All cheap targeted reads (no fastfetch) -- safe to call on a ~1.5s timer."""
    lines: list[str] = []

    cpu_pct = _sample_cpu_percent()
    cpu_temp = _read_cpu_temp()
    if cpu_pct is not None or cpu_temp is not None:
        pct_str = f"{cpu_pct:.0f}%" if cpu_pct is not None else "…"
        temp_str = f" · {cpu_temp}" if cpu_temp else ""
        lines.append(f"CPU     {pct_str}{temp_str}")

    try:
        mem: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            if key in ("MemTotal", "MemAvailable"):
                mem[key] = int(rest.split()[0])
        if "MemTotal" in mem and "MemAvailable" in mem:
            used_gib = (mem["MemTotal"] - mem["MemAvailable"]) / 1024 / 1024
            total_gib = mem["MemTotal"] / 1024 / 1024
            lines.append(f"RAM     {used_gib:.1f}GiB / {total_gib:.1f}GiB")
    except (OSError, ValueError):
        pass

    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0 and out.stdout.strip():
            util, mem_used, mem_total, temp = (p.strip() for p in out.stdout.strip().splitlines()[0].split(","))
            lines.append(f"GPU     {util}% · {mem_used}/{mem_total}MiB · {temp}°C")
    except (OSError, subprocess.SubprocessError, ValueError):
        pass

    try:
        for bat_dir in sorted(Path("/sys/class/power_supply").glob("BAT*")):
            capacity = (bat_dir / "capacity").read_text().strip()
            status = (bat_dir / "status").read_text().strip()
            battery_str = f"{capacity}% [{status}]"
            break
        else:
            battery_str = None
    except OSError:
        battery_str = None

    uptime_str = None
    try:
        uptime_s = float(Path("/proc/uptime").read_text().split()[0])
        hours, rem = divmod(int(uptime_s), 3600)
        mins = rem // 60
        uptime_str = f"{hours}h {mins}m"
    except (OSError, ValueError, IndexError):
        pass

    if battery_str or uptime_str:
        bits = []
        if battery_str:
            bits.append(f"Bat {battery_str}")
        if uptime_str:
            bits.append(f"Up {uptime_str}")
        lines.append("        " + " · ".join(bits))

    return lines


HELP_TEXT = """Commands:
  /model [name-or-role]        show/switch the active model (role name like "code", or a raw model tag)
  /compact                     manually compact the conversation history now
  /ingest [path]                ingest a file or directory into RAG (defaults to workspace/knowledge_dir)
  /refresh-cve, /refresh        run RAG refresh now (CVEs, malware intel, workspace, projects, references)
  /rag-status                   show RAG store stats and last refresh time
  /fetch-references [name]     one-time fetch of Win32 API / Linux kernel / MITRE ATT&CK corpora, then ingest them
  /subagent <role> <task>      spawn a scoped sub-agent directly (roles: researcher, reviewer, pentest_runner, general)
  /skills                       list available skills (name + description)
  /skill <name>                 print a skill's full playbook
  /help                         this message
  /quit, /exit                  leave

Learning: use rag_query to search prior work; rag_remember to save durable facts mid-chat.
Auto-refresh runs every few hours while Miku is open (see rag_refresh_interval_hours in config).
CLI: hermes workspace index | status | search | refresh
"""


def _git_branch(cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _build_tool_registry(
    config: HermesConfig,
    retriever: RAGRetriever,
    ingest: IngestPipeline,
    spawn_fn: Any,
) -> ToolRegistry:
    registry = ToolRegistry()
    for module in (
        fs_tools, shell_tool, git_tool, github_tool,
        web_search_tool, cve_tool, malware_bazaar_tool, android_tool,
    ):
        registry.register_all(module.build_tools(config))
    registry.register_all(rag_tool.build_tools(retriever, ingest))
    registry.register_all(subagent_tool.build_tools(spawn_fn))
    registry.register_all(skill_tool.build_tools(config))
    return registry


class HermesREPL:
    def __init__(self, config: HermesConfig):
        self.config = config
        self.llm = OllamaClient(config.ollama_host, keep_alive=config.ollama_keep_alive)
        max_concurrent = int(config.section("concurrency").get("max_concurrent", 1))
        self.gate = InferenceGate(max_concurrent=max_concurrent)

        embed_profile = config.model("embed")
        self.embedder = EmbeddingClient(self.llm, model=embed_profile.name)
        self.store = VectorStore(config.rag_dir, dim=DIM)
        self.retriever = RAGRetriever(self.embedder, self.store)
        self.ingest = IngestPipeline(self.embedder, self.store)

        async def spawn_fn(role: str, task: str, extra_context: str | None = None) -> str:
            return await _spawn_subagent_impl(
                role, task,
                llm=self.llm, tools=self.registry, config=self.config,
                gate=self.gate, extra_context=extra_context,
            )

        self._spawn_fn = spawn_fn
        self.registry = _build_tool_registry(config, self.retriever, self.ingest, spawn_fn)
        self._rag_refresh_lock = asyncio.Lock()
        self._rag_scheduler_task: asyncio.Task | None = None

        self.skills = discover_skills(config.skills_dir)
        # Computed once -- static (OS/kernel/CPU model/GPU model don't change at runtime),
        # unlike _read_live_stats() which the TUI re-samples on a timer.
        self._static_hw_lines = _read_hw_lines()
        self._quote = random.choice(MIKU_QUOTES)

        cwd = Path.cwd()
        branch = _git_branch(cwd)
        extra_context = f"Current working directory: {cwd}"
        if branch:
            extra_context += f" (git branch: {branch})"
        if self.skills:
            extra_context += (
                f"\n\nAvailable skills (use the use_skill tool to load one's full playbook):\n"
                f"{format_skill_index(self.skills)}"
            )
        chunk_count = self._rag_chunk_count()
        extra_context += (
            f"\n\nRAG memory: {chunk_count} indexed chunk(s) under {config.knowledge_dir}. "
            "Before re-researching, call rag_query. After learning something durable, call "
            "rag_remember or save markdown under workspace/ (auto-indexed on refresh)."
        )

        model_profile = config.model("default")
        fast_profile = config.model("fast")
        self.strategy = AutoToolStrategy(cache_path=config.tool_strategy_cache_path)
        self.context = ContextManager(num_ctx=model_profile.num_ctx)
        self.agent = Agent(
            llm=self.llm,
            model=model_profile.name,
            num_ctx=model_profile.num_ctx,
            system_prompt=load_system_prompt(extra_context=extra_context),
            tools=self.registry,
            strategy=self.strategy,
            gate=self.gate,
            context=self.context,
            summarizer_model=fast_profile.name,
            summarizer_num_ctx=fast_profile.num_ctx,
        )

    async def aclose(self) -> None:
        if self._rag_scheduler_task is not None:
            self._rag_scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._rag_scheduler_task
        self.store.close()
        await self.llm.aclose()

    def _rag_chunk_count(self) -> int:
        row = self.store._conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE deleted = 0"
        ).fetchone()
        return int(row[0]) if row else 0

    def _rag_status_lines(self) -> list[str]:
        rows = self.store._conn.execute(
            "SELECT source_type, COUNT(*) FROM chunks WHERE deleted = 0 GROUP BY source_type ORDER BY source_type"
        ).fetchall()
        lines = [
            f"RAG dir: {self.config.rag_dir}",
            f"Workspace: {self.config.knowledge_dir}",
            f"Total chunks: {self._rag_chunk_count()}",
        ]
        for source_type, count in rows:
            lines.append(f"  {source_type}: {count}")
        from hermes.rag.scheduler import _read_last_refresh

        last = _read_last_refresh(self.config)
        if last:
            lines.append(f"Last refresh: {last.isoformat(timespec='minutes')}")
        else:
            lines.append("Last refresh: never")
        interval = self.config.rag_refresh_interval_hours
        if interval > 0:
            due = refresh_is_due(self.config, interval_hours=interval)
            lines.append(
                f"Auto-refresh: every {interval:g}h while running"
                + (" (due now)" if due else "")
            )
        else:
            lines.append("Auto-refresh: disabled")
        return lines

    def _on_rag_refresh_status(self, msg: str) -> None:
        print(_DIMMED.format(f"  [rag refresh] {msg}"))

    def start_rag_scheduler(self) -> None:
        """Start background RAG refresh (immediate if due, then every N hours)."""
        self._rag_scheduler_task = start_rag_scheduler(
            config=self.config,
            llm=self.llm,
            ingest=self.ingest,
            lock=self._rag_refresh_lock,
            on_status=self._on_rag_refresh_status,
        )

    async def _cmd_rag_status(self) -> None:
        for line in self._rag_status_lines():
            print(line)

    async def _cmd_refresh_cve(self) -> None:
        print("Running RAG refresh (CVEs, malware intel, workspace, projects, references)...")
        summary = await run_refresh_locked(
            config=self.config,
            llm=self.llm,
            ingest=self.ingest,
            lock=self._rag_refresh_lock,
        )
        if summary is None:
            print("Refresh already in progress — try again in a moment.")
            return
        for key, value in summary.items():
            print(f"  {key}: {value}")

    def _render_event(self, event: StreamEvent) -> None:
        if event.type == "tool_call":
            print(_DIMMED.format(f"  -> {event.data['name']}({event.data['arguments']})"))
        elif event.type == "tool_result":
            marker = "ok" if event.data["ok"] else "FAIL"
            display = event.data["display"] or ""
            if len(display) > 300:
                display = display[:300] + "..."
            print(_DIMMED.format(f"  [{marker}] {display}"))
        elif event.type == "compacted":
            print(_DIMMED.format(f"  [context compacted -- {event.data['message_count']} messages kept]"))
        elif event.type == "error":
            print(_RED.format(f"  {event.data['message']}"))

    async def list_pulled_models(self) -> list[str]:
        """Names of locally pulled Ollama models, for the TUI picker or /model listing."""
        pulled = await self.llm.list_models()
        return [m["name"] for m in pulled]

    async def _cmd_model(self, arg: str, *, interactive: bool = True) -> None:
        if not arg:
            print(f"Current model: {self.agent.model} (num_ctx={self.agent.num_ctx})")
            print(f"Configured roles: {', '.join(self.config.models)}")
            try:
                names = await self.list_pulled_models()
            except Exception as exc:
                print(f"(couldn't list local Ollama models: {exc})")
                return
            if not names:
                return
            print("\nLocally pulled models:")
            for i, name in enumerate(names, 1):
                marker = "*" if name == self.agent.model else " "
                print(f" {marker}{i:2d}. {name}")
            if not interactive:
                # The TUI can't hand off to a blocking input() mid-event -- tell the user
                # to switch explicitly instead of prompting for a number.
                print("Use /model <name> to switch.")
                return
            choice = (await asyncio.to_thread(input, "Pick a number (Enter to cancel): ")).strip()
            if not choice:
                return
            if choice.isdigit() and 1 <= int(choice) <= len(names):
                self.agent.model = names[int(choice) - 1]
                print(f"Switched to model '{self.agent.model}' (num_ctx unchanged: {self.agent.num_ctx})")
            else:
                print(f"Not a valid choice: {choice!r}")
            return
        if arg in self.config.models:
            profile = self.config.model(arg)
            self.agent.model = profile.name
            self.agent.num_ctx = profile.num_ctx
            print(f"Switched to role '{arg}': {profile.name} (num_ctx={profile.num_ctx})")
        else:
            self.agent.model = arg
            print(f"Switched to model '{arg}' (num_ctx unchanged: {self.agent.num_ctx})")

    async def _cmd_ingest(self, arg: str) -> None:
        target = Path(arg).expanduser() if arg else self.config.knowledge_dir
        if not target.exists():
            print(f"Not found: {target}")
            return
        total = 0
        if target.is_file():
            total = await self.ingest.ingest_file(target, source_type="knowledge")
        else:
            for path in scan_dir(target, include_globs=DEFAULT_PROJECT_INCLUDE, exclude_globs=DEFAULT_PROJECT_EXCLUDE):
                rel = path.relative_to(target).as_posix()
                total += await self.ingest.ingest_file(path, source_type="knowledge", source=f"knowledge:{rel}")
        print(f"Ingested {total} new chunk(s) from {target}.")

    async def _cmd_fetch_references(self, arg: str) -> None:
        only = [arg] if arg else None
        if arg and arg not in REFERENCE_SOURCES:
            print(f"Unknown reference source '{arg}'. Available: {', '.join(REFERENCE_SOURCES)}")
            return
        print("Fetching reference corpora (first run can take a while)...")
        results = await fetch_all(self.config, only=only)
        for name, status in results.items():
            print(f"  {name}: {status}")
        print("Ingesting fetched corpora into RAG...")
        counts = await ingest_references(self.config, self.ingest, only=only)
        for name, n in counts.items():
            print(f"  {name}: {n} chunk(s)")

    async def _cmd_subagent(self, arg: str) -> None:
        if not arg:
            print("Usage: /subagent <role> <task>")
            return
        role, _, task = arg.partition(" ")
        if not task:
            print("Usage: /subagent <role> <task>")
            return
        print(f"Spawning '{role}' sub-agent...")
        print(await self._spawn_fn(role, task))

    async def handle_slash(self, line: str, *, interactive: bool = True) -> bool:
        """Returns True if the line was a recognized slash command. `interactive=False`
        (used by the TUI) suppresses sub-commands that need a blocking input() prompt."""
        parts = line.strip().split(maxsplit=1)
        cmd, arg = parts[0], (parts[1] if len(parts) > 1 else "")

        if cmd in ("/quit", "/exit"):
            raise SystemExit(0)
        if cmd == "/help":
            print(HELP_TEXT)
        elif cmd == "/model":
            await self._cmd_model(arg, interactive=interactive)
        elif cmd == "/compact":
            self.agent.messages = await self.context.compact(
                self.agent.messages, self.llm, self.config.model("fast").name, self.config.model("fast").num_ctx,
            )
            print(f"Compacted -- {len(self.agent.messages)} messages kept.")
        elif cmd == "/ingest":
            await self._cmd_ingest(arg)
        elif cmd in ("/refresh-cve", "/refresh"):
            await self._cmd_refresh_cve()
        elif cmd == "/rag-status":
            await self._cmd_rag_status()
        elif cmd == "/fetch-references":
            await self._cmd_fetch_references(arg)
        elif cmd == "/subagent":
            await self._cmd_subagent(arg)
        elif cmd == "/skills":
            if not self.skills:
                print(f"No skills found under {self.config.skills_dir}")
            else:
                for skill in self.skills.values():
                    print(f"  {skill.name:<24} {skill.description}")
        elif cmd == "/skill":
            skill = self.skills.get(arg)
            if skill is None:
                print(f"No skill named {arg!r}. Try /skills to list them.")
            else:
                print(skill.body)
        else:
            return False
        return True

    @staticmethod
    def _compact_banner_art(banner: str) -> str:
        """Drop the footer tagline so the TUI header stays shorter without losing the art."""
        lines = banner.splitlines()
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and "ascii art" in lines[-1]:
            lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines)

    def _build_banner_renderable(
        self, live_lines: list[str] | None = None, *, compact: bool = False,
    ) -> Any:
        """The boxed banner+info Panel, shared by the classic REPL print and the TUI's
        fixed header widget so the two don't drift out of sync. `live_lines` lets the TUI
        refresh just the btop-style stats on a timer without re-running fastfetch or
        re-rolling the quote each tick. `compact=True` trims footer/quote/static hw for the
        fixed TUI header -- full panel on the classic REPL startup print."""
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        banner = load_banner()
        if compact and banner:
            banner = self._compact_banner_art(banner)
        info = Table.grid(padding=(0, 1))
        info.add_column()
        info.add_row(f"[bold {MIKU_COLOR}]Miku[/] [dim](Hermes)[/]")
        info.add_row(f"model   {self.agent.model}")
        info.add_row(f"ctx     {self.agent.num_ctx}")
        info.add_row(f"ollama  {self.config.ollama_host}")
        info.add_row(f"roles   {', '.join(self.config.models)}")
        info.add_row("")
        info.add_row("[dim]/help for commands, /quit to exit[/]")
        info.add_row("")
        if not compact:
            for line in self._static_hw_lines:
                info.add_row(f"[dim]{line}[/]")
        for line in (live_lines if live_lines is not None else _read_live_stats()):
            info.add_row(f"[dim]{line}[/]")

        # Quote sits beside art+info in the remaining width (not below everything) --
        # that remaining space is otherwise dead when the panel spans the full terminal.
        quote_block = Text(f"“{self._quote}”", style="dim italic")
        grid = Table.grid(padding=(0, 2), expand=True)
        if banner:
            grid.add_column()
            grid.add_column()
            grid.add_column(ratio=1, vertical="middle")
            grid.add_row(Text.from_ansi(banner), info, quote_block)
        else:
            grid.add_column()
            grid.add_column(ratio=1, vertical="middle")
            grid.add_row(info, quote_block)

        return Panel(grid, border_style=MIKU_COLOR, expand=True, padding=(1, 2))

    def _print_startup_panel(self) -> None:
        """Boxed banner + status, via `rich` if installed; degrades to plain prints
        (same info, no box/color) if it isn't -- rich stays optional, not required."""
        try:
            from rich.console import Console
        except ImportError:
            banner = load_banner()
            if banner:
                print(banner)
            print(f"Miku (Hermes) -- model: {self.agent.model} | ollama: {self.config.ollama_host}")
            return

        Console().print(self._build_banner_renderable())

    async def _reveal_reply(self, console: Any, content: str) -> None:
        """Renders the final answer as real markdown (bold/lists/code), revealed a line at
        a time instead of dumped all at once -- closer to how Claude Code's own replies read."""
        from rich.live import Live
        from rich.markdown import Markdown
        from rich.styled import Styled

        lines = content.split("\n")
        # Cap total reveal time regardless of length: snappy for a short reply, still
        # readable-paced for a long one, never so slow it feels laggy.
        delay = min(0.05, 1.2 / max(len(lines), 1))
        shown: list[str] = []
        with Live(console=console, refresh_per_second=30) as live:
            for line in lines:
                shown.append(line)
                live.update(Styled(Markdown("\n".join(shown)), f"{MIKU_COLOR} on {MIKU_BG}"))
                await asyncio.sleep(delay)

    async def run(self) -> None:
        self._print_startup_panel()
        self.start_rag_scheduler()
        for line in self._rag_status_lines():
            print(_DIMMED.format(f"  {line}"))
        if not await self.llm.ping():
            print(_RED.format(
                f"  Warning: can't reach Ollama at {self.config.ollama_host}. "
                "Check it's running, or OLLAMA_HOST if this is a Qubes client VM."
            ))
        print()

        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        console = Console()

        while True:
            console.rule(style="dim")
            console.print(f"[bold {USER_COLOR} on {USER_BG}] you> [/] ", end="")
            try:
                line = await asyncio.to_thread(input, "")
            except EOFError:
                break
            if not line.strip():
                continue
            if line.startswith("/"):
                try:
                    handled = await self.handle_slash(line)
                except SystemExit:
                    break
                if handled:
                    continue

            try:
                gen = self.agent.stream_run(_prepare_user_turn(line))
                while True:
                    with console.status(f"[{MIKU_COLOR}]miku is thinking...[/]", spinner="dots"):
                        try:
                            event = await gen.__anext__()
                        except StopAsyncIteration:
                            break

                    if event.type == "final":
                        thinking = (event.data.get("thinking") or "").strip()
                        if thinking:
                            console.print(Panel(
                                Text(thinking, style="dim italic"),
                                title="[dim]thinking[/]", border_style="dim",
                                width=max(40, console.width * 7 // 10),
                            ))
                        console.print(f"[bold {MIKU_COLOR} on {MIKU_BG}] miku ✨> [/]")
                        await self._reveal_reply(console, event.data["content"])
                        console.print()
                        break
                    else:
                        self._render_event(event)
            except Exception as e:  # noqa: BLE001 - keep the REPL alive on a bad turn
                console.print(_RED.format(f"[error] {type(e).__name__}: {e}"))


async def _workspace_cli(args: list[str]) -> None:
    """hermes workspace index|status|search|refresh — matches skills' knowledge-rag playbook."""
    config = load_config()
    llm = OllamaClient(config.ollama_host)
    store = VectorStore(config.rag_dir, dim=DIM)
    try:
        embedder = EmbeddingClient(llm, model=config.model("embed").name)
        retriever = RAGRetriever(embedder, store)
        ingest = IngestPipeline(embedder, store)

        sub = args[0] if args else "status"
        if sub == "index":
            config.knowledge_dir.mkdir(parents=True, exist_ok=True)
            total = await ingest.ingest_knowledge_dir(config)
            for project in config.projects:
                total += await ingest.ingest_project(project)
            print(f"Indexed {total} new chunk(s) from {config.knowledge_dir}")
        elif sub == "status":
            rows = store._conn.execute(
                "SELECT source_type, COUNT(*) FROM chunks WHERE deleted = 0 GROUP BY source_type ORDER BY source_type"
            ).fetchall()
            total = store._conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE deleted = 0"
            ).fetchone()[0]
            print(f"RAG store: {config.rag_dir}")
            print(f"Workspace: {config.knowledge_dir}")
            print(f"Total chunks: {total}")
            for source_type, count in rows:
                print(f"  {source_type}: {count}")
            from hermes.rag.scheduler import _read_last_refresh

            last = _read_last_refresh(config)
            print(f"Last refresh: {last.isoformat(timespec='minutes') if last else 'never'}")
        elif sub == "search":
            query = " ".join(args[1:]).strip()
            if not query:
                print("Usage: hermes workspace search <query>")
                return
            chunks = await retriever.query(query, k=8)
            if not chunks:
                print("No matching knowledge found.")
                return
            print(retriever.format_for_prompt(chunks, max_chars=8000))
        elif sub == "refresh":
            summary = await run_daily_refresh(config, llm, ingest)
            for key, value in summary.items():
                print(f"{key}: {value}")
        else:
            print("Usage: hermes workspace {index|status|search|refresh}")
    finally:
        store.close()
        await llm.aclose()


def main() -> None:
    _set_terminal_title("Miku")

    if len(sys.argv) >= 2 and sys.argv[1] == "workspace":
        asyncio.run(_workspace_cli(sys.argv[2:]))
        return

    if "--classic" not in sys.argv:
        from hermes.tui import run_tui
        run_tui()
        return

    config = load_config()
    repl = HermesREPL(config)

    async def _run_and_close() -> None:
        # run() and aclose() must share one event loop: httpx's AsyncClient binds its
        # connections to whichever loop is running on first use, so closing it from a
        # second, separate asyncio.run() call raises "Event loop is closed".
        try:
            await repl.run()
        finally:
            await repl.aclose()

    try:
        asyncio.run(_run_and_close())
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
