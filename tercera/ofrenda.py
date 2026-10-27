"""
The Ofrenda: generates OFRENDA.md and ofrenda.html.

Phase 3 fixes:
- Jinja2 autoescape=True for HTML template (XSS-safe)
- No Google Fonts @import (works fully offline)
- _extract_function_names: filter first, then slice
- Papel picado flags show function names as visible text
"""

from __future__ import annotations

import pathlib
import re
from datetime import datetime
from typing import Optional

from jinja2 import Environment, BaseLoader, select_autoescape


# ---------------------------------------------------------------------------
# OFRENDA.md template (plain text — no autoescape needed)
# ---------------------------------------------------------------------------

_OFRENDA_MD = """\
# OFRENDA -- {{ grave.name }}

> *En Mexico, decimos que uno muere tres veces.*
> *La primera, cuando el cuerpo se detiene.*
> *La segunda, cuando lo entierran.*
> *La tercera, y la ultima, cuando nadie pronuncia su nombre.*
>
> *Hoy pronunciamos tu nombre.*

---

## Epitaph

**{{ grave.name }}** -- *{{ grave.language }} project*

Born: `{{ born }}` -- Died: `{{ died }}`

*{{ epitaph }}*

---

## Those Who Made It

*These names shall not be forgotten:*

{% for name, count in grave.family %}
- **{{ name }}** -- {{ count }} commit{{ "s" if count != 1 else "" }}
{% endfor %}

---

## Favorite Foods (Beloved Dependencies)

{% for dep in grave.dependencies[:20] %}
- `{{ dep }}`
{% endfor %}

---

## Last Words

> *{{ grave.last_commit.message }}*
>
> -- {{ grave.last_commit.author }}, {{ grave.last_commit.date[:10] }}

---

## Unfinished Business

{% if grave.unfinished_todos %}
{% for todo in grave.unfinished_todos[:10] %}
- **{{ todo.kind }}** in `{{ todo.file }}` (line {{ todo.line }}): *{{ todo.text }}*
{% endfor %}
{% else %}
*No unfinished tasks were found. Perhaps it found peace.*
{% endif %}

---

## Resurrection

{% if resurrection %}
**Status:** {{ resurrection.message }}
{% else %}
*No resurrection was attempted.*
{% endif %}

---

## Death Certificate

```
Born:  {{ born }}
Died:  {{ died }}
Age:   {{ grave.age_days }} days
Cause: {{ grave.cause_of_death }}
```

---

*This ofrenda was placed by La Tercera Muerte on {{ today }}.*
*Open-source. Offline. Yours.*
"""


# ---------------------------------------------------------------------------
# ofrenda.html template  (autoescaped -- all {{ }} values are safe)
# ---------------------------------------------------------------------------

_OFRENDA_HTML = """\
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Ofrenda -- {{ grave.name }}</title>
  <style>
    /* No external fonts -- fully offline */
    :root {
      --gold: #f5c842;
      --amber: #e8841a;
      --deep: #1a0a00;
      --marigold: #ff8c00;
      --candle-yellow: #ffe066;
      --smoke: #8a7a6a;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #0d0600;
      color: #e8d5a0;
      font-family: Georgia, 'Times New Roman', serif;
      min-height: 100vh;
      overflow-x: hidden;
    }

    /* Marigold petals */
    .petal {
      position: fixed; font-size: 1.2rem;
      animation: fall linear infinite;
      pointer-events: none; z-index: 0; opacity: 0.7;
    }
    @keyframes fall {
      0%   { transform: translateY(-20px) rotate(0deg);   opacity: 0.8; }
      100% { transform: translateY(110vh) rotate(360deg); opacity: 0;   }
    }

    /* Altar */
    .altar { position: relative; z-index: 1; max-width: 860px; margin: 0 auto; padding: 20px; }

    /* Header */
    .altar-header { text-align: center; padding: 40px 20px 20px; border-bottom: 2px solid var(--gold); }
    .altar-header h1 { font-size: clamp(1.8rem, 5vw, 3rem); color: var(--gold); letter-spacing: 0.1em; text-shadow: 0 0 20px var(--amber); }
    .altar-header .subtitle { font-style: italic; color: var(--smoke); margin-top: 8px; font-size: 1.1rem; }
    .epitaph { margin: 30px auto; max-width: 600px; text-align: center; font-style: italic; font-size: 1.2rem; color: #c9a86c; line-height: 1.7; }

    /* Tiers */
    .tier { margin: 30px 0; padding: 20px; border: 1px solid #3a2a10; border-radius: 4px; background: linear-gradient(180deg, #1c0e02 0%, #0d0600 100%); }
    .tier h2 { font-size: 1.2rem; color: var(--gold); margin-bottom: 16px; text-align: center; text-shadow: 0 0 8px var(--amber); }

    /* Candles */
    .candles-grid { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; }
    .candle-wrap { display: flex; flex-direction: column; align-items: center; gap: 6px; width: 90px; }
    .candle { position: relative; width: 18px; height: 60px; background: linear-gradient(180deg, #f5f0e8 0%, #ddd5c0 100%); border-radius: 2px; margin: 0 auto; }
    .candle::after { content: ''; position: absolute; top: -2px; left: 50%; transform: translateX(-50%); width: 2px; height: 8px; background: #555; }
    .flame { position: absolute; top: -28px; left: 50%; transform: translateX(-50%); width: 14px; height: 22px; background: radial-gradient(ellipse at 50% 80%, var(--candle-yellow), var(--amber), transparent); border-radius: 50% 50% 30% 30%; animation: flicker 0.15s ease-in-out infinite alternate; filter: blur(0.5px); }
    @keyframes flicker {
      0%   { transform: translateX(-50%) scaleX(1)    scaleY(1)    rotate(-1deg); opacity: 0.95; }
      33%  { transform: translateX(-50%) scaleX(0.9)  scaleY(1.05) rotate(1deg);  opacity: 1;    }
      66%  { transform: translateX(-50%) scaleX(1.1)  scaleY(0.95) rotate(-2deg); opacity: 0.9;  }
      100% { transform: translateX(-50%) scaleX(0.95) scaleY(1.02) rotate(0deg);  opacity: 0.98; }
    }
    .candle-name { font-size: 0.68rem; text-align: center; color: #c9a86c; word-break: break-word; line-height: 1.3; }
    .candle-commits { font-size: 0.6rem; color: var(--smoke); }

    /* Offerings */
    .offerings { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
    .offering { background: #2a1500; border: 1px solid var(--marigold); border-radius: 3px; padding: 4px 10px; font-size: 0.85rem; color: var(--marigold); font-family: monospace; }

    /* TODOs */
    .todos { list-style: none; }
    .todos li { padding: 8px 0; border-bottom: 1px solid #2a1500; font-size: 0.9rem; color: #b09060; }
    .todos li:last-child { border-bottom: none; }
    .todo-kind { display: inline-block; padding: 1px 6px; border-radius: 2px; font-size: 0.75rem; font-family: monospace; margin-right: 6px; }
    .kind-TODO  { background: #1a3a00; color: #6fcc6f; }
    .kind-FIXME { background: #3a0000; color: #cc6f6f; }
    .kind-HACK  { background: #3a3000; color: #ccbf6f; }
    .kind-XXX   { background: #30003a; color: #bf6fcc; }

    /* Last words */
    .last-words { text-align: center; font-style: italic; font-size: 1.15rem; color: #c9a86c; padding: 20px; border-left: 3px solid var(--gold); margin: 10px 0; }
    .last-words-attr { margin-top: 8px; font-size: 0.85rem; color: var(--smoke); font-style: normal; }

    /* Resurrection */
    .resurrection-badge { text-align: center; padding: 16px; font-size: 1.2rem; }
    .badge-success { color: #6fcc6f; }
    .badge-fail    { color: #cc6f6f; }

    /* Certificate */
    .cert-box { font-family: monospace; font-size: 0.85rem; background: #0a0400; border: 1px solid #3a2a10; padding: 16px; color: #8a7a6a; white-space: pre; line-height: 1.6; overflow-x: auto; }

    /* Papel picado */
    .papel-picado { display: flex; justify-content: center; gap: 4px; flex-wrap: wrap; padding: 10px 0; }
    .papel-flag {
      width: 44px; height: 32px;
      clip-path: polygon(0 0, 100% 0, 100% 70%, 50% 100%, 0 70%);
      display: flex; align-items: flex-start; justify-content: center;
      padding-top: 2px;
      font-size: 0.42rem; font-family: monospace;
      overflow: hidden; color: rgba(0,0,0,0.75);
      font-weight: bold; letter-spacing: -0.5px;
    }

    /* Footer */
    .footer { text-align: center; padding: 40px 20px; color: var(--smoke); font-size: 0.85rem; border-top: 1px solid #2a1500; margin-top: 40px; }
  </style>
</head>
<body>

{% set flag_colors = ["#e63946","#f4a261","#e9c46a","#2a9d8f","#8338ec","#3a86ff"] %}

<!-- Marigold petals -->
{% for i in range(18) %}
<div class="petal" style="
  left: {{ (i * 5.5 + 2) | int % 100 }}%;
  animation-duration: {{ (6 + (i * 7 % 5)) }}s;
  animation-delay: {{ (i * 4 % 6) }}s;
  font-size: {{ (8 + i % 3 * 3) / 10 }}rem;
">&#127804;</div>
{% endfor %}

<div class="altar">

  <!-- Header -->
  <div class="altar-header">
    <!-- Papel picado: function names as visible text -->
    <div class="papel-picado">
      {% for fn in function_names %}
      <div class="papel-flag"
           style="background: {{ flag_colors[loop.index0 % 6] }};"
           title="{{ fn }}">{{ fn[:6] }}</div>
      {% endfor %}
    </div>
    <h1>{{ grave.name }}</h1>
    <div class="subtitle">{{ grave.language }} &nbsp;&middot;&nbsp; {{ born }} &ndash; {{ died }}</div>
    <div class="epitaph">{{ epitaph }}</div>
  </div>

  <!-- Tier 1: Contributors as candles -->
  <div class="tier">
    <h2>Those Who Made It &mdash; Sus Creadores</h2>
    <div class="candles-grid">
      {% for name, count in grave.family %}
      <div class="candle-wrap">
        <div class="candle"><div class="flame"></div></div>
        <div class="candle-name">{{ name }}</div>
        <div class="candle-commits">{{ count }} commit{{ "s" if count != 1 else "" }}</div>
      </div>
      {% endfor %}
    </div>
  </div>

  <!-- Tier 2: Last words -->
  <div class="tier">
    <h2>Last Words &mdash; &Uacute;ltimas Palabras</h2>
    <div class="last-words">
      &ldquo;{{ grave.last_commit.message }}&rdquo;
      <div class="last-words-attr">&mdash; {{ grave.last_commit.author }}, {{ grave.last_commit.date[:10] }}</div>
    </div>
  </div>

  <!-- Tier 3: Dependencies -->
  {% if grave.dependencies %}
  <div class="tier">
    <h2>Beloved Dependencies &mdash; Sus Alimentos Favoritos</h2>
    <div class="offerings">
      {% for dep in grave.dependencies[:24] %}
      <span class="offering">{{ dep }}</span>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  <!-- Tier 4: Unfinished business -->
  {% if grave.unfinished_todos %}
  <div class="tier">
    <h2>Unfinished Business &mdash; Asuntos Pendientes</h2>
    <ul class="todos">
      {% for todo in grave.unfinished_todos[:10] %}
      <li>
        <span class="todo-kind kind-{{ todo.kind }}">{{ todo.kind }}</span>
        <code>{{ todo.file }}:{{ todo.line }}</code> &mdash; {{ todo.text }}
      </li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}

  <!-- Tier 5: Resurrection -->
  <div class="tier">
    <h2>Resurrection &mdash; La Resurrecci&oacute;n</h2>
    <div class="resurrection-badge {{ 'badge-success' if resurrection and resurrection.success else 'badge-fail' }}">
      {% if resurrection %}
        {{ resurrection.message }}
      {% else %}
        Resurrection not yet attempted.
      {% endif %}
    </div>
  </div>

  <!-- Tier 6: Death certificate -->
  <div class="tier">
    <h2>Acta de Defunci&oacute;n</h2>
    <div class="cert-box">Name:    {{ grave.name }}
Language: {{ grave.language }}
Born:    {{ born }}
Died:    {{ died }}
Age:     {{ grave.age_days }} days ({{ grave.age_days // 365 }} years)
Silence: {{ grave.silence_days }} days ({{ grave.silence_days // 365 }} years)
Commits: {{ grave.total_commits }}
Cause:   {{ grave.cause_of_death }}

First: {{ grave.first_commit.sha }} &mdash; &ldquo;{{ grave.first_commit.message[:60] }}&rdquo;
Last:  {{ grave.last_commit.sha }} &mdash; &ldquo;{{ grave.last_commit.message[:60] }}&rdquo;</div>
  </div>

  <div class="footer">
    <p>This ofrenda was placed by <strong>La Tercera Muerte</strong> on {{ today }}</p>
    <p style="margin-top: 8px; font-style: italic;">
      &ldquo;La tercera muerte es cuando nadie pronuncia tu nombre.<br>
      Hoy pronunciamos tu nombre.&rdquo;
    </p>
    <p style="margin-top: 12px;">Open-source &middot; Offline &middot; Yours</p>
  </div>

</div>
</body>
</html>
"""


def _extract_function_names(grave: dict) -> list[str]:
    """Filter source files first, then extract and slice function names."""
    repo_path = pathlib.Path(grave["path"])

    from .exhume import IGNORE_DIRS, _is_ignored

    exts_patterns = {
        ".py": re.compile(r"def (\w+)\("),
        ".js": re.compile(r"function (\w+)\("),
        ".ts": re.compile(r"function (\w+)\("),
        ".rb": re.compile(r"def (\w+)"),
        ".go": re.compile(r"func (\w+)\("),
    }

    # Filter eligible files first, then slice to limit work
    eligible = [
        f for f in repo_path.rglob("*")
        if not _is_ignored(f)
        and f.is_file()
        and f.suffix.lower() in exts_patterns
        and f.stat().st_size < 200_000
    ][:60]  # slice the file list, not the names

    names: list[str] = []
    for f in eligible:
        pat = exts_patterns[f.suffix.lower()]
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
            names.extend(pat.findall(text))
        except Exception:
            continue
        if len(names) > 40:
            break

    # Filter private/dunder names, deduplicate
    names = [n for n in dict.fromkeys(names) if not n.startswith("_")][:30]
    return names


def _generate_epitaph(grave: dict, llm_epitaph: str | None = None) -> str:
    if llm_epitaph:
        return llm_epitaph
    silence_years = grave.get("silence_days", 0) // 365
    age_years = grave.get("age_days", 0) // 365
    return (
        f"It ran for {age_years} year{'s' if age_years != 1 else ''}, "
        f"then fell silent {silence_years} year{'s' if silence_years != 1 else ''} ago. "
        f"It is remembered here."
    )


def build_ofrenda(
    grave: dict,
    resurrection: dict | None = None,
    epitaph: str | None = None,
) -> tuple[str, str]:
    """Build OFRENDA.md and ofrenda.html. Returns (markdown, html)."""
    born = datetime.fromisoformat(grave["born"]).strftime("%B %d, %Y")
    died = datetime.fromisoformat(grave["died"]).strftime("%B %d, %Y")
    today = datetime.now().strftime("%B %d, %Y")
    epi = _generate_epitaph(grave, epitaph)
    function_names = _extract_function_names(grave)

    ctx = {
        "grave": grave,
        "born": born,
        "died": died,
        "today": today,
        "epitaph": epi,
        "resurrection": resurrection,
        "function_names": function_names,
    }

    # Markdown: no autoescape
    md_env = Environment(loader=BaseLoader(), autoescape=False)
    md = md_env.from_string(_OFRENDA_MD).render(**ctx)

    # HTML: autoescape=True so all {{ }} values are safe
    html_env = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(enabled_extensions=("html",), default=True),
    )
    # The template has a .html suffix in spirit; force autoescape on
    html_env.autoescape = True
    html = html_env.from_string(_OFRENDA_HTML).render(**ctx)

    return md, html


def save_ofrenda(
    grave: dict,
    resurrection: dict | None = None,
    epitaph: str | None = None,
    commit: bool = False,
) -> tuple[pathlib.Path, pathlib.Path]:
    md, html = build_ofrenda(grave, resurrection, epitaph)

    repo_path = pathlib.Path(grave["path"])
    md_path = repo_path / "OFRENDA.md"
    html_path = repo_path / "ofrenda.html"

    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")

    if commit:
        import subprocess
        subprocess.run(
            ["git", "add", "OFRENDA.md", "ofrenda.html"],
            cwd=str(repo_path), capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m",
             "In memory of those who built this -- La Tercera Muerte"],
            cwd=str(repo_path), capture_output=True,
        )

    return md_path, html_path
