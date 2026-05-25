---
name: mcp-server
owner: architect
description: MCP tool/task server: exposes kernel ops to MCP clients (dna, agent, skill, snapshot, scheduler, runtime, audit)
keywords: []
dependencies: []
---

## Positioning

MCP (Model Context Protocol) server exposing kernel ops as MCP tools over stdio for LLM tool calls. Tools defined under `tools/` — split by governance domain:

- **agent** — `agent_list`, `agent_show`, `agent_scaffold`, `agent_update`, `agent_add_skill`, `agent_archive`
- **dna** — `dna_list`, `dna_show`, `dna_reindex`, `dna_init`, `dna_edit`, `dna_split`, `dna_write_doc` (deprecated), `dna_write_section` (deprecated)
- **memory** — `memory_query`, `memory_get`, `memory_list`, `memory_create`, `memory_delete`, `memory_reindex`, `memory_cleanup`
- **skill** — `skill_list`, `skill_show` (read-only)
- **snapshot** — `project_snapshot` (read-only)
- **scheduler** — task scheduler control surface (`scheduler_status`, `scheduler_trigger`)
- **runtime** — slash-command back-end: `dashboard_ensure_running`, `debug_get`, `debug_set`, `log_show`
- **audit** — read-only governance drift checks: `audit_run`, `audit_list_checks`

Background tasks under `tasks/` (heartbeat).

The server lifespan owns the embedded task scheduler. Hook subprocesses do NOT call this server — they run in-process and import kernel modules directly (see `project/hooks_src/`).

## Class Diagram

```mermaid
classDiagram
    class server {
        +main()
        +register_tools()
    }
    class scheduler {
        +run_task(name)
    }
    class dna_tool
    class agent_tool
    class skill_tool
    class snapshot_tool
    class scheduler_tool
    class heartbeat_task
    server --> dna_tool
    server --> agent_tool
    server --> skill_tool
    server --> snapshot_tool
    server --> scheduler_tool
    scheduler --> heartbeat_task
    dna_tool --> SVC[services.KnowledgeService]
    agent_tool --> SVC2[services.AgentService]
```

## Key Decisions

- **All tools talk to `services/`, not to `cbi/` or `memory/` directly.** Preserves the facade boundary.
- **MCP server is the LLM write path only.** Hook subprocesses (Claude Code lifecycle callbacks) bypass MCP entirely and import kernel modules in-process; `mcp` SDK is therefore a soft dependency, required only when the LLM wants to call governance tools.
- **Slash commands talk to MCP tools, never to a Bash CLI.** Project-side `.claude/commands/cbim_*.md` invoke `mcp__cbim__*` tools (e.g. `dashboard_ensure_running`, `debug_set`, `log_show`). Shelling out to `cbim ...` from a slash command is a regression — it bypasses MCP logging, ignores `.cbim/` read-permission denials, and routes through whatever `cbim` binary the user's PATH happens to find (often a stale global pin-launcher, not the project kernel).

## Non-Goals

- **No hook transport.** Hook subprocesses do not connect to this server (no UDS listener, no hook-facing MCP tools). Hook reliability is decoupled from server liveness.

