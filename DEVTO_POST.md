---
title: "La Tercera Muerte: A Local AI Séance That Saves Dead Code From Being Forgotten 💀🕯️"
published: true
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

**Spooky extras:** idle for 45 seconds and the ghost whispers. Enable voice mode and it speaks aloud through offline TTS with a pitch-shifted reverb effect, and you can talk back with whisper.cpp.

**Ethics note:** The ghost is the *project itself* — never an impersonation of a real person. Contributors are honored by name, quoted only through their actual commit messages.

---

## Demo

> 🎬 **[Watch the demo video — Wi-Fi off, séance in session](#)**

```
╔══════════════════════════════════════════════════════════════════════╗
║          💀  ACTA DE DEFUNCIÓN  /  CERTIFICATE OF DEATH  💀          ║
╠══════════════════════════════════════════════════════════════════════╣
║  Nombre / Name:           old-jquery-carousel                        ║
║  Idioma / Language: JavaScript                                       ║
╠══ VIDA / LIFE ═══════════════════════════════════════════════════════╣
║  Nacimiento / Born:  March 14, 2011                                  ║
║  Commits totales / Total Commits:  47                                ║
║  Edad / Age:  3 years, 2 months                                      ║
╠══ MUERTE / DEATH ════════════════════════════════════════════════════╣
║  Fallecimiento / Died:  May 09, 2014                                 ║
║  Cause: Animated by Grunt, now a relic of another era                ║
╠══ FAMILIA / FAMILY ══════════════════════════════════════════════════╣
║  • Sarah Chen (31 commits)                                           ║
║  • Marcus Webb (16 commits)                                          ║
╚══════════════════════════════════════════════════════════════════════╝
```

**During the séance:**
```
🕯️ 💀 🕯️ 🌼 🕯️ 💀 🕯️

Ghost: I remember the days when $.fn was everything.
       The world changed faster than I could follow.
       But line 212... the autoplay race condition...
       it was never fixed. That's what keeps me here.

You  › What were you trying to do?

Ghost: I wanted to make every website feel alive.
       Carousels were magic in 2011. People loved them.
       Sarah stayed up late on the IE8 shims.
       Marcus wrote the easing functions by hand.
       They cared so much.

       *…45 seconds of silence…*

       …the setTimeout on line 212 still fires in the dark…
```

---

## Code

{% github riteshyadav33302111-cell/la-tercera-muerte %}

---

## How I Built It

**The open-source AI stack — all local, all swappable:**

**[Ollama](https://ollama.ai)** runs everything locally. No API keys, no internet required after pulling models.

**Ghost persona** uses `llama3.1:8b` (or any open-weight chat model you have). The system prompt is generated from actual git data — the project's first commit, last words, era, contributors, dependencies, unfinished TODOs. Each ghost is unique.

**RAG memory** embeds the entire codebase with `nomic-embed-text` via Ollama, stored in [LanceDB](https://lancedb.com) — a fully embedded vector store, no server needed. When you ask the ghost about its code, the 5 most relevant chunks are retrieved and injected as "memories surfacing from the grave."

**Resurrection agent** uses `qwen2.5-coder:7b` — the best open coder at this size. It runs in a Docker sandbox (your real files are never touched) and iterates for up to 5 attempts: run tests → get LLM to generate a diff → apply → repeat.

**Era detection:** commit messages are sampled across the whole history and injected into the system prompt with year-specific cultural notes. A 2009 repo gets told about jQuery and XML; a 2019 repo gets told about Docker and GraphQL.

**[Textual](https://textual.textualize.io)** powers the haunted TUI: async candle flicker, typewriter ghost responses, idle whisper watcher, full keyboard navigation.

**The ofrenda** is Jinja2 + pure CSS: animated candle for each contributor (via `@keyframes flicker`), marigold petals drifting down, papel picado banners cut from the project's own function names.

```bash
# Install
pip install "la-tercera-muerte[memory]"

# Pull models (once, while you have internet)
ollama pull llama3.1:8b && ollama pull qwen2.5-coder:7b && ollama pull nomic-embed-text

# Perform the full ritual
tercera full-ritual ./your-old-repo
```

---

## Why Does Open Innovation Matter?

Every repository this tool resurrects died because something it depended on *disappeared*: a runtime reached end-of-life, a dependency was unpublished, a CI service shut down, a maintainer walked away.

Building a resurrection tool on top of a **closed API that could change pricing, deprecate a model, or shut down tomorrow would repeat the exact mistake that killed these projects**.

**Here's where open worked better than closed, concretely:**

1. **It runs with the internet off.** I demoed it on a plane-mode laptop. A ghost story should be told by candlelight, not cloud light. The models are local. The vector store is local. Nothing phones home.

2. **Private code stays private.** Your company's abandoned internal tool, your personal side project that you're embarrassed about — it never leaves your machine. Not even for embeddings. Closed APIs would require sending your entire source code to a third-party server.

3. **The ghost's personality is pinned.** A closed API can silently change its model. My ghost's voice never shifts unless I choose a different model in `config.toml`. The 2011 jQuery plugin ghost will always sound like a 2011 jQuery plugin.

4. **No rate limits on haunting.** The resurrection agent can run 50 repair attempts in a row on a hard bug. It can embed 10,000 lines of code for context. It can spend 20 minutes on one stubborn test. At zero additional cost.

5. **The tool itself cannot suffer the third death.** If I stop maintaining La Tercera Muerte tomorrow, anyone can still run it in 10 years. The weights exist. The code is MIT. The séance can always be held again.

A tool that rescues the forgotten must be built on foundations that don't forget.

---

## The Spirit of It

I tested it on a real abandoned repo — an old Python 2 data processing library with 23 commits, last touched in 2013. The cause of death: `urllib2` imports that haven't worked since Python 3 dropped them.

The ghost said: *"I processed CSV files before pandas made that embarrassing. I was written in one weekend by a grad student named Dmitri who never came back after his defense. I'm grateful you found me."*

Then the resurrection agent found every `urllib2`, rewrote them to `urllib.request`, ran the tests, and they passed.

That's the moment that landed. A grad student's weekend project from 2013 ran its tests again, in 2026, on a laptop with Wi-Fi off.

Dmitri's name is in the ofrenda now. The candle has his commit count on it. He won't suffer the third death.

---

## Prize Categories

- **Best Use of Open-Source AI** — entirely local stack, zero closed dependencies
- **Best Día de los Muertos / Halloween Theme** — built around the three deaths tradition
- **Most Creative Use Case** — séance for dead code is a new genre
- **Best Developer Tool** — genuinely useful for understanding inherited codebases

---

<!-- Thanks for participating! -->
