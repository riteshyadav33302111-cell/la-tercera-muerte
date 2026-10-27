"""
La Tercera Muerte — CLI entry point.

Commands:
  exhume      Parse a repository and generate grave.json
  seance      Open the haunted terminal séance
  resurrect   Run the resurrection agent
  ofrenda     Build the digital altar (OFRENDA.md + ofrenda.html)
  full-ritual All five rituals in sequence
  info        Show available Ollama models
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from . import __version__
from .certificate import print_certificate, save_certificate
from .exhume import exhume, load_grave, save_grave
from .llm import check_ollama, list_models
from .unfinished import detect_unfinished, ghost_names_unfinished

console = Console(markup=False, emoji=False, highlight=False)
console_markup = Console()   # used only for Rich Panel/Progress where markup is needed

app = typer.Typer(
    name="tercera",
    help="La Tercera Muerte -- A local AI seance for dead code.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


def _check_ollama_or_exit() -> None:
    if not check_ollama():
        console_markup.print(
            "[bold red]Cannot reach Ollama.[/bold red] "
            "Make sure it is running: [bold]ollama serve[/bold]"
        )
        raise typer.Exit(1)


def _print_banner() -> None:
    console_markup.print(Panel(
        "[bold yellow]La Tercera Muerte[/bold yellow]\n"
        "[dim]In Mexico, they say we die three times.\n"
        "The first death is when the body stops.\n"
        "The second is burial.\n"
        "The third, and final, is when nobody says your name anymore.[/dim]",
        border_style="dark_orange",
    ))


# ---------------------------------------------------------------------------
# exhume
# ---------------------------------------------------------------------------

@app.command("exhume")
def exhume_cmd(
    repo_path: str = typer.Argument(".", help="Path to the git repository to exhume"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save grave.json to .tercera/"),
    show_cert: bool = typer.Option(True, "--cert/--no-cert", help="Print death certificate"),
) -> None:
    """Exhumacion -- parse a repository and prepare the grave."""
    _print_banner()
    console_markup.print(f"\n[dim]Exhuming [bold]{repo_path}[/bold]...[/dim]\n")

    try:
        with Progress(
            SpinnerColumn(spinner_name="dots12"),
            TextColumn("[progress.description]{task.description}"),
            console=console_markup,
            transient=True,
        ) as progress:
            task = progress.add_task("Reading git history...", total=None)
            grave = exhume(repo_path)
            if save:
                progress.update(task, description="Saving grave.json...")
                grave_path = save_grave(grave)

        console_markup.print("[green]Exhumation complete.[/green]")
        if save:
            console_markup.print(f"[dim]  Grave saved to: {grave_path}[/dim]")

        if show_cert:
            console_markup.print()
            print_certificate(grave)

        business = detect_unfinished(grave)
        if business["primary_task"] != "mystery":
            console_markup.print(Panel(
                f"[bold yellow]Unfinished Business[/bold yellow]\n\n"
                f"[italic]{ghost_names_unfinished(business)}[/italic]",
                border_style="yellow",
            ))

    except FileNotFoundError as e:
        console_markup.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console_markup.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# seance
# ---------------------------------------------------------------------------

@app.command("seance")
def seance_cmd(
    repo_path: str = typer.Argument(".", help="Path to the repository"),
    tui: bool = typer.Option(True, "--tui/--no-tui", help="Use Textual TUI"),
    build_memory: bool = typer.Option(
        None, "--memory/--no-memory",
        help="Build RAG memory first (auto-detected if not set)",
    ),
) -> None:
    """La Sesion -- open the haunted terminal seance."""
    _print_banner()
    _check_ollama_or_exit()

    try:
        grave = load_grave(repo_path)
    except FileNotFoundError:
        console_markup.print("[yellow]No grave found. Running exhumation first...[/yellow]")
        grave = exhume(repo_path)
        save_grave(grave)

    from .memory import build_memory as _build_memory, memory_exists

    should_build = build_memory
    if should_build is None:
        should_build = not memory_exists(grave)

    if should_build:
        console_markup.print("[dim]Building memory (embedding the codebase)...[/dim]")
        try:
            with Progress(
                SpinnerColumn(spinner_name="dots12"),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console_markup,
                transient=True,
            ) as progress:
                task = progress.add_task("Embedding...", total=100)

                def _cb(i: int, total: int, fname: str) -> None:
                    progress.update(
                        task,
                        completed=int(i / max(total, 1) * 100),
                        description=f"Embedding {fname[:40]}...",
                    )

                count = _build_memory(grave, progress_cb=_cb)
                progress.update(task, completed=100)

            console_markup.print(f"[green]Memory built: {count} chunks embedded.[/green]")
        except ImportError:
            console_markup.print(
                "[yellow]lancedb not installed -- RAG memory disabled.[/yellow]\n"
                "[dim]  pip install lancedb pyarrow[/dim]"
            )
        except Exception as e:
            console_markup.print(f"[yellow]Memory build failed: {e} -- continuing without RAG.[/yellow]")

    if tui:
        try:
            from .seance_tui import SeanceApp
            SeanceApp(grave).run()
        except ImportError:
            console_markup.print("[yellow]Textual not installed -- falling back to CLI seance.[/yellow]")
            from .seance_tui import cli_seance
            cli_seance(grave)
        except Exception as e:
            console_markup.print(f"[yellow]TUI error ({e}) -- falling back to CLI seance.[/yellow]")
            from .seance_tui import cli_seance
            cli_seance(grave)
    else:
        from .seance_tui import cli_seance
        cli_seance(grave)


# ---------------------------------------------------------------------------
# resurrect
# ---------------------------------------------------------------------------

@app.command("resurrect")
def resurrect_cmd(
    repo_path: str = typer.Argument(".", help="Path to the repository"),
    attempts: int = typer.Option(5, "--attempts", "-a", help="Max repair attempts"),
    no_docker: bool = typer.Option(
        False, "--no-docker", "--unsafe-local",
        help="Skip Docker, run locally on a temp copy (opt-in, no sandbox)",
    ),
) -> None:
    """Resurreccion -- run the coding agent to fix unfinished business."""
    _print_banner()
    _check_ollama_or_exit()

    try:
        grave = load_grave(repo_path)
    except FileNotFoundError:
        grave = exhume(repo_path)
        save_grave(grave)

    business = detect_unfinished(grave)
    console_markup.print(Panel(
        f"[bold yellow]Unfinished Business[/bold yellow]\n\n"
        f"[italic]{ghost_names_unfinished(business)}[/italic]",
        border_style="yellow",
    ))

    if not Confirm.ask("Attempt resurrection?"):
        raise typer.Exit(0)

    from .resurrect import resurrect

    with Progress(
        SpinnerColumn(spinner_name="moon"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console_markup,
    ) as progress:
        task = progress.add_task("Resurrection in progress...", total=attempts)

        def _cb(attempt: int, total: int, msg: str) -> None:
            progress.update(task, completed=attempt, description=msg)

        result = resurrect(
            grave,
            attempts=attempts,
            no_docker=no_docker,
            progress_cb=_cb,
        )
        progress.update(task, completed=attempts)

    style = "green" if result["success"] else "red"
    console_markup.print(Panel(
        f"[bold {style}]{result['message']}[/bold {style}]\n\n"
        f"[dim]Attempts: {result['attempts']}[/dim]",
        border_style=style,
    ))

    import json
    res_path = Path(grave["path"]) / ".tercera" / "resurrection.json"
    res_path.parent.mkdir(parents=True, exist_ok=True)
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


# ---------------------------------------------------------------------------
# ofrenda
# ---------------------------------------------------------------------------

@app.command("ofrenda")
def ofrenda_cmd(
    repo_path: str = typer.Argument(".", help="Path to the repository"),
    commit: bool = typer.Option(False, "--commit", help="Commit the ofrenda to git"),
    open_html: bool = typer.Option(True, "--open/--no-open", help="Open the HTML in browser"),
) -> None:
    """La Ofrenda -- build the digital altar."""
    _print_banner()

    try:
        grave = load_grave(repo_path)
    except FileNotFoundError:
        grave = exhume(repo_path)
        save_grave(grave)

    import json
    res_path = Path(grave["path"]) / ".tercera" / "resurrection.json"
    resurrection = None
    if res_path.exists():
        try:
            with open(res_path, encoding="utf-8") as f:
                resurrection = json.load(f)
        except Exception:
            pass

    epitaph: str | None = None
    if check_ollama():
        console_markup.print("[dim]Summoning epitaph...[/dim]")
        try:
            from .llm import chat
            epitaph = chat(
                [{"role": "user", "content":
                  f"Write a single poetic epitaph (1-2 sentences, max 200 chars) for the software project "
                  f'"{grave["name"]}" ({grave.get("language", "software")}, '
                  f'born {grave["born"][:10]}, died {grave["died"][:10]}). '
                  f'Cause of death: {grave.get("cause_of_death", "unknown")}. '
                  f"Be lyrical, not technical. No quotes, no attribution."}],
                temperature=0.9,
            ).strip()
        except Exception:
            pass

    from .ofrenda import save_ofrenda

    with Progress(
        SpinnerColumn(spinner_name="dots12"),
        TextColumn("[progress.description]{task.description}"),
        console=console_markup,
        transient=True,
    ) as progress:
        t = progress.add_task("Building the altar...", total=None)
        md_path, html_path = save_ofrenda(grave, resurrection, epitaph, commit=commit)

    console_markup.print("[green]Ofrenda created:[/green]")
    console_markup.print(f"  [dim]{md_path}[/dim]")
    console_markup.print(f"  [dim]{html_path}[/dim]")

    if commit:
        console_markup.print("[green]Committed to git.[/green]")

    if open_html:
        try:
            webbrowser.open(html_path.as_uri())
        except Exception:
            pass


# ---------------------------------------------------------------------------
# full-ritual
# ---------------------------------------------------------------------------

@app.command("full-ritual")
def full_ritual_cmd(
    repo_path: str = typer.Argument(".", help="Path to the repository"),
    attempts: int = typer.Option(5, "--attempts", "-a", help="Max resurrection attempts"),
    no_docker: bool = typer.Option(False, "--no-docker", "--unsafe-local", help="Skip Docker sandbox"),
) -> None:
    """All five rituals in sequence."""
    ctx = typer.get_current_context()

    console_markup.print("\n[bold yellow]The five rituals begin...[/bold yellow]\n")

    console_markup.rule("[yellow]Ritual 1: Exhumacion[/yellow]")
    ctx.invoke(exhume_cmd, repo_path=repo_path, save=True, show_cert=True)

    _check_ollama_or_exit()

    console_markup.rule("[yellow]Ritual 2: La Sesion[/yellow]")
    if Confirm.ask("Open the seance?", default=True):
        ctx.invoke(seance_cmd, repo_path=repo_path, tui=True, build_memory=None)

    console_markup.rule("[yellow]Ritual 3: La Resurreccion[/yellow]")
    ctx.invoke(resurrect_cmd, repo_path=repo_path, attempts=attempts, no_docker=no_docker)

    console_markup.rule("[yellow]Ritual 4: La Ofrenda[/yellow]")
    ctx.invoke(ofrenda_cmd, repo_path=repo_path, commit=False, open_html=True)

    console_markup.print(Panel(
        "[bold yellow]The rituals are complete.[/bold yellow]\n\n"
        "[italic]La tercera muerte es cuando nadie pronuncia tu nombre.\n"
        "Hoy pronunciamos tu nombre.[/italic]",
        border_style="dark_orange",
    ))


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------

@app.command("info")
def info_cmd() -> None:
    """Show system info: Ollama status and available models."""
    console_markup.print(f"[bold]La Tercera Muerte[/bold] v{__version__}\n")

    if check_ollama():
        console_markup.print("[green]Ollama is running[/green]")
        models = list_models()
        if models:
            console_markup.print("\nAvailable models:")
            for m in models:
                console_markup.print(f"  [dim]bullet[/dim] {m}")
        else:
            console_markup.print("[yellow]No models pulled yet.[/yellow]")
            console_markup.print("Pull the recommended models:")
            console_markup.print("  ollama pull llama3.1:8b")
            console_markup.print("  ollama pull qwen2.5-coder:7b")
            console_markup.print("  ollama pull nomic-embed-text")
    else:
        console_markup.print("[red]Ollama is not running[/red]")
        console_markup.print("Start it with: ollama serve")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
