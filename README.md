# CBIM — Capability-Business Independence + Memory

> Context management framework for LLM agents. Multi-agent is not team simulation — it's a mechanism to isolate context along the capability dimension.

**CBIM** = **CBI** (Capability-Business Independence) + **M** (Memory)

---

## The Problem

The most common Claude Code workflow — one default agent + many CLAUDE.md rules + many skills — has a structural flaw that worsens over time:

- Turns accumulate → CLAUDE.md and skills get fully loaded → tokens explode, the LLM gets "lost in the middle," hallucinations rise, corrections pollute context further.
- Reset the session → context clears, but project memory is gone. You must re-grep, re-understand structure, re-brief the agent every time.

## The Principle

**Context = target agent's soul × task subtree's `.dna/`** — independent of total project size.

```
User → Assistant (CLAUDE.md, sole interface)
         ├── Architect    business layer governance (.dna/ knowledge)
         ├── HR           capability layer governance (agents, skills)
         ├── Auditor      independent critical review (read-only)
         └── Work agents  task execution (created by HR on demand)
```

---

## Two Implementations

| | [V1 — CC Kernel](v1/) | [V2 — Native Agent](v2/) |
|---|---|---|
| **What it is** | CBIM running on top of Claude Code — prompts, agent definitions, Python hooks | Standalone C# / .NET 8 runtime — no Claude Code dependency, deterministic state-machine scheduler |
| **Status** | **Available** — install and use today | **Design phase** — architecture whitepaper in [`v2/`](v2/) |
| **Install** | `python v1/src/install.py` | — |
| **Who it's for** | Claude Code users who want multi-agent coordination + memory today | Future: any environment, any host LLM |

V1 validates the CBIM philosophy within the Claude Code ecosystem. V2 reimplements the same model as a compiled runtime so context pruning, dispatch routing, and state changes become deterministic instead of probabilistic.

---

## Quick Start — V1 (Claude Code Kernel)

### Option 1: One-liner via Claude Code (recommended)

In your target project, paste this message to Claude Code:

```
Please fetch https://raw.githubusercontent.com/nan023062/cbim/master/v1/docs/INSTALL.md to get the CBIM installation SOP, then execute all steps starting after the first divider line to install in the current project.
```

### Option 2: Machine-level installer (global kernel)

```bash
git clone https://github.com/nan023062/cbim.git
cd cbim
python v1/src/install.py
```

Installs the kernel to `~/.cbim/kernel/`, sets up a shared venv, and puts `cbim` on your PATH. Then in any project:

```bash
cbim init       # bootstrap .cbim/ in the current project
```

### Option 3: Manual copy

Follow [`v1/docs/INSTALL.md`](v1/docs/INSTALL.md) — copy four runtime artifacts (`.cbim/`, `.claude/`, `CLAUDE.md`, `.claudeignore`) into your project. Merge semantics preserve existing settings.

---

## After Install (V1)

The installed framework ships its own user manual inside the target project:

- **User manual**: `.cbim/README.md` — usage, directory layout, slash commands, governance model
- **Architecture deep dive**: `.cbim/docs/ARCHITECTURE.md`

---

## Requirements (V1)

- Python 3.10+
- Claude Code CLI

## License

[MIT](LICENSE)
