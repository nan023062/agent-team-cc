---
name: mcp-server
owner: architect
description: MCP tool/task server: exposes kernel ops to MCP clients (dna, agent, skill, snapshot, scheduler)
keywords: []
dependencies: []
---
## Positioning

MCP (Model Context Protocol) server exposing kernel ops as MCP tools. Tools defined under `tools/` (dna, agent, skill, snapshot, scheduler). Background tasks under `tasks/` (heartbeat).

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
