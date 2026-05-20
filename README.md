[English](README.md) | [中文](README.zh-CN.md)

# CBIM — Capability-Business Independence + Memory

> Context management framework for Claude Code. Multi-agent is not team simulation — it's a mechanism to isolate context along the capability dimension.

**CBIM** = **CBI** (Capability-Business Independence) + **M** (Memory)

## What Problem It Solves

The most common Claude Code workflow: **one default agent + many CLAUDE.md rules + many skills**.

This pattern has a structural flaw that worsens over time: as conversation turns increase, CLAUDE.md and skill files get fully loaded into context — tokens explode, the LLM gets "lost in the middle," hallucination rates rise, output quality drops, and corrections pollute context further.

Resetting the session clears context but creates another problem: memory loss. You must re-grep the codebase, re-understand the structure, and manually re-brief the agent on project background every time.

CBIM solves both at once:

| Problem | CBIM Solution |
|---------|---------------|
| Context bloat accumulates with turns | Multi-agent × module topology tree: each task loads only target agent soul + task subtree `.dna/` |
| Memory lost on session reset | SessionStart hook auto-injects module snapshot + recent memory — zero-cost recovery |

---

## Design Philosophy

Core = **Multi-Agent (capability axis) × Module Topology Tree (business axis)**

- **Capability axis**: Specialized agents — each task loads only the target agent's soul, no excess capability context
- **Business axis**: `.dna/` directories form a topology tree by module boundary (`module.md` = sole hard constraint per module), loads only the task's subtree, no excess business context
- **Memory**: Cross-session accumulated material — shared source for session recovery, capability governance (HR distills → skills → soul), and business governance (architect distills → `.dna/` workflows)

Each task's context = target agent soul × task subtree `.dna/` — independent of total project size.  
Less context → fewer hallucinations → fewer errors → fewer corrections → net token cost lower than a monolithic agent.

---

## Execution Roles (Context Isolation Mechanism)

CBIM uses specialized agents to isolate context along the capability dimension — each task loads only the target agent's soul, no excess capability context. This is not team simulation; it is context control.

```
User
  ↓
Assistant (CLAUDE.md — sole external interface, task routing)
  ├── Architect    Business layer governance: design and maintain project knowledge (.dna/)
  ├── HR           Capability layer governance: work agent lifecycle management
  ├── Auditor      Independent critical review (adversarial perspective, read-only)
  └── Work Agents  Execute specific tasks (created by HR on demand)
```

You only talk to the assistant. The assistant understands intent, decomposes tasks, routes to the right agent, and consolidates results.

---

## Quick Start

### Option 1: One-liner via Claude Code (recommended)

Open Claude Code in the target project directory and send this message — the agent will complete all installation steps automatically:

```
Please fetch https://raw.githubusercontent.com/nan023062/cbim/master/INSTALL.md to get the CBIM installation SOP, then execute all steps starting after the first divider line to install in the current project.
```

### Option 2: Manual installation

```bash
# 1. Clone CBIM into the target project's cbim/ directory
git clone --branch master https://github.com/nan023062/cbim.git cbim

# 2. Run the installer
python3 cbim/install.py        # macOS / Linux
# or double-click cbim/install.bat  # Windows

# 3. Restart Claude Code
claude
```

---

## First Use After Installation

After restarting Claude Code, send:

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

## Directory Structure (After Deployment)

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
│   ├── index.md                   ← root-module-only: all module paths in the tree
│   ├── module.md                  ← required: sole hard constraint (frontmatter + architecture)
│   ├── contract.md                ← optional: protocol boundary
│   ├── workflows/                 ← optional: deterministic process definitions
│   └── ...                        ← optional: any user-defined files
│
└── cbim/                          ← Framework (git cloned here)
    ├── install.py                 ← Auto installer
    ├── install.bat                ← Windows entry point
    ├── cc-template/               ← Claude Code installation templates
    ├── knowledge/                 ← Knowledge engine (capability + business CRUD)
    ├── memory/                    ← Memory engine (FileBackend)
    └── preview/                   ← Local visualization server
```

---

## Two-Layer Governance · Two Types of Skills

| Layer | Governed by | Scope | Rule |
|-------|-------------|-------|------|
| **Capability layer** | HR | `.claude/agents/` (soul) + `cbim/knowledge/skills/` (capability skills) | soul/skills must contain zero project-specific content |
| **Business layer** | Architect | Each project's `.dna/` (`module.md` = sole hard constraint; extensions optional) | knowledge files must not reference agent specs |

The `.dna/` convention: **minimal constraint + open extension**. Directory exists = module. `module.md` is the only required file (YAML frontmatter + architecture body). `contract.md`, `workflows/`, and user-defined files are all optional.

CBIM splits skills by "who owns it" — `.claude/` only contains `agents/`, no skill pile-ups:

| Type | Storage | Characteristics |
|------|---------|----------------|
| **Capability skill** | `cbim/knowledge/skills/` | Agent private capability; portable; governed by HR |
| **Business skill** | `.dna/workflows/` | Module deterministic process; project-bound; governed by architect |

---

## Memory System

Memory is a three-stage distillation pipeline, not just context recovery:

| Stage | Path | Purpose |
|-------|------|---------|
| Short-term | `cbim/memory/store/short/` | Raw session records; tagged `distilled` after processing, cleaned up after 3 days |
| Medium-term | `cbim/memory/store/medium/` | Compressed pattern summaries; archived after promotion to knowledge layer |
| Knowledge (core) | `cbim/knowledge/skills/` + `.dna/` | Crystallized structure: capability → skills/soul, business → workflows |

Short → Medium is **compression**; Medium → Knowledge is **the critical step** — crystallizing validated patterns into governance structures that serve as the foundation for all future tasks.

SessionStart hook automatically injects at session start: project knowledge snapshot (module tree + agent list) + last session recovery point + recent memory.

---

## Architecture Details

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | [架构文档（中文）](docs/ARCHITECTURE.zh-CN.md)

---

## Requirements

- Python 3.10+
- Claude Code CLI
- No extra dependencies (memory engine defaults to FileBackend, pure standard library)

---

## License

[MIT](LICENSE)
