# CBIM — User Manual

> This file travels with the framework. Read it after installation to understand how to use CBIM.
>
> Full documentation: https://github.com/nan023062/cbim

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

## Directory Structure

```
your-project/
├── CLAUDE.md                      ← Assistant identity (main session)
├── .venv/                         ← Python virtual environment (gitignored)
│
├── .claude/
│   ├── settings.json              ← Permission config + hook registration
│   └── agents/
│       ├── architect/             ← Architect
│       ├── hr/                    ← HR
│       ├── auditor/               ← Auditor
│       └── programmer/            ← Programmer (default work agent)
│
├── .dna/                          ← Project knowledge root module (created by architect)
│   ├── index.md
│   ├── module.json
│   ├── architecture.md
│   └── contract.md
│
└── cbim/                          ← Framework (this directory)
    ├── install.py / install.bat   ← Installer
    ├── cc-template/               ← Claude Code templates
    ├── knowledge/                 ← Knowledge engine + capability skills
    ├── memory/                    ← Memory engine + store
    └── preview/                   ← Local visualization server
```

---

## Two-Layer Governance

| Layer | Governed by | Scope | Rule |
|-------|-------------|-------|------|
| **Capability layer** | HR | `.claude/agents/` + `cbim/knowledge/skills/` | No project-specific content |
| **Business layer** | Architect | `.dna/` (module knowledge + workflows/) | No agent spec references |

| Skill type | Storage | Characteristics |
|------------|---------|----------------|
| **Capability skill** | `cbim/knowledge/skills/` | Agent private capability; portable; governed by HR |
| **Business skill** | `.dna/workflows/` | Module deterministic process; project-bound; governed by architect |

---

## Memory System

| Stage | Path | Purpose |
|-------|------|---------|
| Short-term | `cbim/memory/store/short/` | Raw session records |
| Medium-term | `cbim/memory/store/medium/` | Compressed pattern summaries |
| Knowledge | `cbim/knowledge/skills/` + `.dna/` | Crystallized into governance structures |

SessionStart hook automatically injects at session start: project knowledge snapshot + last session recovery point + recent memory.

---

## Preview

```bash
python -m preview.preview      # macOS / Linux  (run from cbim/)
preview\preview.bat            # Windows
```

Open http://127.0.0.1:8765 — Memory / Capability / Knowledge tabs.

---

## Architecture Details

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | [架构文档（中文）](docs/ARCHITECTURE.zh-CN.md)
