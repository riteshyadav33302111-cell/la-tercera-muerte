"""
The Ofrenda: generates OFRENDA.md and ofrenda.html.

This is the final ritual — an altar that honors the project and its contributors
so they are never forgotten.
"""

from __future__ import annotations

import pathlib
from datetime import datetime
from typing import Optional

from jinja2 import Environment, BaseLoader


# ---------------------------------------------------------------------------
# OFRENDA.md template
# ---------------------------------------------------------------------------

OFRENDA_MD = """\
# 🕯️ OFRENDA — {{ grave.name }}

> *En México, decimos que uno muere tres veces.*
> *La primera, cuando el cuerpo se detiene.*
> *La segunda, cuando lo entierran.*
> *La tercera, y la última, cuando nadie pronuncia su nombre.*
>
> *Hoy pronunciamos tu nombre.*

---

## 📜 Epitaph

**{{ grave.name }}** — *{{ grave.language }} project*

Born: `{{ born }}` — Died: `{{ died }}`

*{{ epitaph }}*

---

## 👥 Those Who Made It

*These names shall not be forgotten:*

{% for name, count in grave.family %}
- **{{ name }}** — {{ count }} commit{{ "s" if count != 1 else "" }}
{% endfor %}

---

## 🍊 Favorite Foods (Beloved Dependencies)

*What it loved and needed to live:*

{% for dep in grave.dependencies[:20] %}
- `{{ dep }}`
{% endfor %}

---

## 📝 Last Words

> *{{ grave.last_commit.message }}*
>
> — {{ grave.last_commit.author }}, {{ grave.last_commit.date[:10] }}

---

## 🕯️ Unfinished Business

{% if grave.unfinished_todos %}
The following tasks were never completed. We remember them here:

{% for todo in grave.unfinished_todos[:10] %}
- **{{ todo.kind }}** in `{{ todo.file }}` (line {{ todo.line }}): *{{ todo.text }}*
{% endfor %}
{% else %}
*No unfinished tasks were found. Perhaps it found peace.*
{% endif %}

---

## 🌼 Resurrection

{% if resurrection %}
**Status:** {{ resurrection.message }}

*{{ "The tests run green again." if resurrection.success else "The work continues." }}*
{% else %}
*No resurrection was attempted.*
{% endif %}

---

## 🎭 Death Certificate

```
Born:  {{ born }}
Died:  {{ died }}
Age:   {{ age_days }} days
Cause: {{ grave.cause_of_death }}
```

---

*This ofrenda was placed by La Tercera Muerte on {{ today }}.*
*Open-source. Offline. Yours.*

🌼🕯️🌼🕯️🌼🕯️🌼🕯️🌼🕯️🌼
"""


# ---------------------------------------------------------------------------
# ofrenda.html template
# ---------------------------------------------------------------------------

OFRENDA_HTML = """\
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Ofrenda — {{ grave.name }}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=IM+Fell+English:ital@0;1&display=swap');

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
      font-family: 'IM Fell English', Georgia, serif;
      min-height: 100vh;
      overflow-x: hidden;
    }

    /* ── Marigold petals ── */
    .petal {
      position: fixed;
      font-size: 1.2rem;
      animation: fall linear infinite;
      pointer-events: none;
      z-index: 0;
      opacity: 0.7;
    }
    @keyframes fall {
      0%   { transform: translateY(-20px) rotate(0deg);   opacity: 0.8; }
      100% { transform: translateY(110vh) rotate(360deg); opacity: 0;   }
    }

    /* ── Altar frame ── */
    .altar {
      position: relative;
      z-index: 1;
      max-width: 860px;
      margin: 0 auto;
      padding: 20px;
    }

    /* ── Header ── */
    .altar-header {
      text-align: center;
      padding: 40px 20px 20px;
      border-bottom: 2px solid var(--gold);
    }

    .altar-header h1 {
      font-family: 'Cinzel', serif;
      font-size: clamp(1.8rem, 5vw, 3rem);
      color: var(--gold);
      letter-spacing: 0.1em;
      text-shadow: 0 0 20px var(--amber);
    }

    .altar-header .subtitle {
      font-style: italic;
      color: var(--smoke);
      margin-top: 8px;
      font-size: 1.1rem;
    }

    .epitaph {
      margin: 30px auto;
      max-width: 600px;
      text-align: center;
      font-style: italic;
      font-size: 1.2rem;
      color: #c9a86c;
      line-height: 1.7;
    }

    /* ── Tiers ── */
    .tier {
      margin: 30px 0;
      padding: 20px;
      border: 1px solid #3a2a10;
      border-radius: 4px;
      background: linear-gradient(180deg, #1c0e02 0%, #0d0600 100%);
    }

    .tier h2 {
      font-family: 'Cinzel', serif;
      color: var(--gold);
      font-size: 1.2rem;
      margin-bottom: 16px;
      text-align: center;
      text-shadow: 0 0 8px var(--amber);
    }

    /* ── Candles grid ── */
    .candles-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 20px;
      justify-content: center;
    }

    .candle-wrap {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      width: 90px;
    }

    .candle {
      position: relative;
      width: 18px;
      height: 60px;
      background: linear-gradient(180deg, #f5f0e8 0%, #ddd5c0 100%);
      border-radius: 2px;
      margin: 0 auto;
    }
    .candle::after {
      content: '';
      position: absolute;
      top: -2px;
      left: 50%;
      transform: translateX(-50%);
      width: 2px;
      height: 8px;
      background: #555;
    }

    .flame {
      position: absolute;
      top: -28px;
      left: 50%;
      transform: translateX(-50%);
      width: 14px;
      height: 22px;
      background: radial-gradient(ellipse at 50% 80%, var(--candle-yellow), var(--amber), transparent);
      border-radius: 50% 50% 30% 30%;
      animation: flicker 0.15s ease-in-out infinite alternate;
      filter: blur(0.5px);
    }
    @keyframes flicker {
      0%  { transform: translateX(-50%) scaleX(1)   scaleY(1)    rotate(-1deg); opacity: 0.95; }
      33% { transform: translateX(-50%) scaleX(0.9) scaleY(1.05) rotate(1deg);  opacity: 1;    }
      66% { transform: translateX(-50%) scaleX(1.1) scaleY(0.95) rotate(-2deg); opacity: 0.9;  }
      100%{ transform: translateX(-50%) scaleX(0.95)scaleY(1.02) rotate(0deg);  opacity: 0.98; }
    }

    .candle-name {
      font-size: 0.68rem;
      text-align: center;
      color: #c9a86c;
      word-break: break-word;
      line-height: 1.3;
    }
    .candle-commits {
      font-size: 0.6rem;
      color: var(--smoke);
    }

    /* ── Dependencies (offerings) ── */
    .offerings {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: center;
    }
    .offering {
      background: #2a1500;
      border: 1px solid var(--marigold);
      border-radius: 3px;
      padding: 4px 10px;
      font-size: 0.85rem;
      color: var(--marigold);
      font-family: monospace;
    }

    /* ── TODOs ── */
    .todos { list-style: none; }
    .todos li {
      padding: 8px 0;
      border-bottom: 1px solid #2a1500;
      font-size: 0.9rem;
      color: #b09060;
    }
    .todos li:last-child { border-bottom: none; }
    .todo-kind {
      display: inline-block;
      padding: 1px 6px;
      border-radius: 2px;
      font-size: 0.75rem;
      font-family: monospace;
      margin-right: 6px;
    }
    .kind-todo  { background: #1a3a00; color: #6fcc6f; }
    .kind-fixme { background: #3a0000; color: #cc6f6f; }
    .kind-hack  { background: #3a3000; color: #ccbf6f; }

    /* ── Last words ── */
    .last-words {
      text-align: center;
      font-style: italic;
      font-size: 1.15rem;
      color: #c9a86c;
      padding: 20px;
      border-left: 3px solid var(--gold);
      margin: 10px 0;
    }
    .last-words-attr {
      margin-top: 8px;
      font-size: 0.85rem;
      color: var(--smoke);
      font-style: normal;
    }

    /* ── Resurrection badge ── */
    .resurrection-badge {
      text-align: center;
      padding: 16px;
      font-size: 1.2rem;
    }
    .badge-success { color: #6fcc6f; }
    .badge-fail    { color: #cc6f6f; }

    /* ── Death certificate ── */
    .cert-box {
      font-family: monospace;
      font-size: 0.85rem;
      background: #0a0400;
      border: 1px solid #3a2a10;
      padding: 16px;
      color: #8a7a6a;
      white-space: pre;
      line-height: 1.6;
    }

    /* ── Footer ── */
    .footer {
      text-align: center;
      padding: 40px 20px;
      color: var(--smoke);
      font-size: 0.85rem;
      border-top: 1px solid #2a1500;
      margin-top: 40px;
    }

    /* ── Papel picado banner ── */
    .papel-picado {
      display: flex;
      justify-content: center;
      gap: 4px;
      flex-wrap: wrap;
      padding: 10px 0;
    }
    .papel-flag {
      width: 24px;
      height: 32px;
      clip-path: polygon(0 0, 100% 0, 100% 70%, 50% 100%, 0 70%);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.5rem;
      overflow: hidden;
    }
  </style>
</head>
<body>

<!-- Marigold petals -->
{% for i in range(18) %}
<div class="petal" style="
  left: {{ (i * 5.5 + 2) % 100 }}%;
  animation-duration: {{ 6 + (i * 0.7 % 5) }}s;
  animation-delay: {{ (i * 0.4) % 6 }}s;
  font-size: {{ 0.8 + (i % 3) * 0.3 }}rem;
">🌼</div>
{% endfor %}

<div class="altar">

  <!-- Header -->
  <div class="altar-header">
    <div class="papel-picado">
      {% set colors = ["#e63946","#f4a261","#e9c46a","#2a9d8f","#8338ec","#3a86ff"] %}
      {% for fn in function_names[:24] %}
      <div class="papel-flag" style="background: {{ colors[loop.index0 % 6] }};" title="{{ fn }}"></div>
      {% endfor %}
    </div>
    <h1>🕯️ {{ grave.name }} 🕯️</h1>
    <div class="subtitle">{{ grave.language }} &nbsp;·&nbsp; {{ born }} – {{ died }}</div>
    <div class="epitaph">{{ epitaph }}</div>
  </div>

  <!-- Tier 1: Contributors as candles -->
  <div class="tier">
    <h2>🕯️ Those Who Made It — Sus Creadores</h2>
    <div class="candles-grid">
      {% for name, count in grave.family %}
      <div class="candle-wrap">
        <div class="candle">
          <div class="flame"></div>
        </div>
        <div class="candle-name">{{ name }}</div>
        <div class="candle-commits">{{ count }} commit{{ "s" if count != 1 else "" }}</div>
      </div>
      {% endfor %}
    </div>
  </div>

  <!-- Tier 2: Last words -->
  <div class="tier">
    <h2>📜 Last Words — Últimas Palabras</h2>
    <div class="last-words">
      "{{ grave.last_commit.message }}"
      <div class="last-words-attr">— {{ grave.last_commit.author }}, {{ grave.last_commit.date[:10] }}</div>
    </div>
  </div>

  <!-- Tier 3: Dependencies as offerings -->
  {% if grave.dependencies %}
  <div class="tier">
    <h2>🍊 Beloved Dependencies — Sus Alimentos Favoritos</h2>
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
    <h2>🔮 Unfinished Business — Asuntos Pendientes</h2>
    <ul class="todos">
      {% for todo in grave.unfinished_todos[:10] %}
      <li>
        <span class="todo-kind kind-{{ todo.kind.lower() }}">{{ todo.kind }}</span>
        <code>{{ todo.file }}:{{ todo.line }}</code> — {{ todo.text }}
      </li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}

  <!-- Tier 5: Resurrection -->
  <div class="tier">
    <h2>✨ Resurrection — La Resurrección</h2>
    <div class="resurrection-badge {{ 'badge-success' if resurrection and resurrection.success else 'badge-fail' }}">
      {% if resurrection %}
        {{ resurrection.message }}
      {% else %}
        🕯️ Resurrection not yet attempted.
      {% endif %}
    </div>
  </div>

  <!-- Tier 6: Death certificate -->
  <div class="tier">
    <h2>📋 Acta de Defunción</h2>
    <div class="cert-box">Name:    {{ grave.name }}
Language: {{ grave.language }}
Born:    {{ born }}
Died:    {{ died }}
Age:     {{ grave.age_days }} days ({{ grave.age_days // 365 }} years)
Silence: {{ grave.silence_days }} days ({{ grave.silence_days // 365 }} years)
Commits: {{ grave.total_commits }}
Cause:   {{ grave.cause_of_death }}

First commit: {{ grave.first_commit.sha }} — "{{ grave.first_commit.message[:60] }}"
Last commit:  {{ grave.last_commit.sha }} — "{{ grave.last_commit.message[:60] }}"</div>
  </div>

  <div class="footer">
    <p>🌼 This ofrenda was placed by <strong>La Tercera Muerte</strong> on {{ today }} 🌼</p>
    <p style="margin-top: 8px; font-style: italic;">
      "La tercera muerte es cuando nadie pronuncia tu nombre.<br>
      Hoy pronunciamos tu nombre."
    </p>
    <p style="margin-top: 12px;">Open-source · Offline · Yours</p>
  </div>

</div>
</body>
</html>
"""


def _extract_function_names(grave: dict) -> list[str]:
    """Extract function names for papel picado banners."""
    import re
    repo_path = pathlib.Path(grave["path"])
    names = []
    exts_patterns = {
        ".py": r"def (\w+)\(",
        ".js": r"function (\w+)\(",
        ".ts": r"function (\w+)\(",
        ".rb": r"def (\w+)",
        ".go": r"func (\w+)\(",
    }
    for f in list(repo_path.rglob("*"))[:50]:
        if f.is_file() and f.suffix in exts_patterns:
            try:
                text = f.read_text(errors="ignore")
                found = re.findall(exts_patterns[f.suffix], text)
                names.extend(found)
            except Exception:
                continue
        if len(names) > 30:
            break
    return list(dict.fromkeys(names))[:30]


def _generate_epitaph(grave: dict, llm_epitaph: str | None = None) -> str:
    """Generate or return an epitaph."""
    if llm_epitaph:
        return llm_epitaph

    silence_years = grave.get("silence_days", 0) // 365
    return (
        f"It ran for {grave.get('age_days', 0) // 365} years, "
        f"then fell silent {silence_years} year{'s' if silence_years != 1 else ''} ago. "
        f"It is remembered here."
    )


def build_ofrenda(
    grave: dict,
    resurrection: dict | None = None,
    epitaph: str | None = None,
) -> tuple[str, str]:
    """
    Build OFRENDA.md and ofrenda.html content strings.
    Returns (markdown_content, html_content).
    """
    from jinja2 import Environment, BaseLoader

    env = Environment(loader=BaseLoader())

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
        "age_days": grave.get("age_days", 0),
    }

    md = env.from_string(OFRENDA_MD).render(**ctx)
    html = env.from_string(OFRENDA_HTML).render(**ctx)
    return md, html


def save_ofrenda(
    grave: dict,
    resurrection: dict | None = None,
    epitaph: str | None = None,
    commit: bool = False,
) -> tuple[pathlib.Path, pathlib.Path]:
    """
    Save OFRENDA.md and ofrenda.html into the repository root.
    Optionally commits them.
    """
    md, html = build_ofrenda(grave, resurrection, epitaph)

    repo_path = pathlib.Path(grave["path"])
    md_path = repo_path / "OFRENDA.md"
    html_path = repo_path / "ofrenda.html"

    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")

    if commit:
        import subprocess
        subprocess.run(["git", "add", "OFRENDA.md", "ofrenda.html"],
                       cwd=str(repo_path), capture_output=True)
        subprocess.run(
            ["git", "commit", "-m",
             "🕯️ In memory of those who built this — La Tercera Muerte"],
            cwd=str(repo_path), capture_output=True,
        )

    return md_path, html_path
