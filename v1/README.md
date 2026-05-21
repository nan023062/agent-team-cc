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
| `/cbim_debug on\|off\|status` | Toggle/inspect extra engine-internal logging |
| `/cbim_log [N]` | Show the current session log (agent loop signals) |
| `/cbim_sched status\|trigger <name>` | Inspect / fire scheduler tasks |
| `/cbim_update` | Upgrade the CBIM kernel to latest (equivalent to `cbim update -y`) |

## MCP Tools

CBIM also ships as an MCP server registered in `.claude/settings.json` under `mcpServers.cbim`. The assistant can invoke the following tools directly, no `cbim ...` Bash needed:

| Tool | Purpose |
|---|---|
| `memory_query` / `memory_list` / `memory_create` / `memory_delete` | CBIM memory store access |
| `dna_list` / `dna_show` / `dna_reindex` | Module knowledge (.dna/) |
| `agent_list` / `agent_show` | Claude Code agent registry |
| `skill_list` / `skill_show` | CBIM skill catalog |
| `project_snapshot` | Full project knowledge snapshot |
| `scheduler_status` / `scheduler_trigger` | Inspect and fire scheduled tasks |

The server is implemented with the official `mcp` Python SDK (FastMCP). Source: `.cbim/mcp_server/server.py`; install via `pip install -r .cbim/mcp_server/requirements.txt` in the project venv.

## Scheduler

An async task scheduler is embedded in the MCP server (started in its lifespan). It ticks every 30 seconds and dispatches tasks discovered under `.cbim/mcp_server/tasks/*.py`.

Each task subclasses `mcp_server.scheduler.Task`:

```python
from mcp_server.scheduler import Task

class MyTask(Task):
    name = "my-task"
    description = "Poll something or run a benchmark"
    interval_seconds = 600       # 0 = manual only
    respect_cc_idle = True       # only fire when CC is idle (per .cbim/.cc-status)

    async def run(self, context: dict) -> str:
        # context: {project_root, cbim_root, cc_idle}
        return "summary line written to session log + state.json"
```

`UserPromptSubmit` and `Stop` hooks maintain `.cbim/.cc-status` (`busy` / `idle`) so opt-in tasks only fire between turns. State persists in `.cbim/scheduler/state.json`; results are logged as `[SCHED]` in the session log.

**Lifetime**: the scheduler dies when Claude Code exits the MCP server. For tasks that must run when CC is offline, launch the server standalone (`python .cbim/mcp_server/server.py`) — same code path, no CC required.

---

## Directory Structure

`.dna/` directories are **modules** scattered through the codebase at any depth where a module exists; they form a tree by filesystem hierarchy. The project root **does not** require a `.dna/`. The only hard requirement is the framework-managed registry at `.cbim/index.md` (created by install, updated by `init_module`).

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
├── src/                           ← Your code (any layout you like)
│   ├── combat/
│   │   ├── .dna/                  ← Module (parent): describes children + boundaries
│   │   │   ├── module.md          ← required: frontmatter + architecture body
│   │   │   ├── contract.md        ← optional: protocol boundary
│   │   │   ├── workflows/         ← optional: deterministic process definitions
│   │   │   └── ...                ← optional: any user-defined files
│   │   ├── skill/.dna/            ← Module (leaf): specific implementation
│   │   └── buff/.dna/             ← Module (leaf)
│   └── economy/.dna/              ← Module
│
├── .dna/                          ← OPTIONAL project-root module
│   └── module.md                  ←   (only if your project root is itself a module —
│                                  ←    single-app shape; monorepos often skip this)
│
└── .cbim/                         ← Framework (this directory)
    ├── .dna/index.md              ← Module registry (framework-managed, required after install)
    ├── .pin                       ← Project-pinned CBIM schema version (single line)
    ├── cbi/                       ← Capability + business definitions, agents, skills
    ├── engine/                    ← Unified CLI entry (invoked via `cbim ...`)
    ├── hooks/                     ← SessionStart / Stop / PreToolUse hook scripts
    ├── memory/                    ← Memory engine + store
    ├── dashboard/                 ← Local dashboard server
    ├── docs/                      ← Architecture documentation
    └── config.json                ← Local framework config
```

---

## Version Pin & Upgrade

Since 1.3.3, the project-pinned CBIM schema version lives in `.cbim/.pin` (plain text, single-line version number, trailing newline, gitignored). All reads/writes go through the sole accessor `project/pin.py` (`read_pin` / `write_pin`). `.cbim/config.json` no longer carries a `cbim_version` field.

Upgrade and migrate:

| Operation | Command |
|---|---|
| Upgrade the CBIM kernel | `cbim update -y` or `/cbim_update` |
| Migrate the current project to a specific version | `cbim migrate --version <X>` |

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
| Short-term | `.cbim/memory/short/` | Raw session records (cleaned after 3 days) |
| Medium-term | `.cbim/memory/medium/` | Compressed pattern summaries |
| Knowledge | `.cbim/cbi/skills/` + `.dna/` | Crystallized into governance structures |

`SessionStart` hook automatically injects at session start: project knowledge snapshot + last session recovery point + recent memory.
`Stop` hook distills the just-finished session into `memory/short/`.
`PreToolUse` hook (inert by default) writes tool-call logs to `.cbim/logs/tools.txt` when `/cbim_debug on` is set.

---

## Dashboard

```bash
python -m dashboard.dashboard    # macOS / Linux  (run from .cbim/)
dashboard\dashboard.bat          # Windows
```

Open http://127.0.0.1:8765 — Memory / Capability / Knowledge / Log tabs.

---

## Architecture Details

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | [架构文档（中文）](docs/ARCHITECTURE.zh-CN.md)
