[English](README.md) | [中文](README.zh-CN.md)

# CBIM — Capability-Business Independence + Memory

> Context management framework for Claude Code. Multi-agent is not team simulation — it's a mechanism to isolate context along the capability dimension.

**CBIM** = **CBI** (Capability-Business Independence) + **M** (Memory)

---

## The Problem

The most common Claude Code workflow — **one default agent + many CLAUDE.md rules + many skills** — has a structural flaw that worsens over time:

- Turns accumulate → CLAUDE.md and skills get fully loaded → tokens explode, the LLM gets "lost in the middle," hallucinations rise, corrections pollute context further.
- Reset the session → context clears, but project memory is gone. You must re-grep, re-understand structure, re-brief the agent every time.

## The Principle

**Context = target agent's soul × task subtree's `.dna/`** — independent of total project size.

| Problem | CBIM Solution |
|---------|---------------|
| Context bloat accumulates with turns | **Multi-agent (capability axis) × module topology tree (business axis)**. Each task loads only the target agent + the relevant module subtree. |
| Memory lost on session reset | **SessionStart hook** auto-injects: module snapshot + recent memory. Zero-cost recovery. |
| Knowledge dissipates across sessions | **Three-stage distillation pipeline**: short-term memory → medium-term patterns → crystallized knowledge (capability skills / `.dna/` workflows). |

```
User → Assistant (CLAUDE.md, sole interface)
         ├── Architect    business layer governance (.dna/ knowledge)
         ├── HR           capability layer governance (agents, skills)
         ├── Auditor      independent critical review (read-only)
         └── Work agents  task execution (created by HR on demand)
```

You only talk to the assistant. It decomposes intent, routes to the right agent, consolidates results.

---

## Two Delivery Forms

This repo hosts two implementations of the same CBIM model:

| Version | Form | Status | Where |
|---------|------|--------|-------|
| **V1 — Prompt edition** | Claude Code prompts, agent definitions, Python hooks | **Available now** | `install/` + `.cbim/` (this is what the quick start below installs) |
| **V2 — Native runtime** | C# / .NET 8 standalone runtime with Avalonia UI; deterministic state-machine scheduler replacing prompt-driven dispatch | **Coming soon** | [`CBIM/`](CBIM/) — design spec and architecture whitepaper |

V1 validates the CBIM philosophy (capability-business independence + memory paging) inside Claude Code. V2 lifts the same model into a strongly-typed native runtime so context pruning, dispatch routing, and state changes become deterministic instead of probabilistic.

---

## Quick Start (V1 — Prompt Edition)

### Option 1: One-liner via Claude Code (recommended)

In your target project, paste this message to Claude Code:

```
Please fetch https://raw.githubusercontent.com/nan023062/cbim/master/INSTALL.md to get the CBIM installation SOP, then execute all steps starting after the first divider line to install in the current project.
```

### Option 2: Copy-based manual install

Follow [`INSTALL.md`](INSTALL.md) — clone this repo to a temp dir, copy four runtime artifacts (`.cbim/`, `.claude/`, `CLAUDE.md`, `.claudeignore`) into your project, create a venv. Merge semantics preserve user-added settings.json keys and `.claudeignore` lines.

### Option 3: Legacy one-shot installer

```bash
git clone --branch master https://github.com/nan023062/cbim.git
cd cbim
python3 install/install.py --root /path/to/your/project
```

Restart Claude Code after install. Then send: **"Please initialize the module knowledge system for this project"**.

---

## After Install

The installed framework ships its own user manual:

- **User manual**: [`.cbim/README.md`](.cbim/README.md) | [`.cbim/README.zh-CN.md`](.cbim/README.zh-CN.md) — how to use, directory layout, slash commands, governance model
- **Architecture deep dive**: [`.cbim/docs/ARCHITECTURE.md`](.cbim/docs/ARCHITECTURE.md) | [`.cbim/docs/ARCHITECTURE.zh-CN.md`](.cbim/docs/ARCHITECTURE.zh-CN.md)

---

## Requirements

- Python 3.10+
- Claude Code CLI
- No extra dependencies (memory engine defaults to FileBackend, pure standard library)

## License

[MIT](LICENSE)
