---
description: Inspect/trigger CBIM scheduler tasks
argument-hint: status | trigger <task-name>
allowed-tools: Bash
---

Dispatch on `$ARGUMENTS`:

- `status` (or empty) → call the `scheduler_status` MCP tool and display the task list with last-run state
- `trigger <name>` → call `scheduler_trigger` with the given task name
- Anything else → print usage: `/cbim_sched status | trigger <task-name>`

The scheduler lives inside the CBIM MCP server (`.cbim/kernel/mcp_server/server.py`) and ticks every 30s. Tasks come from `.cbim/kernel/mcp_server/tasks/*.py`. Lifetime is tied to the MCP server — Claude Code starts it on session start, kills it on exit.
