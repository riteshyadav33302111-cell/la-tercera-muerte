"""
La Tercera Muerte — CLI entry point.

Commands:
  exhume      Parse a repository and generate grave.json
  certificate Print the death certificate
  seance      Open the haunted terminal séance
  resurrect   Run the resurrection agent
  ofrenda     Build the digital altar (OFRENDA.md + ofrenda.html)
  info        Show available Ollama models
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Confirm, Prompt
from rich.text import Text

from . import __version__
from .exhume import exhume, save_grave, load_grave
from .certificate import print_certificate, save_certificate
from .llm import check_ollama, list_models
from .unfinished import detect_unfinished, ghost_names_unfinished

console = Console()
app = typer.Typer(
    name="tercera",
    help="💀 La Tercera Muerte — A local AI séance for dead code.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


def _check_ollama_or_exit() -> None:
    if not check_ollama():
        console.print(
            "[bold red]✗ Cannot reach Ollama.[/bold red] "
            "Make sure Ollama is running: [bold]ollama serve[/bold]"
        )
        raise typer.Exit(1)


def _print_banner() -> None:
    console.print(
        Panel(
            "[bold yellow]💀 La Tercera Muerte 💀[/bold yellow]\n"
            "[dim]In Mexico, they say we die three times.\n"
            "The first death is when the body stops.\n"
            "The second is burial.\n"
            "The third, and the final one, is when nobody says your name anymore.[/dim]",
            border_style="dark_orange",
        )
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def exhume_cmd(
    repo_path: str = typer.Argument(".", help="Path to the git repository to exhume"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save grave.json to .tercera/"),
    show_cert: bool = typer.Option(True, "--cert/--no-cert", help="Print death certificate"),
):
    """
    ⚰️  EXHUMACIÓN — Parse a repository and prepare the grave.

    Extracts git history, contributors, dependencies, TODOs, and
    generates a death certificate.
    """
    _print_banner()
    console.print(f"\n[dim]Exhuming [bold]{repo_path}[/bold]...[/dim]\n")

    try:
        with Progress(
            SpinnerColumn(spinner_name="dots12"),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Reading git history...", total=None)
            grave = exhume(repo_path)
            progress.update(task, description="Analyzing dependencies...")
            if save:
                progress.update(task, description="Saving grave.json...")
                grave_path = save_grave(grave)

        console.print(f"[green]✓[/green] Exhumation complete.")
        if save:
            console.print(f"[dim]  Grave saved to: {grave_path}[/dim]")

        if show_cert:
            console.print()
            print_certificate(grave)

        # Show unfinished business
        business = detect_unfinished(grave)
        if business["primary_task"] != "mystery":
            console.print(
                Panel(
                    f"[bold yellow]⚠ Unfinished Business[/bold yellow]\n\n"
                    f"[italic]{ghost_names_unfinished(business)}[/italic]",
                    border_style="yellow",
                )
            )

    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)


@app.command()
def seance(
    repo_path: str = typer.Argument(".", help="Path to the repository (must be exhumed first)"),
    tui: bool = typer.Option(True, "--tui/--no-tui", help="Use Textual TUI (default: True)"),
    build_memory: bool = typer.Option(
        None, "--memory/--no-memory",
        help="Build RAG memory first (auto-detected if not set)"
    ),
):
    """
    🕯️  LA SESIÓN — Open the haunted terminal séance.

    Talk to the ghost of the repository using local AI.
    Idle for 45 seconds and it will whisper to you.
    """
    _print_banner()
    _check_ollama_or_exit()

    try:
        grave = load_grave(repo_path)
    except FileNotFoundError:
        console.print("[yellow]⚠ No grave found. Running exhumation first...[/yellow]")
        grave = exhume(repo_path)
        save_grave(grave)

    # Build memory if needed
    from .memory import memory_exists, build_memory as _build_memory

    should_build = build_memory
    if should_build is None:
        should_build = not memory_exists(grave)

    if should_build:
        console.print("[dim]Building memory (embedding the codebase)...[/dim]")
        try:
            with Progress(
                SpinnerColumn(spinner_name="dots12"),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Embedding...", total=100)

                def _cb(i, total, fname):
                    progress.update(task, completed=int(i / max(total, 1) * 100),
                                    description=f"Embedding {fname[:40]}...")

                count = _build_memory(grave, progress_cb=_cb)
                progress.update(task, completed=100)

            console.print(f"[green]✓[/green] Memory built: {count} chunks embedded.")
        except ImportError:
            console.print(
                "[yellow]⚠ lancedb not installed — RAG memory disabled.[/yellow]\n"
                "[dim]  pip install lancedb pyarrow[/dim]"
            )
        except Exception as e:
            console.print(f"[yellow]⚠ Memory build failed: {e} — continuing without RAG.[/yellow]")

    # Launch séance
    if tui:
        try:
            from .seance_tui import SeanceApp
            SeanceApp(grave).run()
        except ImportError:
            console.print("[yellow]⚠ Textual not installed — falling back to CLI séance.[/yellow]")
            from .seance_tui import cli_seance
            cli_seance(grave)
        except Exception as e:
            console.print(f"[yellow]⚠ TUI error ({e}) — falling back to CLI séance.[/yellow]")
            from .seance_tui import cli_seance
            cli_seance(grave)
    else:
        from .seance_tui import cli_seance
        cli_seance(grave)


@app.command()
def resurrect_cmd(
    repo_path: str = typer.Argument(".", help="Path to the repository"),
    attempts: int = typer.Option(5, "--attempts", "-a", help="Max repair attempts"),
    no_docker: bool = typer.Option(False, "--no-docker", help="Skip Docker, run locally (less safe)"),
):
    """
    ✨  RESURRECCIÓN — Run the open-source coding agent to fix unfinished business.

    The agent works inside a Docker sandbox (safe) or locally (fast).
    """
    _print_banner()
    _check_ollama_or_exit()

    try:
        grave = load_grave(repo_path)
    except FileNotFoundError:
        console.print("[yellow]⚠ No grave found. Running exhumation first...[/yellow]")
        grave = exhume(repo_path)
        save_grave(grave)

    business = detect_unfinished(grave)
    console.print(Panel(
        f"[bold yellow]⚰ Unfinished Business[/bold yellow]\n\n"
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
        console=console,
    ) as progress:
        task = progress.add_task("Resurrection in progress...", total=attempts)

        def _cb(attempt, total, msg):
            progress.update(task, completed=attempt, description=msg)

        result = resurrect(grave, progress_cb=_cb)
        progress.update(task, completed=attempts)

    if result["success"]:
        console.print(Panel(
            f"[bold green]{result['message']}[/bold green]\n\n"
            f"[dim]Resolved in {result['attempts']} attempt(s).[/dim]",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold red]{result['message']}[/bold red]\n\n"
            f"[dim]The spirit remains restless after {result['attempts']} attempts.[/dim]",
            border_style="red",
        ))

    # Save resurrection result
    import json
    res_path = Path(grave["path"]) / ".tercera" / "resurrection.json"
    res_path.parent.mkdir(parents=True, exist_ok=True)
    with open(res_path, "w") as f:
        json.dump(result, f, indent=2)

    return result


@app.command()
def ofrenda_cmd(
    repo_path: str = typer.Argument(".", help="Path to the repository"),
    commit: bool = typer.Option(False, "--commit", help="Commit the ofrenda to git"),
    open_html: bool = typer.Option(True, "--open/--no-open", help="Open the HTML in browser"),
):
    """
    🌼  LA OFRENDA — Build the digital altar.

    Creates OFRENDA.md and ofrenda.html honoring the project and contributors.
    """
    _print_banner()

    try:
        grave = load_grave(repo_path)
    except FileNotFoundError:
        grave = exhume(repo_path)
        save_grave(grave)

    # Load resurrection result if it exists
    import json
    res_path = Path(grave["path"]) / ".tercera" / "resurrection.json"
    resurrection = None
    if res_path.exists():
        try:
            with open(res_path) as f:
                resurrection = json.load(f)
        except Exception:
            pass

    # Generate epitaph with LLM (optional)
    epitaph = None
    if check_ollama():
        console.print("[dim]Summoning epitaph...[/dim]")
        try:
            from .llm import chat
            epitaph_resp = chat(
                [{"role": "user", "content":
                  f"Write a single poetic epitaph (1-2 sentences, max 200 chars) for the software project "
                  f"\"{grave['name']}\" ({grave.get('language', 'software')}, "
                  f"born {grave['born'][:10]}, died {grave['died'][:10]}). "
                  f"Cause of death: {grave.get('cause_of_death', 'unknown')}. "
                  f"Be lyrical, not technical. No quotes, no attribution."}],
                temperature=0.9,
            )
            epitaph = epitaph_resp.strip()
        except Exception:
            pass

    from .ofrenda import save_ofrenda

    with Progress(
        SpinnerColumn(spinner_name="dots12"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        t = progress.add_task("Building the altar...", total=None)
        md_path, html_path = save_ofrenda(grave, resurrection, epitaph, commit=commit)

    console.print(f"[green]✓[/green] Ofrenda created:")
    console.print(f"  📜 [dim]{md_path}[/dim]")
    console.print(f"  🌐 [dim]{html_path}[/dim]")

    if commit:
        console.print("[green]✓[/green] Committed to git.")

    if open_html:
        import webbrowser
        try:
            webbrowser.open(f"file://{html_path}")
        except Exception:
            pass


@app.command()
def full_ritual(
    repo_path: str = typer.Argument(".", help="Path to the repository to perform all rituals on"),
):
    """
    💀  THE FULL RITUAL — Exhume, séance, resurrect, and build the ofrenda.

    Performs all five rituals in sequence for a complete experience.
    """
    ctx = typer.get_current_context()

    console.print("\n[bold yellow]The five rituals begin...[/bold yellow]\n")

    # 1. Exhumation
    console.rule("[yellow]Ritual 1: Exhumación[/yellow]")
    ctx.invoke(exhume_cmd, repo_path=repo_path, save=True, show_cert=True)

    # 2. Check Ollama before continuing
    _check_ollama_or_exit()

    # 3. Séance
    console.rule("[yellow]Ritual 2: La Sesión[/yellow]")
    if Confirm.ask("Open the séance?", default=True):
        ctx.invoke(seance, repo_path=repo_path, tui=True)

    # 4. Resurrection
    console.rule("[yellow]Ritual 3: La Resurrección[/yellow]")
    ctx.invoke(resurrect_cmd, repo_path=repo_path, attempts=5)

    # 5. Ofrenda
    console.rule("[yellow]Ritual 4: La Ofrenda[/yellow]")
    ctx.invoke(ofrenda_cmd, repo_path=repo_path, commit=False)

    console.print(Panel(
        "[bold yellow]The rituals are complete.[/bold yellow]\n\n"
        "[italic]La tercera muerte es cuando nadie pronuncia tu nombre.\n"
        "Hoy pronunciamos tu nombre.[/italic]",
        border_style="dark_orange",
    ))


@app.command()
def info():
    """
    ℹ️  Show system info: Ollama status, available models.
    """
    console.print(f"[bold]La Tercera Muerte[/bold] v{__version__}\n")

    if check_ollama():
        console.print("[green]✓ Ollama is running[/green]")
        models = list_models()
        if models:
            console.print("\nAvailable models:")
            for m in models:
                console.print(f"  [dim]•[/dim] {m}")
        else:
            console.print("[yellow]No models pulled yet.[/yellow]")
            console.print("Pull the recommended models:")
            console.print("  [dim]ollama pull llama3.1:8b[/dim]")
            console.print("  [dim]ollama pull qwen2.5-coder:7b[/dim]")
            console.print("  [dim]ollama pull nomic-embed-text[/dim]")
    else:
        console.print("[red]✗ Ollama is not running[/red]")
        console.print("Start it with: [bold]ollama serve[/bold]")


def main():
    app()


if __name__ == "__main__":
    main()
