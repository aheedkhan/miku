"""The REPL entrypoint: wires config, the Ollama client, the RAG store/retriever/ingest
pipeline, every tool module, the persona, and the main Agent together, then runs an
interactive chat loop with a handful of slash commands. Both `hermes` (the console script)
and `python -m hermes` land here.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from hermes.agents.subagent import spawn_subagent as _spawn_subagent_impl
from hermes.config import DEFAULT_PROJECT_EXCLUDE, DEFAULT_PROJECT_INCLUDE, HermesConfig, load_config
from hermes.core.agent_loop import Agent, StreamEvent
from hermes.core.concurrency import InferenceGate
from hermes.core.context_manager import ContextManager
from hermes.core.llm_client import OllamaClient
from hermes.core.tool_strategy import AutoToolStrategy
from hermes.persona.loader import load_system_prompt
from hermes.rag.daily_refresh import run_daily_refresh
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
    subagent_tool,
    web_search_tool,
)
from hermes.tools.registry import ToolRegistry

DIM = 768  # nomic-embed-text's dimensionality (verified live) — VectorStore self-corrects
# from whatever's already on disk if a different-dimension embed model was used instead.

_DIMMED = "\033[2m{}\033[0m"
_RED = "\033[31m{}\033[0m"

HELP_TEXT = """Commands:
  /model [name-or-role]        show/switch the active model (role name like "code", or a raw model tag)
  /compact                     manually compact the conversation history now
  /ingest [path]                ingest a file or directory into RAG (defaults to knowledge_dir)
  /refresh-cve                 run the daily refresh now (Android CVEs, malware intel, projects, reference corpora)
  /fetch-references [name]     one-time fetch of Win32 API / Linux kernel / MITRE ATT&CK corpora, then ingest them
  /subagent <role> <task>      spawn a scoped sub-agent directly (roles: researcher, reviewer, pentest_runner, general)
  /help                         this message
  /quit, /exit                  leave
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
    return registry


class HermesREPL:
    def __init__(self, config: HermesConfig):
        self.config = config
        self.llm = OllamaClient(config.ollama_host)
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

        cwd = Path.cwd()
        branch = _git_branch(cwd)
        extra_context = f"Current working directory: {cwd}"
        if branch:
            extra_context += f" (git branch: {branch})"

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
        self.store.close()
        await self.llm.aclose()

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

    async def _cmd_model(self, arg: str) -> None:
        if not arg:
            print(f"Current model: {self.agent.model} (num_ctx={self.agent.num_ctx})")
            print(f"Configured roles: {', '.join(self.config.models)}")
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

    async def _cmd_refresh_cve(self) -> None:
        print("Running daily refresh (Android CVEs, malware intel, projects, reference corpora)...")
        summary = await run_daily_refresh(self.config, self.llm, self.ingest)
        for key, value in summary.items():
            print(f"  {key}: {value}")

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

    async def handle_slash(self, line: str) -> bool:
        """Returns True if the line was a recognized slash command."""
        parts = line.strip().split(maxsplit=1)
        cmd, arg = parts[0], (parts[1] if len(parts) > 1 else "")

        if cmd in ("/quit", "/exit"):
            raise SystemExit(0)
        if cmd == "/help":
            print(HELP_TEXT)
        elif cmd == "/model":
            await self._cmd_model(arg)
        elif cmd == "/compact":
            self.agent.messages = await self.context.compact(
                self.agent.messages, self.llm, self.config.model("fast").name, self.config.model("fast").num_ctx,
            )
            print(f"Compacted -- {len(self.agent.messages)} messages kept.")
        elif cmd == "/ingest":
            await self._cmd_ingest(arg)
        elif cmd == "/refresh-cve":
            await self._cmd_refresh_cve()
        elif cmd == "/fetch-references":
            await self._cmd_fetch_references(arg)
        elif cmd == "/subagent":
            await self._cmd_subagent(arg)
        else:
            return False
        return True

    async def run(self) -> None:
        print(f"Miku (Hermes) -- model: {self.agent.model} | ollama: {self.config.ollama_host}")
        if not await self.llm.ping():
            print(_RED.format(
                f"  Warning: can't reach Ollama at {self.config.ollama_host}. "
                "Check it's running, or OLLAMA_HOST if this is a Qubes client VM."
            ))
        print("Type /help for commands, /quit to exit.\n")

        while True:
            try:
                line = await asyncio.to_thread(input, "you> ")
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

            print("miku> ", end="", flush=True)
            try:
                async for event in self.agent.stream_run(line):
                    if event.type == "final":
                        print(event.data["content"])
                    else:
                        self._render_event(event)
            except Exception as e:  # noqa: BLE001 - keep the REPL alive on a bad turn
                print(_RED.format(f"\n[error] {type(e).__name__}: {e}"))


def main() -> None:
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
