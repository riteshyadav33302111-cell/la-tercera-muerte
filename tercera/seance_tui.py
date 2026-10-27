"""
La Sesion -- The haunted terminal seance.

Phase 4 fixes:
- Rename call_after_refresh -> _schedule_opening (Textual uses that name internally)
- Escape all LLM/user text with rich.markup.escape() before showing
- Convert markdown **bold**/*italic* to Rich [bold]/[italic] markup
- Stream responses: update a single widget token-by-token
- Reset idle timer in on_input_changed so whispers don't fire while typing
"""

from __future__ import annotations

import asyncio
import random
import re
import time
from typing import Optional

from rich.markup import escape as rich_escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, Input, Static

from .config import get_config
from .llm import chat, whisper as llm_whisper
from .memory import retrieve
from .persona import build_persona, build_whisper_prompt

_cfg = get_config()
_IDLE_SECONDS = _cfg.get("seance", {}).get("idle_whisper_seconds", 45)


# ---------------------------------------------------------------------------
# Candle widget
# ---------------------------------------------------------------------------

_EMBER_COLORS = ["bright_yellow", "yellow", "dark_orange", "orange1", "gold1"]


class CandleRow(Widget):
    DEFAULT_CSS = """
    CandleRow {
        height: 3;
        content-align: center middle;
        background: #0d0600;
        color: yellow;
    }
    """
    frame: reactive[int] = reactive(0)

    def render(self):
        from rich.text import Text
        color = random.choice(_EMBER_COLORS)
        row = Text()
        for c in ["[C]", "[*]", "[C]", "[~]", "[C]", "[*]", "[C]"]:
            row.append(f" {c} ", style=f"bold {color}")
        return row

    def on_mount(self) -> None:
        self.set_interval(0.15 + random.random() * 0.25, self._flicker)

    def _flicker(self) -> None:
        self.frame = (self.frame + 1) % 4
        self.refresh()


# ---------------------------------------------------------------------------
# Message widgets
# ---------------------------------------------------------------------------

def _md_to_rich(text: str) -> str:
    """
    Escape raw text then convert markdown **bold** and *italic* to Rich markup.
    Order matters: escape first so literal brackets are safe, then insert markup.
    """
    safe = rich_escape(text)
    # **bold**
    safe = re.sub(r"\*\*(.+?)\*\*", r"[bold]\1[/bold]", safe)
    # *italic* (not preceded by another *)
    safe = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"[italic]\1[/italic]", safe)
    return safe


class GhostMessage(Static):
    DEFAULT_CSS = """
    GhostMessage {
        margin: 1 2; padding: 1 2;
        border-left: tall $warning;
        background: #100800; color: #c9a86c;
    }
    """


class UserMessage(Static):
    DEFAULT_CSS = """
    UserMessage {
        margin: 1 2; padding: 1 2;
        border-left: tall $accent;
        background: #080c10; color: #8ab4d4;
    }
    """


class WhisperMessage(Static):
    DEFAULT_CSS = """
    WhisperMessage {
        margin: 1 4; padding: 0 2;
        color: #4a3a2a; text-style: italic;
    }
    """


# ---------------------------------------------------------------------------
# Seance App
# ---------------------------------------------------------------------------

class SeanceApp(App):
    TITLE = "La Tercera Muerte"
    CSS = """
    Screen { background: #0d0600; }
    #project-title {
        text-align: center; color: #f5c842; text-style: bold;
        height: 3; content-align: center middle; background: #0d0600;
    }
    #chat-area { background: #0d0600; scrollbar-color: #3a2a10 #0d0600; }
    #input-row {
        height: 5; border-top: solid #3a2a10;
        background: #100800; padding: 1 2;
    }
    #prompt-label { width: 14; content-align: center middle; color: #c9a86c; }
    #user-input { background: #0d0600; border: solid #3a2a10; color: #8ab4d4; }
    #user-input:focus { border: solid #f5c842; }
    #status-bar {
        height: 1; background: #0a0400;
        color: #4a3a2a; content-align: left middle; padding: 0 2;
    }
    Footer { background: #0a0400; color: #4a3a2a; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+w", "request_whisper", "Whisper"),
        Binding("escape", "clear_input", "Clear"),
    ]

    def __init__(self, grave: dict, **kwargs):
        super().__init__(**kwargs)
        self.grave = grave
        self.system_prompt = build_persona(grave)
        self.whisper_prompt = build_whisper_prompt(grave)
        self.history: list[dict] = []
        self._last_activity = time.time()
        self._typing = False

    def compose(self) -> ComposeResult:
        yield CandleRow()
        yield Static(
            f"[bold yellow]{self.grave['name']}[/bold yellow]\n"
            f"[dim]{self.grave.get('language', '?')} | "
            f"{self.grave['born'][:10]} - {self.grave['died'][:10]}[/dim]",
            id="project-title",
        )
        with ScrollableContainer(id="chat-area"):
            yield Static(
                "[dim italic]The candles are lit. The seance begins.\n"
                "Ask the ghost anything. Type [bold]/quit[/bold] to leave, "
                "[bold]/whisper[/bold] for a whisper.[/dim italic]",
                id="intro",
            )
        with Horizontal(id="input-row"):
            yield Static("[c] You > ", id="prompt-label")
            yield Input(placeholder="Speak to the spirit...", id="user-input")
        yield Static("Idle...", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(5, self._check_idle)
        # Schedule opening message without colliding with Textual internals
        self._schedule_opening()

    def _schedule_opening(self) -> None:
        async def _run():
            await asyncio.sleep(0.6)
            name = rich_escape(self.grave["name"])
            born = self.grave["born"][:10]
            died = self.grave["died"][:10]
            lw = rich_escape(self.grave["last_commit"]["message"][:100])
            deps = len(self.grave.get("dependencies", []))
            commits = self.grave.get("total_commits", 0)
            todos = len(self.grave.get("unfinished_todos", []))
            self._show_ghost_message(
                f"[italic]*The candles flicker...*[/italic]\n\n"
                f"I am [bold]{name}[/bold]. "
                f"I was born [cyan]{born}[/cyan] and fell silent [cyan]{died}[/cyan].\n\n"
                f"My last words were: [italic]\"{lw}\"[/italic]\n\n"
                f"I remember {deps} beloved dependencies, "
                f"{commits} moments of life, and {todos} things left undone.\n\n"
                f"Ask me anything."
            )
        asyncio.create_task(_run())

    def _show_ghost_message(self, markup: str) -> None:
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        msg = GhostMessage(markup)
        chat_area.mount(msg)
        chat_area.scroll_end(animate=False)

    def _show_user_message(self, text: str) -> None:
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        safe = rich_escape(text)
        msg = UserMessage(f"[bold cyan]You:[/bold cyan] {safe}")
        chat_area.mount(msg)
        chat_area.scroll_end(animate=False)

    def _show_whisper(self, text: str) -> None:
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        safe = rich_escape(text)
        msg = WhisperMessage(f"[dim italic]...{safe}...[/dim italic]")
        chat_area.mount(msg)
        chat_area.scroll_end(animate=False)

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#status-bar", Static).update(rich_escape(text))
        except Exception:
            pass

    # ── Idle whisper ────────────────────────────────────────────────────────

    def _check_idle(self) -> None:
        if self._typing:
            return
        idle = time.time() - self._last_activity
        if idle >= _IDLE_SECONDS:
            self._last_activity = time.time()  # reset so it doesn't spam
            asyncio.create_task(self._do_whisper())

    async def _do_whisper(self) -> None:
        self._set_status("*something stirs in the silence...*")
        try:
            text = await asyncio.get_event_loop().run_in_executor(
                None, llm_whisper, self.whisper_prompt
            )
            self._show_whisper(text)
        except Exception:
            pass
        self._set_status("Listening...")

    # ── Input handling ───────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        """Reset idle timer while the user is typing."""
        self._last_activity = time.time()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        self._last_activity = time.time()

        if text.lower() in ("/quit", "/q", "quit", "exit"):
            self.exit()
            return
        if text.lower() in ("/whisper", "/w"):
            asyncio.create_task(self._do_whisper())
            return

        self._show_user_message(text)
        asyncio.create_task(self._get_ghost_response(text))

    async def _get_ghost_response(self, user_text: str) -> None:
        """Stream the ghost's response token-by-token into a single widget."""
        self._typing = True
        self._set_status("The spirit stirs...")

        # Mount an empty ghost message we'll fill in
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        msg_widget = GhostMessage("[dim italic]...[/dim italic]")
        await chat_area.mount(msg_widget)
        chat_area.scroll_end(animate=False)

        try:
            memories = await asyncio.get_event_loop().run_in_executor(
                None, retrieve, user_text, self.grave, 4
            )
            memory_block = ""
            if memories:
                memory_block = "\n\nMemories surfacing from the grave:\n" + "\n---\n".join(
                    f"[{m['file']}:{m.get('start_line', '?')}]\n{m['text'][:400]}"
                    for m in memories
                )

            messages = [
                {"role": "system", "content": self.system_prompt + memory_block},
            ] + self.history[-10:] + [
                {"role": "user", "content": user_text},
            ]

            # Streaming: collect tokens and update the widget
            accumulated = ""

            def _stream_sync():
                nonlocal accumulated
                for token in chat(messages, stream=True):
                    accumulated += token
                    # Schedule a UI update from the sync thread
                    self.call_from_thread(
                        msg_widget.update,
                        _md_to_rich(accumulated),
                    )
                return accumulated

            full_response = await asyncio.get_event_loop().run_in_executor(
                None, _stream_sync
            )

            # Ensure final state is rendered
            msg_widget.update(_md_to_rich(full_response))
            chat_area.scroll_end(animate=False)

            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": full_response})

        except Exception as e:
            msg_widget.update(
                f"[dim red italic]*The connection faltered: {rich_escape(str(e))}*[/dim red italic]"
            )
        finally:
            self._typing = False
            self._set_status("Listening...")

    def action_request_whisper(self) -> None:
        asyncio.create_task(self._do_whisper())

    def action_clear_input(self) -> None:
        self.query_one("#user-input", Input).value = ""


# ---------------------------------------------------------------------------
# CLI fallback seance (no Textual)
# ---------------------------------------------------------------------------

def cli_seance(grave: dict) -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt

    console = Console()
    system_prompt = build_persona(grave)
    history: list[dict] = []

    console.print(Panel(
        f"[bold yellow]{rich_escape(grave['name'])}[/bold yellow]\n"
        f"[dim]{grave.get('language', '?')} | "
        f"{grave['born'][:10]} - {grave['died'][:10]}[/dim]",
        border_style="dark_orange",
    ))
    console.print("\n[italic dim]Seance begun. Type [bold]quit[/bold] to leave.[/italic dim]\n")

    while True:
        try:
            user_input = Prompt.ask("[cyan]You[/cyan]")
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower() in ("quit", "exit", "/q"):
            break

        memories = retrieve(user_input, grave, top_k=3)
        memory_block = ""
        if memories:
            memory_block = "\n\nMemories:\n" + "\n---\n".join(
                f"[{m['file']}]\n{m['text'][:300]}" for m in memories
            )

        messages = [
            {"role": "system", "content": system_prompt + memory_block},
        ] + history[-8:] + [
            {"role": "user", "content": user_input},
        ]

        console.print("\n[dim yellow]The spirit stirs...[/dim yellow]")
        try:
            response = ""
            with console.status("[dim]Thinking...[/dim]"):
                response = chat(messages, stream=False)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
            console.print(Panel(
                _md_to_rich(response),
                title="[yellow]Ghost[/yellow]",
                border_style="dark_orange",
            ))
        except Exception as e:
            console.print(f"[red]Connection faltered: {rich_escape(str(e))}[/red]")

    console.print("\n[italic dim]The candles go dark. The seance is over.[/italic dim]\n")
