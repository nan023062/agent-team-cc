---
name: mcp-server
owner: architect
description: MCP tool/task server: exposes kernel ops to MCP clients (dna, agent, skill, snapshot, scheduler)
keywords: []
dependencies: []
---

## Positioning

MCP (Model Context Protocol) server exposing kernel ops as MCP tools. Tools defined under `tools/` — split by governance domain:

- **agent** — `agent_list`, `agent_show`, `agent_scaffold`, `agent_update`, `agent_add_skill`, `agent_archive` (4 of these are write tools added in Phase 1)
- **dna** — `dna_list`, `dna_show`, `dna_reindex`, `dna_init`, `dna_edit`, `dna_split`, `dna_write_doc` (deprecated), `dna_write_section` (deprecated) (5 of these are write tools added in Phase 1)
- **memory** — `memory_query`, `memory_list`, `memory_create`, `memory_delete`, `memory_reindex`, `memory_cleanup` (2 of these are governance writes added in Phase 1)
- **skill** — `skill_list`, `skill_show` (read-only)
- **snapshot** — `project_snapshot` (read-only)
- **scheduler** — task scheduler control surface
- **hook** — server-side facades called from Claude Code hook scripts (Phase 1 registers the surface; the hook UDS sidecar that calls them is Phase 2/3a): `snapshot_for_session_start`, `memory_distill_session`, `cc_status_set`, `session_log_append`, `tool_call_log`, `dashboard_ensure_running` (6 new tools)

Background tasks under `tasks/` (heartbeat).

Server lifespan now also binds a UDS listener at `~/.cache/cbim/<project-hash>/mcp.sock` for hook clients (Phase 2).

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
- **Hook UDS transport uses a simplified JSON-RPC-lite framing (newline-delimited) rather than full MCP JSON-RPC; FastMCP SDK is reserved for the stdio path consumed by Claude Code.**

## Non-Goals

- **No spool / no client-side cache.** When the MCP server is unreachable from a hook, the hook becomes a no-op — it does NOT queue events for later replay. This is the B-plan (pure) decision: hook reliability is bounded by server liveness, with no eventual-consistency layer to debug. Phase 2/3a will deliver the UDS sidecar that gives hooks a fast local path to the server; until then, hook-initiated work simply skips when the server is down.

