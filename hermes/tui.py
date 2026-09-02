"""The real TUI: a fixed banner header (with live btop-style stats), a fixed status line
that never scrolls away, a scrolling column of collapsible per-turn sections (only the
latest stays expanded -- older ones fold down to a one-line title, freeing space for the
active exchange), and a pinned input at the bottom. Built with `textual` because this
layout -- fixed regions plus one independently-scrollable region, all live -- is exactly
what `rich`'s Live/Console can't do; see hermes/cli.py's HermesREPL for the classic
single-flow REPL (`--classic`).

Reuses HermesREPL entirely for config/agent/tools/persona/skills wiring and for slash-
command handling (`handle_slash`) -- this module only replaces the presentation layer.
"""

from __future__ import annotations

import asyncio
import contextlib
import io

from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Collapsible, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from hermes.cli import MIKU_BG, MIKU_COLOR, USER_BG, USER_COLOR, HermesREPL, _prepare_user_turn
from hermes.config import HermesConfig, load_config

_THINKING_FRAMES = ["miku is thinking.", "miku is thinking..", "miku is thinking..."]
_REVEAL_BUDGET_S = 1.2  # total time to reveal a block of text, regardless of length
_LIVE_STATS_INTERVAL_S = 1.5


class ModelPickerScreen(ModalScreen[str | None]):
    """Arrow-key model picker for /model in the TUI (classic REPL keeps input() instead)."""

    CSS = """
    ModelPickerScreen {
        align: center middle;
    }
    #picker-box {
        width: 90%;
        height: auto;
        max-height: 80%;
        border: tall #3DC5C9;
        background: #123536;
        padding: 1 2;
    }
    #model-list {
        height: auto;
        max-height: 18;
        border: none;
        padding: 0;
        background: transparent;
    }
    #model-list:focus {
        border: none;
    }
    Label {
        color: #3DC5C9;
        margin-bottom: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, models: list[str], current: str) -> None:
        super().__init__()
        self._models = models
        self._current = current

    def compose(self) -> ComposeResult:
        with Container(id="picker-box"):
            yield Label("Select model  (↑↓ move · Enter pick · Esc cancel)")
            options = [
                Option(
                    f"{'▸ ' if name == self._current else '  '}{name}",
                    id=name,
                )
                for name in self._models
            ]
            picker = OptionList(*options, id="model-list")
            if self._current in self._models:
                picker.highlighted = self._models.index(self._current)
            yield picker

    def on_mount(self) -> None:
        self.query_one("#model-list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(event.option_id)

    def action_cancel(self) -> None:
        self.dismiss(None)


def _reply_style(content: str) -> Group:
    return Group(Text(f" miku ✨>", style=f"bold {MIKU_COLOR} on {MIKU_BG}"), Markdown(content, style=MIKU_COLOR))


class MikuApp(App):
    CSS = """
    Screen { layout: vertical; }
    #banner { height: auto; padding: 0 1; }
    #status { height: 1; padding: 0 1; }
    #chat { height: 1fr; padding: 0 1; }
    #input { dock: bottom; border: tall #123536; }
    #input:focus { border: tall #3DC5C9; }

    CollapsibleTitle { color: #FAF2EF; }
    CollapsibleTitle:hover { background: #123536; color: #3DC5C9; }
    CollapsibleTitle:focus { background: #123536; color: #3DC5C9; text-style: bold; }
    """
    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def __init__(self, repl: HermesREPL):
        super().__init__()
        self.repl = repl
        self._thinking_frame = 0
        self._thinking_timer = None

    def compose(self) -> ComposeResult:
        yield Static(self.repl._build_banner_renderable(compact=True), id="banner")
        yield Static("", id="status")
        yield VerticalScroll(id="chat")
        yield Input(placeholder="type a message, or /help for commands...", id="input")

    async def on_mount(self) -> None:
        self.query_one("#input", Input).focus()
        self.set_interval(_LIVE_STATS_INTERVAL_S, self._refresh_live_stats)
        self.repl.start_rag_scheduler()
        if not await self.repl.llm.ping():
            await self._mount_turn(
                "(startup)",
                Static(f"Warning: can't reach Ollama at {self.repl.config.ollama_host}."),
                collapsed=False,
            )

    def _refresh_live_stats(self) -> None:
        from hermes.cli import _read_live_stats
        try:
            banner = self.query_one("#banner", Static)
        except Exception:  # noqa: BLE001 - app may be mid-teardown; a missed tick is fine
            return
        banner.update(self.repl._build_banner_renderable(live_lines=_read_live_stats(), compact=True))

    def _set_thinking(self, on: bool) -> None:
        status = self.query_one("#status", Static)
        if on:
            self._thinking_frame = 0
            status.update(Text(_THINKING_FRAMES[0], style=MIKU_COLOR))
            self._thinking_timer = self.set_interval(0.5, self._tick_thinking)
        else:
            if self._thinking_timer is not None:
                self._thinking_timer.stop()
                self._thinking_timer = None
            status.update("")

    def _tick_thinking(self) -> None:
        self._thinking_frame = (self._thinking_frame + 1) % len(_THINKING_FRAMES)
        self.query_one("#status", Static).update(Text(_THINKING_FRAMES[self._thinking_frame], style=MIKU_COLOR))

    async def _pick_model(self) -> None:
        try:
            models = await self.repl.list_pulled_models()
        except Exception as exc:  # noqa: BLE001
            await self._mount_turn("you> /model", Static(f"Couldn't list models: {exc}"), collapsed=False)
            return
        if not models:
            await self._mount_turn("you> /model", Static("No locally pulled models."), collapsed=False)
            return

        picked = await self.push_screen_wait(ModelPickerScreen(models, self.repl.agent.model))
        if not picked:
            await self._mount_turn("you> /model", Static("(cancelled)"), collapsed=False)
            return
        self.repl.agent.model = picked
        msg = f"Switched to model '{picked}' (num_ctx unchanged: {self.repl.agent.num_ctx})"
        self._refresh_live_stats()
        await self._mount_turn("you> /model", Static(msg), collapsed=False)

    async def _mount_turn(self, title: str, body: Static, *, collapsed: bool) -> Collapsible:
        chat = self.query_one("#chat", VerticalScroll)
        for existing in chat.query(Collapsible):
            existing.collapsed = True
        label = title if len(title) <= 60 else title[:57] + "..."
        collapsible = Collapsible(body, title=label, collapsed=collapsed)
        await chat.mount(collapsible)
        chat.scroll_end(animate=False)
        return collapsible

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        line = event.value.strip()
        event.input.value = ""
        if not line:
            return

        if line.startswith("/"):
            parts = line.strip().split(maxsplit=1)
            if parts[0] == "/model" and len(parts) == 1:
                self.run_worker(self._pick_model(), exclusive=False)
                return
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    handled = await self.repl.handle_slash(line, interactive=False)
            except SystemExit:
                self.exit()
                return
            if handled:
                output = buf.getvalue().rstrip("\n")
                body = Static(output or "(ok)")
                await self._mount_turn(f"you> {line}", body, collapsed=False)
                return

        body = Static("")
        await self._mount_turn(f"you> {line}", body, collapsed=False)
        self.run_worker(self._run_turn(line, body), exclusive=True, group="turn")

    async def _reveal(self, body: Static, parts: list, render_target: str, *, final: bool = False) -> None:
        """Progressively reveals `render_target` (already-complete text) into the last slot
        of `parts`, line by line, so it reads like it's being typed instead of dumped."""
        lines = render_target.split("\n")
        delay = min(0.05, _REVEAL_BUDGET_S / max(len(lines), 1))
        shown: list[str] = []
        for line in lines:
            shown.append(line)
            parts[-1] = "\n".join(shown)
            body.update(Group(*[p if not isinstance(p, str) else Text(p) for p in parts]))
            if not final:
                await asyncio.sleep(delay)
            else:
                await asyncio.sleep(delay)

    async def _run_turn(self, line: str, body: Static) -> None:
        self._set_thinking(True)
        parts: list = []

        def render() -> Group:
            return Group(*parts) if parts else Text("")

        try:
            gen = self.repl.agent.stream_run(_prepare_user_turn(line))
            while True:
                try:
                    event = await gen.__anext__()
                except StopAsyncIteration:
                    break

                if event.type == "tool_call":
                    parts.append(Text(f"  -> {event.data['name']}({event.data['arguments']})", style="dim"))
                    body.update(render())
                elif event.type == "tool_result":
                    marker = "ok" if event.data["ok"] else "FAIL"
                    display = (event.data["display"] or "")[:300]
                    parts.append(Text(f"  [{marker}] {display}", style="dim"))
                    body.update(render())
                elif event.type == "compacted":
                    parts.append(Text(f"  [context compacted -- {event.data['message_count']} messages kept]", style="dim"))
                    body.update(render())
                elif event.type == "error":
                    parts.append(Text(f"  {event.data['message']}", style="red"))
                    body.update(render())
                elif event.type == "final":
                    # Thinking and the reply are rendered independently -- a problem in one
                    # must never suppress the other.
                    thinking = (event.data.get("thinking") or "").strip()
                    if thinking:
                        try:
                            parts.append("")  # placeholder slot _reveal fills in-place
                            await self._reveal_thinking(body, parts, thinking)
                        except Exception as exc:  # noqa: BLE001
                            parts[-1] = Text(f"[thinking render error: {exc}]", style="dim red")
                            body.update(render())

                    content = event.data.get("content") or "(empty response)"
                    try:
                        parts.append("")
                        await self._reveal_final(body, parts, content)
                    except Exception as exc:  # noqa: BLE001
                        parts[-1] = Text(f" miku ✨> [render error: {exc}]\n{content}", style=MIKU_COLOR)
                        body.update(render())
        except Exception as exc:  # noqa: BLE001 - keep the TUI alive on a bad turn
            parts.append(Text(f"[error] {type(exc).__name__}: {exc}", style="red"))
            body.update(render())
        finally:
            self._set_thinking(False)

    async def _reveal_thinking(self, body: Static, parts: list, thinking: str) -> None:
        lines = thinking.split("\n")
        delay = min(0.04, _REVEAL_BUDGET_S / max(len(lines), 1))
        shown: list[str] = []
        for line in lines:
            shown.append(line)
            parts[-1] = Panel(Text("\n".join(shown), style="dim italic"), title="[dim]thinking[/]", border_style=MIKU_COLOR)
            body.update(Group(*parts))
            await asyncio.sleep(delay)

    async def _reveal_final(self, body: Static, parts: list, content: str) -> None:
        lines = content.split("\n")
        delay = min(0.04, _REVEAL_BUDGET_S / max(len(lines), 1))
        shown: list[str] = []
        for line in lines:
            shown.append(line)
            text_so_far = "\n".join(shown)
            parts[-1] = Group(Text(" miku ✨>", style=f"bold {MIKU_COLOR} on {MIKU_BG}"), Markdown(text_so_far, style=MIKU_COLOR))
            body.update(Group(*parts))
            await asyncio.sleep(delay)


def run_tui(config: HermesConfig | None = None) -> None:
    config = config or load_config()
    repl = HermesREPL(config)
    app = MikuApp(repl)

    async def _run_and_close() -> None:
        # app.run_async() and repl.aclose() must share one event loop: httpx's AsyncClient
        # binds its connections to whichever loop is running on first use, so closing it
        # from a second, separate asyncio.run() call raises "Event loop is closed" (same
        # pitfall the classic REPL's main() already avoids the same way).
        try:
            await app.run_async()
        finally:
            await repl.aclose()

    asyncio.run(_run_and_close())
