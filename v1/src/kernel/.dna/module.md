---
name: cbim-kernel-pkg
owner: architect
description: CBIM kernel package: engine, project, cbi, memory, hooks, services, dashboard, mcp_server
keywords: []
dependencies: []
---

## Positioning

This module IS the CBIM kernel Python package — the single code drop that powers every per-project CBIM operation: CLI commands, Claude Code hook handlers, memory engine, dashboard server, MCP server, agent/skill primitives, and project bootstrap.

The whole package is installed verbatim under `<project>/.cbim/kernel/` by the `/cbim_install` slash command. There is exactly one install path (download tree + run `python -m engine init`) and exactly one runtime entry — the shim `.cbim/run` (POSIX) or `.cbim/run.cmd` (Windows), which sets `PYTHONPATH=<project>/.cbim/kernel` and execs `python -m engine "$@"`. No `cbim` binary on `PATH`. No global venv. No multi-version staging. No version pin.

## Sub-module Relationships

```mermaid
graph TD
    engine["engine/<br/>unified CLI dispatcher"]
    project["project/<br/>install-side: init, sync, templates, source-of-truth agents+commands+hook-scripts"]
    cbi["cbi/<br/>capability+business primitives (agents, skills, dna, snapshot)"]
    memory["memory/<br/>memory engine (file backend, chroma backend, loader, writer)"]
    services["services/<br/>cross-cutting facades (agent_service, memory_service, knowledge_service, log_service)"]
    dashboard["dashboard/<br/>local web UI server"]
    mcp["mcp_server/<br/>FastMCP stdio server (LLM governance tools) + scheduler + tasks"]
    ctx["context.py (leaf file)<br/>project_root / cbim_dir / kernel_root resolution"]

    engine --> project
    engine --> cbi
    engine --> memory
    engine --> dashboard
    engine --> mcp
    services --> cbi
    services --> memory
    services --> engine
    mcp --> services
    mcp --> cbi
    mcp --> memory
    mcp --> engine
    dashboard --> services
    project -.->|reads templates at install time only| cbi
```

Dependency direction is strict and unidirectional. The stable bottom: `context.py` (a single leaf file, no sub-package), `cbi`, `memory`. Mid-tier: `services`, `project`. Top-tier (orchestrators): `engine`, `dashboard`, `mcp_server`. Nothing below imports anything above. `cbi` and `memory` import only from `context` and their own internals.

Hook subprocesses are not a sub-package of the kernel: they live as install-time snapshots under `project/hooks_src/cbim_*.py`, get copied into `.claude/hooks/` at init, and bootstrap `<project>/.cbim/kernel/` onto `sys.path` to import `memory.*` / `cbi.*` / `engine.*` directly. No subprocess-to-server transport.

Loose kernel-root artefacts: `__init__.py` (exposes `__version__` read from `VERSION`), `VERSION` (single-line semver string), `requirements.txt` (runtime dependencies), `context.py` (shared root-resolution primitives).

## Origin Context

A CBIM "install" is just a directory tree. The user runs `/cbim_install` inside a project; that downloads this whole kernel package into `<project>/.cbim/kernel/` and runs `python -m engine init` once. Init writes the shim `.cbim/run`, installs the 4 agents under `.claude/agents/`, installs the 6 slash commands under `.claude/commands/`, installs the 7 in-process hook bridges under `.claude/hooks/cbim_*.py` (snapshot copied from `project/hooks_src/`), merges hook + MCP config into `.claude/settings.json`, drops a `CLAUDE.md`, and appends `.cbim/` to `.gitignore` plus the `permissions.deny` entries that keep LLM tools out of `.cbim/`. From then on the user (and Claude Code) invoke the kernel only via the shim — and LLM-driven writes to `.dna/`, `.claude/agents/`, and `.cbim/memory/` go through the `cbim` MCP server, never through raw `Write`/`Edit`.

Sub-modules exist because each one corresponds to a distinct invocation trigger or audience:

- `engine/` — invoked once per CLI command (human-typed; LLM `Bash` is blocked from `.cbim/run *` by `permissions.deny`)
- `dashboard/`, `mcp_server/` — long-lived servers spawned on demand. `mcp_server` exposes governance tools to the LLM over stdio; the dashboard serves the local web UI.
- `cbi/` — read at design time by agents (resources: Agent / Skill / DNAModule / Memory)
- `memory/` — persistent store accessed by hooks (in-process) and by the engine on user request
- `project/` — touched only at install / init / `project sync`; no runtime role. Source of truth for the agents, commands, hook scripts (under `hooks_src/`), templates, and `permissions.deny` entries that get snapshotted into the user's project.
- `services/` — façade layer so `mcp_server` and `dashboard` never reach into `cbi`/`memory` internals directly
- `context.py` — shared infrastructure imported by everyone for path resolution

Hook subprocesses are install-time snapshots, not a kernel sub-module: they live at `project/hooks_src/cbim_*.py` (source of truth) and execute from `.claude/hooks/cbim_*.py` after init. They bootstrap `<project>/.cbim/kernel/` onto `sys.path` and call kernel functions in-process — there is no MCP transport, no UDS, no subprocess hop into the server. One trigger family per sub-module. A change in the MCP wire protocol stays inside `mcp_server`; a change in hook behaviour stays inside `hooks_src/`.

## Key Decisions

- **Single runtime entry: the shim `.cbim/run` → `python -m engine`.** No `cbim` binary on `PATH`, no global venv, no installer/updater. The kernel lives at exactly one location per project (`<project>/.cbim/kernel/`) and is invoked exactly one way. Uninstall = `rm -rf .cbim/ .claude/agents/{architect,auditor,hr,programmer}/ .claude/commands/cbim_*.md .claude/hooks/cbim_*.py`. Refresh = re-run `/cbim_install` (idempotent).
- **`context.py` is a leaf file, not a sub-package.** Every sub-module imports `from context import project_root, cbim_dir, kernel_root`. Promoting it to a package would invert the dependency graph (everyone would depend on a `context` sub-module that itself depends on nothing). Keeping it as one file at the kernel root makes its "shared kernel primitive" status structurally obvious.
- **`services/` exists so `mcp_server/` and `dashboard/` never reach into `cbi/` or `memory/` directly.** Both servers are surface-area-heavy; without the façade layer they would pin kernel internals as their public API.
- **`project/` is the only sub-module that mutates the user's filesystem outside `.cbim/`.** Init writes `.claude/agents/`, `.claude/commands/`, `.claude/hooks/cbim_*.py`, `.claude/settings.json` (hooks + mcpServers + permissions.deny), `CLAUDE.md`, `.gitignore`, `.claudeignore`. Every other sub-module reads or writes inside `.cbim/` only.
- **MCP is the LLM write path; hooks are in-process.** All LLM-initiated writes to `.dna/`, `.claude/agents/`, and `.cbim/memory/` flow through `mcp_server/` (`dna_*`, `agent_*`, `memory_*` tools). Hook subprocesses (Claude Code lifecycle callbacks) bypass MCP entirely: they bootstrap `<project>/.cbim/kernel/` onto `sys.path` and call `memory.*` / `cbi.*` / `engine.*` directly. Hooks are trusted by the Claude Code framework — `permissions.deny` does not apply to them, only to LLM-driven tool calls.
- **Hook subprocesses can write `.cbim/` data directories, but never `.cbim/kernel/`.** Permitted writes: `.cbim/memory/short/`, `.cbim/logs/`, `.cbim/scheduler/`, `.cbim/.cc-status`, `.cbim/.debug`. The kernel code drop at `.cbim/kernel/` is owned by `/cbim_install` and never mutated by hooks.
- **`.cbim/` is invisible to LLM tools.** `permissions.deny` blocks `Read(.cbim/**)` and `Bash(.cbim/run *)`; `.claudeignore` hides it from indexing. Hooks are exempt — they are framework-level lifecycle callbacks, not LLM tool calls.
- **Sub-package vs leaf file is a deliberate axis.** `context.py` is a file because it has zero internal structure to encapsulate. Every other sub-module is a package because it has at least two collaborators that benefit from a shared boundary.

## Non-Goals

- No installer, updater, upgrade flow, migrate command, version pin, `versions.json`, `.cbim/.pin`, or `cbim_kernel.context` legacy import path.
- No `bin/` directory, no `cbim` launcher script on PATH, no global venv at `~/.cbim/`.
- No multi-version kernel staging. Each project carries its own kernel copy at `<project>/.cbim/kernel/`. To "upgrade", re-run `/cbim_install`.

