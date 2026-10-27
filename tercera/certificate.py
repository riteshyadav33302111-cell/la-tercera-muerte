"""
Certificate of Death -- Acta de Defuncion.

Built in plain Python with a row() helper so the border always lines up
regardless of which Jinja2 filters exist. Printed with markup=False,
emoji=False, highlight=False so the box characters survive any terminal.
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path


# Width of the inner content area (between the side borders)
_W = 70


def _row(text: str = "") -> str:
    """Return one certificate line padded to _W chars with side borders."""
    return f"| {text.ljust(_W)} |"


def _divider(label: str = "") -> str:
    if label:
        # inner must be _W+2 chars wide (same as the unlabeled "=" divider)
        # "-- LABEL " occupies len(label)+4 chars, so fill the rest with dashes
        dashes = max(1, _W + 2 - len(label) - 4)
        inner = f"-- {label} " + "-" * dashes
    else:
        inner = "=" * (_W + 2)
    return f"+{inner}+"


def _wrap(text: str, width: int = _W - 2) -> list[str]:
    lines = textwrap.wrap(str(text), width=width)
    return lines if lines else [""]


def _fmt_duration(days: int) -> str:
    if days < 0:
        return "unknown"
    years, rem = divmod(days, 365)
    months = rem // 30
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    return ", ".join(parts) if parts else f"{days} days"


def generate_certificate(grave: dict) -> str:
    born = datetime.fromisoformat(grave["born"]).strftime("%B %d, %Y")
    died = datetime.fromisoformat(grave["died"]).strftime("%B %d, %Y")
    today = datetime.now().strftime("%B %d, %Y")
    age = _fmt_duration(grave.get("age_days", 0))
    silence = _fmt_duration(grave.get("silence_days", 0))

    lines: list[str] = []
    a = lines.append

    a(_divider())
    a(_row("*** ACTA DE DEFUNCION  /  CERTIFICATE OF DEATH ***".center(_W)))
    a(_divider())
    a(_row())
    a(_row(f"Nombre / Name:    {grave['name'][:52]}"))
    a(_row(f"Language:         {grave.get('language', 'Unknown')[:52]}"))
    a(_row())
    a(_divider("VIDA / LIFE"))
    a(_row())
    a(_row(f"Born:   {born}"))
    a(_row(f"First words:"))
    for ln in _wrap(grave["first_commit"]["message"]):
        a(_row(f"  {ln}"))
    a(_row())
    a(_row(f"Total commits: {grave.get('total_commits', 0)}"))
    a(_row(f"Age:           {age}"))
    a(_row())
    a(_divider("MUERTE / DEATH"))
    a(_row())
    a(_row(f"Died:    {died}"))
    a(_row(f"Silent for {silence}"))
    a(_row(f"Last words:"))
    for ln in _wrap(grave["last_commit"]["message"]):
        a(_row(f"  {ln}"))
    a(_row())
    a(_row(f"Cause of death:"))
    for ln in _wrap(grave.get("cause_of_death", "Unknown")):
        a(_row(f"  {ln}"))
    a(_row())
    a(_divider("FAMILIA / FAMILY"))
    a(_row())
    a(_row("Those who made it:"))
    for name, count in grave.get("family", [])[:8]:
        a(_row(f"  * {name} ({count} commits)"))
    a(_row())
    a(_divider("ASUNTOS PENDIENTES / UNFINISHED BUSINESS"))
    a(_row())
    todos = grave.get("unfinished_todos", [])
    if todos:
        for t in todos[:5]:
            loc = f"{t['file']}:{t['line']}"[:28]
            a(_row(f"  {t['kind']}: {loc}"))
            for ln in _wrap(t["text"], width=_W - 6):
                a(_row(f"    {ln}"))
    else:
        a(_row("  None found. Perhaps it found peace after all."))
    a(_row())
    a(_divider("DEPENDENCIAS / DEPENDENCIES"))
    a(_row())
    deps = grave.get("dependencies", [])
    dep_line = ", ".join(deps[:8])
    for ln in _wrap(dep_line if dep_line else "(none detected)"):
        a(_row(f"  {ln}"))
    a(_row())
    a(_divider())
    a(_row())
    a(_row(f"  Signed by: La Tercera Muerte"))
    a(_row(f"  Date:      {today}"))
    a(_row())
    a(_divider())

    return "\n".join(lines)


def print_certificate(grave: dict) -> None:
    """Print the death certificate safely on any terminal."""
    from rich.console import Console
    c = Console(markup=False, emoji=False, highlight=False)
    c.print(generate_certificate(grave))


def save_certificate(grave: dict, output_dir: str | None = None) -> Path:
    cert = generate_certificate(grave)
    if output_dir is None:
        out = Path(grave["path"]) / ".tercera" / "certificate.txt"
    else:
        out = Path(output_dir) / "certificate.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(cert, encoding="utf-8")
    return out
