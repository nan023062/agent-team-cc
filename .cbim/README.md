# CBIM — User Manual

> This file travels with the framework. Read it after installation to understand how to use CBIM.
>
> Full documentation: https://github.com/nan023062/cbim
> 中文版: [README.zh-CN.md](README.zh-CN.md)

---

## First Use After Installation

Restart Claude Code, then send:

> **"Please initialize the module knowledge system for this project"**

The assistant dispatches the architect to build the `.dna/` knowledge system. After that, you're ready to use it.

---

## How to Use

Just tell the assistant what you want — no need to specify an agent:

| What you want | Just say |
|---------------|----------|
| Initialize knowledge system | Please initialize the module knowledge system for this project |
| Create a feature module | Create a combat module |
| Implement a feature | Implement the login API per the current blueprint |
| Review a design | Review this change |
| Query a past decision | What was the decision history for the combat module |
| Recruit a work agent | Help me recruit an AI engineer agent |

---

## Slash Commands

| Command | Purpose |
|---|---|
| `/cbim_help` | Framework overview (workflow + command list + key paths) |
| `/cbim_debug on\|off\|status` | Toggle/inspect tool-call logging |
| `/cbim_log [N]` | Tail the last N tool-call log entries |

---

## Directory Structure

```
your-project/
├── CLAUDE.md                      ← Assistant identity (main session)
├── .venv/                         ← Python virtual environment (gitignored)
│
├── .claude/
│   ├── settings.json              ← Permission config + hook registration
│   ├── agents/                    ← Architect / HR / Auditor / Programmer
│   └── commands/                  ← Slash commands (/cbim_*)
│
├── .dna/                          ← Project knowledge root module (created by architect)
│   ├── index.md                   ← root-module-only: all module paths in the tree
│   ├── module.md                  ← required: sole hard constraint (frontmatter + architecture)
│   ├── contract.md                ← optional: protocol boundary
│   ├── workflows/                 ← optional: deterministic process definitions
│   └── ...                        ← optional: any user-defined files
│
└── .cbim/                         ← Framework (this directory)
    ├── install.py / install.bat   ← Installer (legacy; pure-copy install is preferred)
    ├── cbi/                       ← Capability + business definitions, agents, skills
    ├── engine/                    ← Unified CLI entry (python .cbim/engine ...)
    ├── installer/                 ← Install scripts + SessionStart/Stop hooks
    ├── memory/                    ← Memory engine + store
    ├── preview/                   ← Local visualization server
    ├── docs/                      ← Architecture documentation
    └── config.json                ← Local framework config
```

---

## Two-Layer Governance

| Layer | Governed by | Scope | Rule |
|-------|-------------|-------|------|
| **Capability layer** | HR | `.claude/agents/` + `.cbim/cbi/skills/` | No project-specific content |
| **Business layer** | Architect | `.dna/` (`module.md` = sole hard constraint; extensions optional) | No agent spec references |

The `.dna/` convention follows **minimal constraint + open extension**: the directory's existence marks a module; `module.md` is the only required file (YAML frontmatter + architecture body in one file); `contract.md`, `workflows/`, and any user-defined files are optional.

| Skill type | Storage | Characteristics |
|------------|---------|----------------|
| **Capability skill** | `.cbim/cbi/skills/` | Agent private capability; portable; governed by HR |
| **Business skill** | `.dna/workflows/` | Module deterministic process; project-bound; governed by architect |

---

## Memory System

| Stage | Path | Purpose |
|-------|------|---------|
| Short-term | `.cbim/memory/store/short/` | Raw session records (cleaned after 3 days) |
| Medium-term | `.cbim/memory/store/medium/` | Compressed pattern summaries |
| Knowledge | `.cbim/cbi/skills/` + `.dna/` | Crystallized into governance structures |

`SessionStart` hook automatically injects at session start: project knowledge snapshot + last session recovery point + recent memory.
`Stop` hook distills the just-finished session into `memory/store/short/`.
`PreToolUse` hook (inert by default) writes tool-call logs to `.cbim/logs/tools.txt` when `/cbim_debug on` is set.

---

## Preview

```bash
python -m preview.preview      # macOS / Linux  (run from .cbim/)
preview\preview.bat            # Windows
```

Open http://127.0.0.1:8765 — Memory / Capability / Knowledge tabs.

---

## Architecture Details

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | [架构文档（中文）](docs/ARCHITECTURE.zh-CN.md)
