"""
La Sesion -- The haunted terminal seance.

Redesigned UI:
- Real animated candle flames (multi-frame ASCII art)
- Marigold / skull decorative header
- Gothic atmosphere: deep amber on near-black
- Typewriter streaming responses
- Papel picado divider between messages
- Idle whispers
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
from textual.containers import Horizontal, ScrollableContainer, Vertical
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
# Candle flame animation
# ---------------------------------------------------------------------------

# Each frame is a 3-line ASCII candle (tip / body / base)
_FLAME_FRAMES = [
    ["   ) ",
     "  ( )",
     "  )/ "],
    ["  .) ",
     "  ( )",
     "  (/ "],
    ["  (. ",
     " .( )",
     "  )/ "],
    ["  .) ",
     "  () ",
     " .() "],
]

_CANDLE_BODY = [
    " |||||",
    " |||||",
    "_|||||_",
]

_FLAME_COLORS = ["bold yellow", "bold gold1", "bold orange1", "yellow", "gold1"]
_WAX_COLOR    = "#d4aa70"
_BASE_COLOR   = "#8B5E3C"


class CandleWidget(Widget):
    """A single animated ASCII candle."""
    DEFAULT_CSS = """
    CandleWidget {
        width: 9;
        height: 7;
        content-align: center middle;
        background: #0d0400;
    }
    """
    frame: reactive[int] = reactive(0)

    def on_mount(self) -> None:
        # Each candle flickers at a slightly different rate for realism
        rate = 0.12 + random.random() * 0.2
        self.set_interval(rate, self._flicker)

    def _flicker(self) -> None:
        self.frame = (self.frame + 1) % len(_FLAME_FRAMES)
        self.refresh()

    def render(self):
        from rich.text import Text
        from rich.console import RenderableType
        color = random.choice(_FLAME_COLORS)
        flame = _FLAME_FRAMES[self.frame % len(_FLAME_FRAMES)]
        t = Text()
        for fl in flame:
            t.append(fl + "\n", style=color)
        for i, bl in enumerate(_CANDLE_BODY):
            style = _WAX_COLOR if i < 2 else _BASE_COLOR
            t.append(bl + "\n", style=style)
        return t


class CandleRow(Widget):
    """A row of candles with marigold decorations between them."""
    DEFAULT_CSS = """
    CandleRow {
        height: 8;
        background: #0d0400;
        content-align: center middle;
        layout: horizontal;
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("  [bold yellow]✦[/bold yellow]  [dark_orange]❧[/dark_orange]  [bold yellow]✦[/bold yellow]  ", id="deco-left")
        yield CandleWidget()
        yield Static("  [dark_orange]✿[/dark_orange] [yellow]✾[/yellow] [dark_orange]✿[/dark_orange]  ", id="deco-mid-l")
        yield CandleWidget()
        yield Static("  [yellow]❀[/yellow] [dark_orange]✿[/dark_orange] [yellow]❀[/yellow]  ", id="deco-mid-r")
        yield CandleWidget()
        yield Static("  [bold yellow]✦[/bold yellow]  [dark_orange]❧[/dark_orange]  [bold yellow]✦[/bold yellow]  ", id="deco-right")


# ---------------------------------------------------------------------------
# Papel picado divider
# ---------------------------------------------------------------------------

_PICADO = "━━ ✦ ━━━ 💀 ━━━ ✦ ━━"

class PicadoDivider(Static):
    DEFAULT_CSS = """
    PicadoDivider {
        color: #3a2210;
        text-align: center;
        height: 1;
        margin: 0 2;
    }
    """
    def __init__(self):
        super().__init__(_PICADO)


# ---------------------------------------------------------------------------
# Message widgets
# ---------------------------------------------------------------------------

def _md_to_rich(text: str) -> str:
    safe = rich_escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"[bold]\1[/bold]", safe)
    safe = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"[italic]\1[/italic]", safe)
    return safe


class GhostMessage(Static):
    DEFAULT_CSS = """
    GhostMessage {
        margin: 0 2 0 2;
        padding: 1 3;
        border-left: outer #8B4513;
        border-right: outer #0d0400;
        background: #120900;
        color: #d4aa70;
    }
    """


class UserMessage(Static):
    DEFAULT_CSS = """
    UserMessage {
        margin: 0 2 0 2;
        padding: 1 3;
        border-left: outer #1a3a5a;
        background: #08101a;
        color: #7ab8d4;
        text-align: right;
    }
    """


class WhisperMessage(Static):
    DEFAULT_CSS = """
    WhisperMessage {
        margin: 0 6;
        padding: 0 2;
        color: #5a3d20;
        text-style: italic;
        text-align: center;
    }
    """


# ---------------------------------------------------------------------------
# Project header
# ---------------------------------------------------------------------------

class ProjectHeader(Static):
    DEFAULT_CSS = """
    ProjectHeader {
        height: 5;
        content-align: center middle;
        text-align: center;
        background: #0d0400;
        color: #f5c518;
        padding: 1 0;
    }
    """


# ---------------------------------------------------------------------------
# Seance App
# ---------------------------------------------------------------------------

class SeanceApp(App):
    TITLE = "💀 La Tercera Muerte"

    CSS = """
    Screen {
        background: #0d0400;
        layers: base overlay;
    }

    /* ── Top bar ── */
    #top-bar {
        height: auto;
        background: #0d0400;
        border-bottom: solid #3a1f00;
    }

    /* ── Skull banner ── */
    #skull-banner {
        height: 3;
        background: #0a0300;
        color: #3a1f00;
        content-align: center middle;
        text-align: center;
        border-bottom: solid #1e0f00;
    }

    /* ── Chat area ── */
    #chat-area {
        background: #0d0400;
        scrollbar-color: #3a1f00 #0d0400;
        border: none;
        padding: 0 0 1 0;
    }

    /* ── Intro text ── */
    #intro {
        margin: 1 3;
        color: #5a3d20;
        text-style: italic;
        text-align: center;
    }

    /* ── Input row ── */
    #input-row {
        height: 5;
        border-top: double #3a1f00;
        background: #0a0300;
        padding: 1 2;
        align: left middle;
    }
    #prompt-label {
        width: 12;
        content-align: left middle;
        color: #f5c518;
        text-style: bold;
    }
    #user-input {
        background: #0d0400;
        border: solid #3a1f00;
        color: #8ab4d4;
    }
    #user-input:focus {
        border: solid #f5c518;
    }

    /* ── Status bar ── */
    #status-bar {
        height: 1;
        background: #080200;
        color: #3a2210;
        content-align: left middle;
        padding: 0 2;
    }

    Footer {
        background: #080200;
        color: #3a2210;
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
        self._typing = False

    def compose(self) -> ComposeResult:
        with Vertical(id="top-bar"):
            yield CandleRow()
            yield ProjectHeader(
                f"[bold yellow]{rich_escape(self.grave['name'])}[/bold yellow]\n"
                f"[dim]{self.grave.get('language', '?')}  |  "
                f"[cyan]{self.grave['born'][:10]}[/cyan]  —  "
                f"[cyan]{self.grave['died'][:10]}[/cyan][/dim]"
            )
            yield Static(
                "  💀  " * 19,
                id="skull-banner",
            )

        with ScrollableContainer(id="chat-area"):
            yield Static(
                "[italic]The candles are lit. The séance begins.\n"
                "Ask the ghost anything.  /quit to leave  ·  /whisper for a whisper  ·  Ctrl+W[/italic]",
                id="intro",
            )

        with Horizontal(id="input-row"):
            yield Static("🕯  You > ", id="prompt-label")
            yield Input(placeholder="Speak to the spirit...", id="user-input")

        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(5, self._check_idle)
        self._schedule_opening()

    def _schedule_opening(self) -> None:
        async def _run():
            await asyncio.sleep(0.7)
            name    = rich_escape(self.grave["name"])
            born    = self.grave["born"][:10]
            died    = self.grave["died"][:10]
            lw      = rich_escape(self.grave["last_commit"]["message"][:120])
            deps    = len(self.grave.get("dependencies", []))
            commits = self.grave.get("total_commits", 0)
            todos   = len(self.grave.get("unfinished_todos", []))
            silence = self.grave.get("silence_days", 0) // 365

            self._show_ghost_message(
                f"[dim italic]*The candles flicker...*[/dim italic]\n\n"
                f"I am [bold yellow]{name}[/bold yellow].  "
                f"Born [cyan]{born}[/cyan], silenced [cyan]{died}[/cyan].\n\n"
                f"My last words were:\n"
                f"[italic dim]\"{lw}\"[/italic dim]\n\n"
                f"[dim]I carry {deps} dependencies, {commits} moments of life, "
                f"{todos} things left undone,\n"
                f"and {silence} years of silence.[/dim]\n\n"
                f"[bold]Ask me anything.[/bold]"
            )
        asyncio.create_task(_run())

    # ── Message helpers ──────────────────────────────────────────────────────

    def _show_ghost_message(self, markup: str) -> None:
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        chat_area.mount(PicadoDivider())
        msg = GhostMessage(markup)
        chat_area.mount(msg)
        self.call_after_refresh(chat_area.scroll_end, animate=False)

    def _show_user_message(self, text: str) -> None:
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        safe = rich_escape(text)
        msg = UserMessage(f"[bold cyan]You:[/bold cyan]  {safe}")
        chat_area.mount(msg)
        self.call_after_refresh(chat_area.scroll_end, animate=False)

    def _show_whisper(self, text: str) -> None:
        chat_area = self.query_one("#chat-area", ScrollableContainer)
        safe = rich_escape(text)
        msg = WhisperMessage(f"[dim]✦  {safe}  ✦[/dim]")
        chat_area.mount(msg)
        self.call_after_refresh(chat_area.scroll_end, animate=False)

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#status-bar", Static).update(text)
        except Exception:
            pass

    # ── Idle whisper ─────────────────────────────────────────────────────────

    def _check_idle(self) -> None:
        if self._typing:
            return
        idle = time.time() - self._last_activity
        if idle >= _IDLE_SECONDS:
            self._last_activity = time.time()
            asyncio.create_task(self._do_whisper())

    async def _do_whisper(self) -> None:
        self._set_status("[dim italic]✦  something stirs in the silence...  ✦[/dim italic]")
        try:
            text = await asyncio.get_event_loop().run_in_executor(
                None, llm_whisper, self.whisper_prompt
            )
            self._show_whisper(text)
        except Exception:
            pass
        self._set_status("[dim]Listening...[/dim]")

    # ── Input handling ────────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        self._last_activity = time.time()
        self._typing = bool(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        self._last_activity = time.time()
        self._typing = False

        if text.lower() in ("/quit", "/q", "quit", "exit"):
            self.exit()
            return
        if text.lower() in ("/whisper", "/w"):
            asyncio.create_task(self._do_whisper())
            return

        self._show_user_message(text)
        asyncio.create_task(self._get_ghost_response(text))

    async def _get_ghost_response(self, user_text: str) -> None:
        """Stream the ghost's response token-by-token."""
        self._typing = True
        self._set_status("[dim italic]The spirit stirs...[/dim italic]")

        chat_area = self.query_one("#chat-area", ScrollableContainer)
        chat_area.mount(PicadoDivider())
        msg_widget = GhostMessage("[dim italic]...[/dim italic]")
        await chat_area.mount(msg_widget)
        self.call_after_refresh(chat_area.scroll_end, animate=False)

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

            accumulated = ""

            def _stream_sync():
                nonlocal accumulated
                for token in chat(messages, stream=True):
                    accumulated += token
                    self.call_from_thread(
                        msg_widget.update,
                        _md_to_rich(accumulated),
                    )
                return accumulated

            full_response = await asyncio.get_event_loop().run_in_executor(
                None, _stream_sync
            )

            msg_widget.update(_md_to_rich(full_response))
            self.call_after_refresh(chat_area.scroll_end, animate=False)

            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": full_response})

        except Exception as e:
            msg_widget.update(
                f"[dim red italic]*The connection faltered: {rich_escape(str(e))}*[/dim red italic]"
            )
        finally:
            self._typing = False
            self._set_status("[dim]Listening...[/dim]")

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
        title="💀 La Tercera Muerte",
    ))
    console.print("\n[italic dim]Séance begun. Type [bold]quit[/bold] to leave.[/italic dim]\n")

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
                title="[yellow]👻 Ghost[/yellow]",
                border_style="dark_orange",
            ))
        except Exception as e:
            console.print(f"[red]Connection faltered: {rich_escape(str(e))}[/red]")

    console.print("\n[italic dim]The candles go dark. The séance is over.[/italic dim]\n")
