"""
La Sesión — The haunted terminal séance.

A Textual TUI with:
- Flickering candle header
- Typewriter ghost responses
- Idle whispers after 45 seconds
- RAG-powered memory recall
"""

from __future__ import annotations

import asyncio
import random
import re
import time
from datetime import datetime
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Footer, Header, Input, Label, RichLog, Static
)
from rich.text import Text
from rich.console import Console
from rich.panel import Panel

from .config import get_config
from .llm import chat, whisper as llm_whisper
from .memory import retrieve
from .persona import build_persona, build_whisper_prompt

_cfg = get_config()
_IDLE_SECONDS = _cfg.get("seance", {}).get("idle_whisper_seconds", 45)
_TYPEWRITER_MS = _cfg.get("seance", {}).get("typewriter_delay_ms", 30)


# ---------------------------------------------------------------------------
# Candle widget
# ---------------------------------------------------------------------------

CANDLE_FRAMES = [
    "🕯️",
    " 🕯",
    "🕯 ",
    " 🕯️",
]

EMBER_COLORS = ["bright_yellow", "yellow", "dark_orange", "orange1", "gold1"]


class CandleRow(Widget):
    """A row of flickering candles."""

    DEFAULT_CSS = """
    CandleRow {
        height: 3;
        content-align: center middle;
        background: #0d0600;
        color: yellow;
    }
    """

    frame: reactive[int] = reactive(0)

    def render(self) -> Text:
        candles = ["🕯️", "💀", "🕯️", "🌼", "🕯️", "💀", "🕯️"]
        color = random.choice(EMBER_COLORS)
        row = Text()
        for c in candles:
            row.append(f" {c} ", style=f"bold {color}")
        return row

    def on_mount(self) -> None:
        self.set_interval(0.15 + random.random() * 0.25, self._flicker)

    def _flicker(self) -> None:
        self.frame = (self.frame + 1) % len(CANDLE_FRAMES)
        self.refresh()


# ---------------------------------------------------------------------------
# Ghost message widget
# ---------------------------------------------------------------------------

class GhostMessage(Static):
    """A message from the ghost, rendered in ghostly style."""

    DEFAULT_CSS = """
    GhostMessage {
        margin: 1 2;
        padding: 1 2;
        border-left: tall $warning;
        background: #100800;
        color: #c9a86c;
    }
    """


class UserMessage(Static):
    """A message from the living user."""

    DEFAULT_CSS = """
    UserMessage {
        margin: 1 2;
        padding: 1 2;
        border-left: tall $accent;
        background: #080c10;
        color: #8ab4d4;
    }
    """


class WhisperMessage(Static):
    """An unsolicited ghostly whisper."""

    DEFAULT_CSS = """
    WhisperMessage {
        margin: 1 4;
        padding: 0 2;
        color: #4a3a2a;
        text-style: italic;
    }
    """


# ---------------------------------------------------------------------------
# Main Séance App
# ---------------------------------------------------------------------------

class SeanceApp(App):
    """The haunted terminal séance."""

    TITLE = "La Tercera Muerte"
    CSS = """
    Screen {
        background: #0d0600;
    }

    #header-area {
        height: 6;
        background: #0d0600;
        border-bottom: solid #3a2a10;
    }

    #project-title {
        text-align: center;
        color: #f5c842;
        text-style: bold;
        height: 3;
        content-align: center middle;
        background: #0d0600;
    }

    #chat-area {
        background: #0d0600;
        scrollbar-color: #3a2a10 #0d0600;
    }

    #input-row {
        height: 5;
        border-top: solid #3a2a10;
        background: #100800;
        padding: 1 2;
    }

    #prompt-label {
        width: 14;
        content-align: center middle;
        color: #c9a86c;
    }

    #user-input {
        background: #0d0600;
        border: solid #3a2a10;
        color: #8ab4d4;
    }

    #user-input:focus {
        border: solid #f5c842;
    }

    #status-bar {
        height: 1;
        background: #0a0400;
        color: #4a3a2a;
        content-align: left middle;
        padding: 0 2;
    }

    Footer {
        background: #0a0400;
        color: #4a3a2a;
    }
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
        self._whisper_task: Optional[asyncio.Task] = None
        self._typing = False

    def compose(self) -> ComposeResult:
        yield CandleRow()
        yield Static(
            f"💀  {self.grave['name']}  💀\n"
            f"[dim]{self.grave.get('language', '?')} · "
            f"{self.grave['born'][:10]} – {self.grave['died'][:10]}[/dim]",
            id="project-title",
        )
        with ScrollableContainer(id="chat-area"):
            yield Static(
                "[dim italic]The candles are lit. The séance begins.\n"
                "Ask the ghost anything about its code, its life, its unfinished business.\n"
                "Type [bold]/quit[/bold] to leave. Type [bold]/whisper[/bold] to call a whisper.[/dim]",
                id="intro",
                markup=True,
            )
        with Horizontal(id="input-row"):
            yield Static("🕯️ You › ", id="prompt-label")
            yield Input(placeholder="Speak to the spirit...", id="user-input")
        yield Static("Idle...", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Start the idle whisper watcher."""
        self.set_interval(5, self._check_idle)
        self._send_opening_message()

    def _send_opening_message(self) -> None:
        """The ghost introduces itself."""
        opening = (
            f"*The candles flicker...*\n\n"
            f"I am **{self.grave['name']}**. "
            f"I was born `{self.grave['born'][:10]}` and fell silent `{self.grave['died'][:10]}`.\n\n"
            f"My last words were: *\"{self.grave['last_commit']['message'][:100]}\"*\n\n"
            f"I remember {len(self.grave.get('dependencies', []))} beloved dependencies, "
            f"{self.grave.get('total_commits', 0)} moments of life, "
            f"and {len(self.grave.get('unfinished_todos', []))} things left undone.\n\n"
            f"Ask me anything."
        )
        self.call_after_refresh(self._show_ghost_message, opening)

    def call_after_refresh(self, fn, *args):
        async def _run():
            await asyncio.sleep(0.5)
            fn(*args)
        asyncio.create_task(_run())

    def _show_ghost_message(self, text: str) -> None:
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        msg = GhostMessage(text, markup=True)
        chat_area.mount(msg)
        chat_area.scroll_end(animate=False)

    def _show_user_message(self, text: str) -> None:
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        msg = UserMessage(f"[bold]You:[/bold] {text}", markup=True)
        chat_area.mount(msg)
        chat_area.scroll_end(animate=False)

    def _show_whisper(self, text: str) -> None:
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        msg = WhisperMessage(f"*…{text}…*", markup=True)
        chat_area.mount(msg)
        chat_area.scroll_end(animate=False)

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#status-bar", Static).update(text)
        except Exception:
            pass

    def _check_idle(self) -> None:
        """If the user has been idle, send a whisper."""
        if self._typing:
            return
        idle = time.time() - self._last_activity
        if idle >= _IDLE_SECONDS:
            self._last_activity = time.time()  # reset so it doesn't spam
            asyncio.create_task(self._do_whisper())

    async def _do_whisper(self) -> None:
        """Generate and show an idle whisper."""
        self._set_status("*something stirs in the silence...*")
        try:
            text = await asyncio.get_event_loop().run_in_executor(
                None,
                llm_whisper,
                self.whisper_prompt,
            )
            self._show_whisper(text)
        except Exception:
            pass
        self._set_status("Listening...")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user pressing Enter."""
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
        """Query the ghost LLM with RAG context."""
        self._typing = True
        self._set_status("🕯️ The spirit stirs...")

        try:
            # Retrieve relevant memories
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

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: chat(messages, stream=False),
            )

            # Add glitch effect occasionally
            response = _maybe_glitch(response)

            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": response})

            self._show_ghost_message(response)

        except Exception as e:
            self._show_ghost_message(
                f"[dim red]*The connection to the spirit world faltered: {e}*[/dim red]",
            )
        finally:
            self._typing = False
            self._set_status("Listening...")

    def action_request_whisper(self) -> None:
        asyncio.create_task(self._do_whisper())

    def action_clear_input(self) -> None:
        self.query_one("#user-input", Input).value = ""


# ---------------------------------------------------------------------------
# Glitch effect
# ---------------------------------------------------------------------------

def _maybe_glitch(text: str) -> str:
    """Occasionally introduce a ghostly glitch into the response."""
    if random.random() > 0.2:  # 20% chance
        return text

    words = text.split()
    if len(words) < 5:
        return text

    idx = random.randint(0, len(words) - 1)
    word = words[idx]
    if len(word) > 3:
        # Repeat a character then "correct" it
        glitched = word[:2] + word[1] + word[2:]
        words[idx] = glitched

    return " ".join(words)


# ---------------------------------------------------------------------------
# Simple fallback CLI séance (no Textual)
# ---------------------------------------------------------------------------

def cli_seance(grave: dict) -> None:
    """
    Minimal CLI séance for environments without a proper terminal.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt

    console = Console(style="on #0d0600")
    system_prompt = build_persona(grave)
    history: list[dict] = []

    console.print(Panel(
        f"[bold yellow]💀 {grave['name']} 💀[/bold yellow]\n"
        f"[dim]{grave.get('language', '?')} · {grave['born'][:10]} – {grave['died'][:10]}[/dim]",
        border_style="dark_orange",
    ))

    console.print(
        f"\n[italic dim]The séance begins. Type [bold]quit[/bold] to leave.[/italic dim]\n"
    )

    while True:
        try:
            user_input = Prompt.ask("[cyan]🕯 You[/cyan]")
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower() in ("quit", "exit", "/q"):
            break

        memories = retrieve(user_input, grave, top_k=3)
        memory_block = ""
        if memories:
            memory_block = "\n\nMemories surfacing:\n" + "\n---\n".join(
                f"[{m['file']}]\n{m['text'][:300]}" for m in memories
            )

        messages = [
            {"role": "system", "content": system_prompt + memory_block},
        ] + history[-8:] + [
            {"role": "user", "content": user_input},
        ]

        console.print("\n[dim yellow]🕯️ The spirit stirs...[/dim yellow]")
        try:
            response = chat(messages, stream=False)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
            console.print(Panel(response, title="[yellow]Ghost[/yellow]", border_style="dark_orange"))
        except Exception as e:
            console.print(f"[red]Connection faltered: {e}[/red]")

    console.print("\n[italic dim]The candles go dark. The séance is over.[/italic dim]\n")
