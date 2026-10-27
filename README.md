# 💀 La Tercera Muerte

> *En México, decimos que uno muere tres veces.*
> *La primera, cuando el cuerpo se detiene.*
> *La segunda, cuando lo entierran.*
> *La tercera, y la última, cuando nadie pronuncia su nombre.*
>
> *Software dies the same way.*

**La Tercera Muerte** is a fully offline AI tool that *exhumes* an abandoned git repository and turns it into a ghost you can talk to. It speaks in the voice of its era, remembers its own code, names its unfinished business, and — if you ask — lets an open-source coding agent try to resolve it. At the end, it builds a **digital ofrenda**: an animated candlelit HTML altar that honors every contributor by name, so they are never forgotten.

Built for [Hacktoberfest Open-Source AI Challenge — Week 4: Ghost in the Machine](https://dev.to/challenges/hacktoberfest-week4-2026-10-26).

---

## 🎬 The Five Rituals

| # | Ritual | What happens |
|---|--------|-------------|
| 1 | **Exhumación** | `tercera exhume ./old-repo` — parses git history, authors, TODOs, dependencies, tests |
| 2 | **Acta de Defunción** | Prints a death certificate: born, died, cause of death, last words, family |
| 3 | **La Sesión** | A haunted terminal séance — chat with the project's ghost using local RAG |
| 4 | **Asuntos Pendientes** | The ghost names what keeps it here; the resurrection agent tries to fix it |
| 5 | **La Ofrenda** | `OFRENDA.md` + animated `ofrenda.html` altar committed back into the repo |

---

## ✨ Features

- **🕯️ Haunted terminal TUI** — Flickering candles, typewriter ghost text, idle whispers after 45 seconds of silence
- **🧠 RAG-powered memory** — The ghost actually knows its own code via local embeddings (LanceDB + nomic-embed-text)
- **💬 Era-accurate voice** — Each ghost speaks in the slang and tech culture of its era (2009 jQuery plugin ≠ 2020 Rust crate)
- **🔧 Resurrection agent** — Sandboxed Docker + Qwen2.5-Coder tries to fix failing tests or last TODOs
- **🌼 Animated ofrenda** — CSS candles flicker for each contributor, marigold petals drift, papel picado from function names
- **🔇 100% offline** — Runs on a laptop with Wi-Fi off. Your private codebase never leaves your machine
- **🔄 Swappable models** — Change `persona_model` or `coder_model` in `config.toml` to use any Ollama model
- **🎤 Optional voice** — whisper.cpp for input + Piper TTS with reverb for the ghost's voice

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
# Core
pip install la-tercera-muerte

# With RAG memory (recommended)
pip install "la-tercera-muerte[memory]"

# From source
git clone https://github.com/riteshyadav33302111-cell/la-tercera-muerte
cd la-tercera-muerte
pip install -e ".[memory]"
```

### 2. Pull Ollama models

```bash
# Make sure Ollama is running
ollama serve

# Pull the models (do this while you still have internet)
ollama pull llama3.1:8b          # Ghost persona
ollama pull qwen2.5-coder:7b     # Code repair
ollama pull nomic-embed-text     # Memory embeddings
```

### 3. Perform the rituals

```bash
# Full ritual (interactive, all 5 steps)
tercera full-ritual ./your-old-repo

# Or step by step:
tercera exhume ./your-old-repo         # Step 1: exhume
tercera seance ./your-old-repo         # Step 3: séance
tercera resurrect ./your-old-repo      # Step 4: resurrection
tercera ofrenda ./your-old-repo        # Step 5: ofrenda

# Check Ollama status and available models
tercera info
```

---

## 📸 Screenshots

```
╔══════════════════════════════════════════════════════════════════════╗
║          💀  ACTA DE DEFUNCIÓN  /  CERTIFICATE OF DEATH  💀          ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Nombre / Name:               old-jquery-carousel                    ║
║  Idioma / Language: JavaScript                                       ║
║                                                                      ║
╠══ VIDA / LIFE ═══════════════════════════════════════════════════════╣
║  Nacimiento / Born:  March 14, 2011                                  ║
║  Primera Palabra / First Words: "initial commit, jQuery plugin"      ║
║  Commits totales / Total Commits:  47                                ║
║  Edad / Age:  3 years, 2 months                                      ║
╠══ MUERTE / DEATH ════════════════════════════════════════════════════╣
║  Fallecimiento / Died:  May 09, 2014                                 ║
║  Causa de Muerte / Cause of Death:                                   ║
║    Animated by Grunt, now a relic of another era                     ║
╚══════════════════════════════════════════════════════════════════════╝
```

**The séance:**
```
🕯️ 💀 🕯️ 🌼 🕯️ 💀 🕯️
      old-jquery-carousel
  JavaScript · 2011-03-14 – 2014-05-09

  Ghost: I remember the days when $.fn was everything...
         You could ask me about the carousel logic,
         the browser compatibility hacks, the IE8 shims.
         I was fast. I was loved. Then Grunt stopped,
         and no one came back.

  You › Why did you die?

  Ghost: My keeper moved to React. I understand.
         The world changed faster than I could.
         But line 212... the autoplay race condition...
         it was never fixed. That's what keeps me here.
```

---

## 🛠️ Tech Stack — All Open, All Local

| Layer | Tool | Why |
|-------|------|-----|
| LLM runtime | [Ollama](https://ollama.ai) | Local inference, no API keys |
| Ghost persona | Llama 3.1 8B / Gemma 3 / Qwen | Any open-weight chat model |
| Code repair | Qwen2.5-Coder 7B | Best open coder at this size |
| Embeddings | `nomic-embed-text` via Ollama | High quality, offline |
| Vector store | [LanceDB](https://lancedb.com) | Embedded, no server needed |
| TUI | [Textual](https://textual.textualize.io) | Beautiful terminal apps in Python |
| Git parsing | [GitPython](https://gitpython.readthedocs.io) | Full git history access |
| Sandbox | Docker | Agent never touches your real files |
| Voice input | [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | Offline STT |
| Voice output | [Piper TTS](https://github.com/rhasspy/piper) + sox | Offline TTS with reverb |
| Ofrenda | Jinja2 + CSS animations | Animated candlelit altar |
| CLI | [Typer](https://typer.tiangolo.com) + [Rich](https://rich.readthedocs.io) | Beautiful CLI |

**Hardware target:** 16 GB RAM laptop, no internet. Demo with Wi-Fi off.

---

## 🌿 Why Open Innovation Matters Here

Every repository this tool resurrects died because something it depended on *disappeared*: a runtime reached end-of-life, a dependency was unpublished, a CI service shut down, a maintainer burned out. Building a resurrection tool on top of a closed API that could change pricing, deprecate a model, or shut down tomorrow would repeat **the exact mistake that killed these projects**.

With open weights:

- **It works with the lights off.** Run on a plane, in a bunker, with Wi-Fi disabled on camera. Your séance doesn't need permission from a server farm.
- **Private codebases stay private.** Proprietary code, internal tools, personal projects — your source never touches anyone else's server.
- **Models are pinned.** The ghost's personality never shifts under you because a provider updated their model. `config.toml` says what model to run, forever.
- **You can fine-tune the ghost.** Want a different voice? A more melancholic persona? Train or adapt the model yourself.
- **No rate limits, no cost per call.** The resurrection agent can spend an hour running hundreds of repair attempts without a bill.
- **The tool itself can't suffer the third death.** If I stop maintaining it, anyone can still run it in ten years. The weights exist. The code is MIT.

A tool that rescues the forgotten *must* be built on foundations that don't forget.

---

## 🎭 The Demo Video Script (90 seconds)

1. **Black screen:** *"In Mexico, they say we die three times…"*
2. Turn off Wi-Fi on camera
3. `tercera exhume ./forgotten-repo` — death certificate prints
4. Séance opens: candles flicker. *"Why did you die?"* Ghost answers in its era's voice
5. Walk away. 45 seconds later, an idle whisper: *"…line 212 still remembers what you did…"*
6. *"What keeps you here?"* Ghost names unfinished business. `tercera resurrect`. Tests turn green
7. Ofrenda opens in browser: candles with every contributor's name
8. **Closing text:** *"The third death is being forgotten. No one gets forgotten here."*

---

## 🗂️ Project Structure

```
la-tercera-muerte/
├── tercera/
│   ├── __init__.py       # Version, docstring
│   ├── cli.py            # Typer commands: exhume, seance, resurrect, ofrenda
│   ├── config.py         # Config loader (config.toml)
│   ├── exhume.py         # Git log, authors, TODOs, deps, tests → grave.json
│   ├── certificate.py    # Death certificate generation
│   ├── persona.py        # Builds ghost system prompt from grave.json
│   ├── memory.py         # Chunk + embed codebase into LanceDB
│   ├── seance_tui.py     # Textual app: flicker, whispers, idle haunting
│   ├── unfinished.py     # Detect unfinished business
│   ├── resurrect.py      # Agent loop in Docker sandbox
│   ├── ofrenda.py        # Renders OFRENDA.md + ofrenda.html
│   ├── voice.py          # Optional: whisper.cpp + Piper TTS
│   └── llm.py            # Thin Ollama wrapper (model swap via config)
├── sandbox/
│   └── Dockerfile.tmpl   # Template for language-specific sandbox
├── config.toml           # Default configuration
├── pyproject.toml        # Package metadata
└── README.md
```

---

## ⚙️ Optional: Voice Mode

Install `whisper.cpp`, `piper`, and `sox`, then set `enabled = true` in `config.toml`:

```toml
[voice]
enabled = true
whisper_model = "base"
piper_voice = "en_US-lessac-medium"
reverb = true   # ghostly reverb effect
```

The ghost will speak with a pitch-shifted, reverb-soaked voice. You can talk back.

---

## 🌼 Finding Dead Repos to Exhume

Good candidates:
- GitHub Explore → Archived repositories
- Search GitHub for `archived:true` + old language-specific terms
- Your own old repos with the last commit years ago
- Famous abandoned projects: `node-fibers`, `bower`, `grunt-contrib-*` plugins

Small Python 2 projects make the best demo targets — the cause of death is clear, the
resurrection challenge is real, and `pytest` gives you a clean pass/fail signal.

---

## 📜 License

MIT — because the whole point is that this can never be taken away.

---

*🌼🕯️🌼🕯️🌼🕯️🌼🕯️🌼🕯️🌼*

*La tercera muerte es cuando nadie pronuncia tu nombre.*
*Hoy pronunciamos tu nombre.*
