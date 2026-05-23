# CBIM

[English](README.md) | [中文](README.zh-CN.md)

> CBIM (Capability–Business Independence + Memory) is a cc-prompt-pack for Claude Code. It splits a project along two axes — **capability** (specialized agents and skills) and **business** (a per-module `.dna/` knowledge tree) — and adds a session-spanning **memory** pipeline so each task loads only `target-agent-soul × task-subtree.dna`, never the whole project. The result: bounded context, fewer hallucinations, durable cross-session knowledge.

This repo hosts two implementations:

| | [V1 — CC Kernel](v1/) | [V2 — Native Agent](v2/) |
|---|---|---|
| **What it is** | CBIM riding on Claude Code — prompts, agent definitions, Python hooks, an MCP server | Standalone C# / .NET 8 runtime with a deterministic scheduler |
| **Status** | Available — see install below | Design phase — see [`v2/`](v2/) |

Everything below describes **V1**.

---

## Install

1. Open your project root (cd into it; this is the directory where CBIM will live).
2. From the project root, run:

   ```bash
   curl -sSL https://raw.githubusercontent.com/nan023062/cbim/master/install.sh | bash
   ```

3. The script clones the repo into a temp directory, copies `v1/src/kernel/` into `<project>/.cbim/kernel/` (flat — `engine/`, `cbi/`, `memory/`, `project/` are direct children), then runs `python3 -m engine init` to populate the project (launcher shims, agents, slash commands, hooks, MCP server, `CLAUDE.md`, `.gitignore`). `init` also builds a managed venv at `<project>/.cbim/.venv/` and installs the `mcp` SDK into it — your system Python is untouched. Requires `git` and `python3` ≥ 3.10 on PATH; no global `pip install`.
4. **Restart Claude Code** so the `SessionStart` hook fires.

Native Windows is not supported by `install.sh` (POSIX bash); use WSL.

After install, the project root contains:

- `.cbim/run` (POSIX, 0755) + `.cbim/run.cmd` (Windows) — launcher shims; each resolves its own directory and execs `.cbim/.venv/bin/python -m engine "$@"` with `PYTHONPATH=<project>/.cbim/kernel`. No absolute interpreter path is baked in — `.cbim/` is self-contained.
- `.cbim/.venv/` — managed venv (gitignored); built by `engine init` with the bootstrap `python3`, then holds `mcp` and any future CBIM Python deps. Your system Python is never modified.
- `.cbim/kernel/` — vendored kernel (gitignored)
- `.cbim/config.json`, `.cbim/logs/`, `.cbim/memory/{short,medium}/` — engine state (gitignored)
- `.claude/agents/{architect,auditor,hr,programmer}/` — 4 core agents
- `.claude/commands/cbim_{install,help,dashboard,debug,log,sched}.md` — 6 slash commands
- `.claude/settings.json` — hooks (registered as `.cbim/run hook <event>`) + `mcpServers.cbim` entry (runs `.cbim/run mcp`) + `permissions.deny` for `Write(.cbim/**)` / `Edit(.cbim/**)`
- `CLAUDE.md` — assistant identity (coordination hub); regenerated on every `/cbim_install`
- `.claudeignore` — paths Claude Code excludes from its read scope
- `.gitignore` — appends `.cbim/`

**Refresh / upgrade.** Once the first install has completed, the `/cbim_install` slash command is registered in `.claude/commands/`. From then on, re-run it from the Claude prompt — it's idempotent. The shim and kernel are regenerated; your `.dna/` and `.cbim/memory/` are preserved. There is no `cbim update` CLI; the slash command is the canonical refresh path. (Re-running the `install.sh` curl command from step 2 is also a valid refresh — it overwrites `.cbim/kernel/` and re-runs `engine init`, preserving `.cbim/memory/`, `.cbim/scheduler/`, `.cbim/config.json`, and `.dna/`.)

**Uninstall.** `rm -rf .cbim/`, then remove `.claude/agents/{architect,auditor,hr,programmer}/`, the 6 `.claude/commands/cbim_*.md` files, the `mcpServers.cbim` + hook entries in `.claude/settings.json`, the CBIM block from `CLAUDE.md`, and the `.cbim/` line in `.gitignore`. There is no uninstall CLI.

**Migration from an earlier layout.** If `<project>/cbim-cc/` exists from a pre-rename install, `rm -rf cbim-cc/` and re-run `/cbim_install`. The shim regenerates with the new `.cbim/kernel/` path. No automated migrator script exists — this is the entire migration procedure.

There is **no `cbim` CLI on your PATH**, **no global `pip install`**, **no project-version pinning**. The sole runtime entry is `.cbim/run <subcommand>`, which dispatches through the project-local venv at `.cbim/.venv/`.

For the canonical install spec see [`v1/src/kernel/project/commands/cbim_install.md`](v1/src/kernel/project/commands/cbim_install.md).

---

## First Use

Restart Claude Code, then send:

> **"Please initialize the module knowledge system for this project"**

The assistant dispatches the architect to build the `.dna/` knowledge system. After that, you're ready.

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

`.dna/` directories are **modules** scattered through the codebase at any depth where a module exists; they form a tree by filesystem hierarchy. The project root **does not** require a `.dna/`. The only hard requirement is the framework-managed registry at `.cbim/.dna/index.md` (created by install, updated by `init_module`).

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

Note on long-term memory: `.cbim/memory/short/` and `.cbim/memory/medium/` are created at install time. A long-term tier (if/when distilled from medium) is created on demand by the distill flow, not by `init`.

---

## Two-Layer Governance

| Layer | Governed by | Scope | Rule |
|-------|-------------|-------|------|
| **Capability layer** | HR | `.claude/agents/` + `.cbim/kernel/cbi/skills/` | No project-specific content |
| **Business layer** | Architect | `.dna/` (`module.md` = sole hard constraint; extensions optional) | No agent spec references |

The `.dna/` convention follows **minimal constraint + open extension**: the directory's existence marks a module; `module.md` is the only required file (YAML frontmatter + architecture body in one file); `contract.md`, `workflows/`, and any user-defined files are optional.

| Skill type | Storage | Characteristics |
|------------|---------|----------------|
| **Capability skill** | `.cbim/kernel/cbi/skills/` | Agent private capability; portable; governed by HR |
| **Business skill** | `.dna/workflows/` | Module deterministic process; project-bound; governed by architect |

---

## Memory System

| Stage | Path | Purpose |
|-------|------|---------|
| Short-term | `.cbim/memory/short/` | Raw session records (cleaned after 3 days) |
| Medium-term | `.cbim/memory/medium/` | Compressed pattern summaries |
| Knowledge | `.cbim/kernel/cbi/skills/` + `.dna/` | Crystallized into governance structures |

`SessionStart` hook automatically injects at session start: project knowledge snapshot + last session recovery point + recent memory.
`Stop` hook distills the just-finished session into `memory/short/`.
`PreToolUse` hook (inert by default) writes tool-call logs to `.cbim/logs/tools.txt` when `/cbim_debug on` is set.

---

## Dashboard

Run `/cbim_dashboard` (or `.cbim/run dashboard`) — opens http://127.0.0.1:8765 with Memory / Capability / Knowledge / Log tabs. The dashboard is also auto-spawned in the background by the `auto_preview` hook when CC is idle.

---

## Architecture Details

See [v1/docs/ARCHITECTURE.md](v1/docs/ARCHITECTURE.md) | [架构文档（中文）](v1/docs/ARCHITECTURE.zh-CN.md)

---

## Requirements

- Python 3.10+ (`python3` on PATH at install time; baked into the shim as an absolute path)
- Claude Code CLI

## License

[MIT](LICENSE)
