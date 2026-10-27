"""
Certificate of Death — Acta de Defunción.

The second ritual: a formal record of the project's life and passing.
"""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


_CERTIFICATE_TEMPLATE = """\
╔══════════════════════════════════════════════════════════════════════╗
║          💀  ACTA DE DEFUNCIÓN  /  CERTIFICATE OF DEATH  💀          ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Nombre / Name:  {{ name | center(52) }}  ║
║  Idioma / Language: {{ language | ljust(46) }}  ║
║                                                                      ║
╠══ VIDA / LIFE ═══════════════════════════════════════════════════════╣
║                                                                      ║
║  Nacimiento / Born:  {{ born_date | ljust(46) }}  ║
║  Primera Palabra / First Words:                                      ║
{% for line in first_words_wrapped %}║    {{ line | ljust(64) }}  ║
{% endfor %}║                                                                      ║
║  Commits totales / Total Commits:  {{ total_commits | string | ljust(32) }}  ║
║  Edad / Age:  {{ age }}
║                                                                      ║
╠══ MUERTE / DEATH ════════════════════════════════════════════════════╣
║                                                                      ║
║  Fallecimiento / Died:  {{ died_date | ljust(43) }}  ║
║  Silencio / Silence:  {{ silence }}
║  Últimas Palabras / Last Words:                                      ║
{% for line in last_words_wrapped %}║    {{ line | ljust(64) }}  ║
{% endfor %}║                                                                      ║
║  Causa de Muerte / Cause of Death:                                   ║
{% for line in cause_wrapped %}║    {{ line | ljust(64) }}  ║
{% endfor %}║                                                                      ║
╠══ FAMILIA / FAMILY ══════════════════════════════════════════════════╣
║                                                                      ║
║  Los que lo hicieron / Those who made it:                            ║
{% for name, count in family[:8] %}║    • {{ (name ~ " (" ~ count ~ " commits)") | ljust(62) }}  ║
{% endfor %}║                                                                      ║
╠══ ASUNTOS PENDIENTES / UNFINISHED BUSINESS ══════════════════════════╣
║                                                                      ║
{% if unfinished_todos %}{% for t in unfinished_todos[:5] %}║  {{ t.kind }}: {{ (t.file ~ ":" ~ t.line|string) | ljust(20) }}                                            ║
║    {{ t.text[:62] | ljust(62) }}  ║
{% endfor %}{% else %}║  None found. Perhaps it found peace after all.                       ║
{% endif %}║                                                                      ║
╠══ DEPENDENCIAS AMADAS / BELOVED DEPENDENCIES ════════════════════════╣
║                                                                      ║
║  {{ (deps[:8] | join(", "))[:66] | ljust(66) }}  ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝

  Firmado / Signed by: La Tercera Muerte  🕯️
  Fecha de este documento: {{ today }}
"""


def _wrap(text: str, width: int = 62) -> list[str]:
    lines = textwrap.wrap(text, width=width)
    return lines if lines else [""]


def _format_duration(days: int) -> str:
    if days < 0:
        return "unknown"
    years = days // 365
    months = (days % 365) // 30
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    return ", ".join(parts) if parts else f"{days} days"


def generate_certificate(grave: dict) -> str:
    """Render the death certificate as a string."""
    from jinja2 import Template

    born = datetime.fromisoformat(grave["born"]).strftime("%B %d, %Y")
    died = datetime.fromisoformat(grave["died"]).strftime("%B %d, %Y")
    today = datetime.now().strftime("%B %d, %Y")

    age_str = f"{_format_duration(grave.get('age_days', 0)):>43}  ║"
    silence_str = f"{_format_duration(grave.get('silence_days', 0))} of silence{'':>20}  ║"

    ctx = {
        "name": grave["name"],
        "language": grave.get("language", "Unknown"),
        "born_date": born,
        "died_date": died,
        "today": today,
        "total_commits": grave.get("total_commits", 0),
        "age": age_str,
        "silence": silence_str,
        "first_words_wrapped": _wrap(grave["first_commit"]["message"]),
        "last_words_wrapped": _wrap(grave["last_commit"]["message"]),
        "cause_wrapped": _wrap(grave.get("cause_of_death", "Unknown")),
        "family": grave.get("family", []),
        "unfinished_todos": grave.get("unfinished_todos", []),
        "deps": grave.get("dependencies", []),
    }

    tpl = Template(_CERTIFICATE_TEMPLATE, undefined=__import__("jinja2").Undefined)
    return tpl.render(**ctx)


def print_certificate(grave: dict) -> None:
    """Print the death certificate to stdout with color."""
    try:
        from rich.console import Console
        from rich.text import Text

        console = Console()
        cert = generate_certificate(grave)
        console.print(cert, style="dim white on black")
    except ImportError:
        print(generate_certificate(grave))


def save_certificate(grave: dict, output_dir: str | None = None) -> Path:
    """Save the certificate as a text file."""
    cert = generate_certificate(grave)
    if output_dir is None:
        out = Path(grave["path"]) / ".tercera" / "certificate.txt"
    else:
        out = Path(output_dir) / "certificate.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(cert, encoding="utf-8")
    return out
