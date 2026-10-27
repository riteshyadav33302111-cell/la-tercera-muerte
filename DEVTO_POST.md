---
title: "La Tercera Muerte: A Local AI Séance That Saves Dead Code From Being Forgotten 💀🕯️"
published: false
tags: devchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 4: Ghost in the Machine](https://dev.to/challenges/hacktoberfest-week4-2026-10-26)*

---

## What I Built

In Mexican tradition, we say a person dies three times.

The **first death** is when the body stops.
The **second** is burial.
The **third, and the final one**, is when nobody says your name anymore.

Día de los Muertos exists to stop that third death.

**Software dies the same way.** A repo gets its last commit, gets archived, and is eventually forgotten along with everyone who built it.

**La Tercera Muerte** is a fully offline AI tool that *exhumes* an abandoned git repository and turns it into a ghost you can talk to — in a haunted terminal, with candles flickering and whispers in the silence.

The ghost knows its own history. It remembers the people who built it. It speaks in the voice of its era — a 2011 jQuery plugin sounds very different from a 2020 Rust crate. It has unfinished business: a failing test, a last `TODO`, a dependency that died. An open-source coding agent runs inside a Docker sandbox and tries to finish that business so the ghost can rest.

At the end, the tool builds a **digital ofrenda**: an animated candlelit HTML altar committed back into the repo, with a candle for every contributor, their dependencies as offerings, and an epitaph so they are remembered.

**The five rituals:**

| # | Ritual | What happens |
|---|--------|-------------|
| 1 | Exhumación | `tercera exhume ./old-repo` — git history, authors, TODOs, dependencies |
| 2 | Acta de Defunción | Death certificate: born, died, cause, last words, family |
| 3 | La Sesión | Haunted terminal séance — chat with the ghost using local RAG |
| 4 | Asuntos Pendientes | Ghost names its unfinished business; agent tries to fix it |
| 5 | La Ofrenda | `OFRENDA.md` + animated `ofrenda.html` altar |

**Spooky extras:** idle for 45 seconds and the ghost whispers. Optional voice mode allows speaking aloud through offline TTS and speech-to-text.

**Ethics note:** The ghost is the *project itself* — never an impersonation of a real person. Contributors are honored by name, quoted only through their actual commit messages.

---

## Demo

> 🎬 *Demo video and altar preview to be added here.*

---

## Code

{% github riteshyadav33302111-cell/la-tercera-muerte %}

---

## How I Built It

**The open-source AI stack — all local, all swappable:**

**[Ollama](https://ollama.ai)** runs everything locally. No API keys, no internet required after pulling models.

**Ghost persona** uses `llama3.1:8b` (or any open-weight chat model you have). The system prompt is generated from actual git data — the project's first commit, last words, era, contributors, dependencies, unfinished TODOs. Each ghost is unique.

**RAG memory** embeds the entire codebase with `nomic-embed-text` via Ollama, stored in [LanceDB](https://lancedb.com) — a fully embedded vector store, no server needed. When you ask the ghost about its code, the 5 most relevant chunks are retrieved and injected as memories surfacing from the grave.

**Resurrection agent** *(planned/prototype)* uses `qwen2.5-coder:7b`. It runs in a Docker sandbox (your real files are never touched) and iterates: run tests → get LLM to generate a diff or file correction → apply → re-test.

**Era detection:** commit messages are sampled across history and injected into the system prompt with era-specific cultural notes. A 2009 repo gets context about jQuery and XML; a 2019 repo gets context about Docker and microservices.

**[Textual](https://textual.textualize.io)** powers the haunted TUI: async candle flicker, typewriter streaming responses, idle whisper watcher, full keyboard navigation.

**The ofrenda** is rendered with Jinja2 + pure CSS (no external web fonts, fully offline): animated candle for each contributor (via `@keyframes flicker`), marigold petals drifting down, papel picado banners cut from the project's own function names.

```bash
# Install from source
git clone https://github.com/riteshyadav33302111-cell/la-tercera-muerte
cd la-tercera-muerte
pip install -e ".[memory]"

# Pull models (once, while you have internet)
ollama pull llama3.1:8b && ollama pull qwen2.5-coder:7b && ollama pull nomic-embed-text

# Perform the full ritual
tercera full-ritual ./your-old-repo
```

---

## Why Does Open Innovation Matter?

Every repository this tool resurrects died because something it depended on *disappeared*: a runtime reached end-of-life, a dependency was unpublished, a CI service shut down, a maintainer walked away.

Building a resurrection tool on top of a **closed API that could change pricing, deprecate a model, or shut down tomorrow would repeat the exact mistake that killed these projects**.

**Here's where open worked better than closed:**

1. **It runs with the internet off.** A ghost story should be told by candlelight, not cloud servers. The models are local. The vector store is local. Nothing leaves your machine.

2. **Private code stays private.** Your team's abandoned internal tool, your personal side project — it never leaves your machine. Not even for embeddings. Closed APIs would require sending your source code to a third-party server.

3. **The ghost's personality is pinned.** A closed API can silently change its model. The local ghost's voice never shifts unless you choose a different model in `config.toml`.

4. **No rate limits on haunting.** The resurrection agent can run multiple repair attempts on a hard bug. It can embed thousands of lines of code for context at zero API cost.

5. **The tool itself cannot suffer the third death.** If maintenance ceases tomorrow, anyone can still run it in 10 years. The weights exist. The code is MIT. The séance can always be held again.

A tool that rescues the forgotten must be built on foundations that don't forget.

---

## The Spirit of It

Día de los Muertos is not about mourning loss; it is about keeping memory alive. In open-source software, millions of hours of human labor, creativity, and care sit inside archived GitHub repositories. When a project is abandoned, the contributors often disappear into history.

By treating the codebase as an artifact with a voice and building an ofrenda that lists every contributor with their commit count as a candle, La Tercera Muerte turns codebase archaeology into an act of remembrance.

---

## Prize Categories

- **Best Use of Open-Source AI** — entirely local stack, zero closed dependencies
- **Best Día de los Muertos / Halloween Theme** — built around the three deaths tradition
- **Most Creative Use Case** — séance for dead code
- **Best Developer Tool** — useful for understanding inherited codebases

---

<!-- Thanks for participating! -->
