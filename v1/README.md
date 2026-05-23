# CBIM — User Manual

> This file travels with the framework. Read it after installation to understand how to use CBIM.
>
> Full documentation: https://github.com/nan023062/cbim
> 中文版: [README.zh-CN.md](README.zh-CN.md)

---

## Install

1. Open your project root in Claude Code.
2. In the Claude prompt, run:
   ```
   /cbim_install
   ```
3. Claude downloads the kernel from https://github.com/nan023062/cbim into `<project>/.cbim/kernel/`, then runs `python3 -m engine init` from inside it to populate the project (shims, agents, slash commands, hooks, MCP server, `CLAUDE.md`, `.gitignore`).
4. **Restart Claude Code** so the `SessionStart` hook fires.

After install, the project root contains:

- `.cbim/run` (POSIX, 0755) + `.cbim/run.cmd` (Windows) — launcher shims; export `PYTHONPATH=<project>/.cbim/kernel` and exec `python -m engine "$@"`
- `.cbim/kernel/` — vendored kernel (gitignored)
- `.cbim/config.json`, `.cbim/logs/`, `.cbim/memory/{short,medium}/` — engine state (gitignored)
- `.claude/agents/{architect,auditor,hr,programmer}/` — 4 core agents
- `.claude/commands/cbim_{install,help,dashboard,debug,log,sched}.md` — 6 slash commands
- `.claude/settings.json` — hooks + `mcpServers.cbim` entry
- `CLAUDE.md` — assistant identity (coordination hub)
- `.claudeignore` — paths Claude Code excludes from its read scope
- `.gitignore` — adds `.cbim/`

**Refresh / upgrade.** Re-run `/cbim_install` — it's idempotent. The shim and kernel are regenerated; your `.dna/` and `.cbim/memory/` are preserved.

**Uninstall.** `rm -rf .cbim/`, then remove `.claude/agents/{architect,auditor,hr,programmer}/`, the 6 `.claude/commands/cbim_*.md`, the `mcpServers.cbim` + hook entries in `.claude/settings.json`, the CBIM block from `CLAUDE.md`, and the `.cbim/` line in `.gitignore`.

**Migration from an earlier layout.** If `<project>/cbim-cc/` exists from a pre-rename install, `rm -rf cbim-cc/` and re-run `/cbim_install`. The shim regenerates automatically with the new `.cbim/kernel/` path.

There is no `cbim` CLI on your PATH, no global `pip install`, no project-version pinning. The sole runtime entry is `.cbim/run <subcommand>`.

For the canonical install spec see [`.cbim/kernel/project/commands/cbim_install.md`](src/kernel/project/commands/cbim_install.md) inside this repo, or the same file inside your project after install.

---

## First Use

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
| `/cbim_install` | Install or refresh CBIM in the current project (downloads kernel into `.cbim/kernel/`, writes the `.cbim/run` shim, registers hooks + MCP server) |
| `/cbim_help` | Framework overview (workflow + command list + key paths) |
| `/cbim_dashboard` | Open the local dashboard (memory / capability / knowledge / log) |
| `/cbim_debug on\|off\|status` | Toggle/inspect extra engine-internal logging |
| `/cbim_log [N]` | Show the current session log (agent loop signals) |
| `/cbim_sched status\|trigger <name>` | Inspect / fire scheduler tasks |

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

The server is implemented with the official `mcp` Python SDK (FastMCP) and runs via the project-local `.cbim/run mcp` shim — no global install, no `pip install` step. The shim sets `PYTHONPATH=<project>/.cbim/kernel` and invokes `python -m engine mcp`.

## Scheduler

An async task scheduler is embedded in the MCP server (started in its lifespan). It ticks every 30 seconds and dispatches built-in tasks that ship with the kernel package (`mcp_server.tasks`).

Each task subclasses `mcp_server.scheduler.Task` and declares `name`, `description`, `interval_seconds` (0 = manual-only), and `respect_cc_idle` (True = only fire when CC is idle, per `.cbim/.cc-status`). Tasks currently ship inside the kernel; there is no project-local task drop-in path yet.

`UserPromptSubmit` and `Stop` hooks maintain `.cbim/.cc-status` (`busy` / `idle`) so opt-in tasks only fire between turns. State persists in `.cbim/scheduler/state.json`; results are logged as `[SCHED]` in the session log.

**Lifetime**: the scheduler runs inside the MCP server process. CC starts the server (via the `.cbim/run mcp` shim registered in `.claude/settings.json` under `mcpServers.cbim`) → scheduler starts; CC exits → scheduler stops.

---

## Directory Structure

`.dna/` directories are **modules** scattered through the codebase at any depth where a module exists; they form a tree by filesystem hierarchy. The project root **does not** require a `.dna/`. The only hard requirement is the framework-managed registry at `.cbim/index.md` (created by install, updated by `init_module`).

```
your-project/
├── CLAUDE.md                      ← Assistant identity (main session)
│
├── .claude/
│   ├── settings.json              ← Permission config + hook registration + MCP server registration
│   ├── agents/                    ← Architect / HR / Auditor / Programmer (installed by /cbim_install)
│   └── commands/                  ← Slash commands /cbim_install, /cbim_help, /cbim_dashboard, /cbim_debug, /cbim_log, /cbim_sched
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
    ├── run                        ← POSIX launcher shim (sets PYTHONPATH, execs `python -m engine`)
    ├── run.cmd                    ← Windows launcher shim
    ├── config.json                ← Local framework config
    ├── .dna/index.md              ← Module registry (framework-managed)
    ├── logs/                      ← Engine logs (gitignored)
    ├── memory/                    ← Memory store (gitignored)
    │   ├── short/                 ← Short-term session memory
    │   └── medium/                ← Medium-term distilled memory
    └── kernel/                    ← Kernel install (downloaded by /cbim_install)
        ├── engine/                ← Unified CLI dispatcher (memory / dna / agent / skill / hook / mcp / dashboard ...)
        ├── cbi/                   ← Capability + business primitives + resources
        ├── memory/                ← Memory engine
        ├── hooks/                 ← SessionStart / Stop / UserPromptSubmit / PreToolUse hook scripts
        ├── mcp_server/            ← FastMCP server + scheduler + built-in tasks
        ├── dashboard/             ← Local dashboard server
        ├── services/              ← Cross-cutting services (frontmatter, ids, ...)
        ├── project/               ← Init / sync / templates
        └── context.py             ← Shared root-resolution module
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
| Short-term | `.cbim/memory/short/` | Raw session records (cleaned after 3 days) |
| Medium-term | `.cbim/memory/medium/` | Compressed pattern summaries |
| Knowledge | `.cbim/cbi/skills/` + `.dna/` | Crystallized into governance structures |

`SessionStart` hook automatically injects at session start: project knowledge snapshot + last session recovery point + recent memory.
`Stop` hook distills the just-finished session into `memory/short/`.
`PreToolUse` hook (inert by default) writes tool-call logs to `.cbim/logs/tools.txt` when `/cbim_debug on` is set.

---

## Dashboard

Run `/cbim_dashboard` (or `.cbim/run dashboard`) — opens http://127.0.0.1:8765 with Memory / Capability / Knowledge / Log tabs. The dashboard is also auto-spawned in the background by the `auto_preview` hook when CC is idle.

---

## Architecture Details

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | [架构文档（中文）](docs/ARCHITECTURE.zh-CN.md)
