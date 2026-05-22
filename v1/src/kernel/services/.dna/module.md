---
name: services
owner: architect
description: Service layer: agent/log/memory/knowledge facades used by mcp_server and dashboard
keywords: []
dependencies: []
---

## Positioning

Facade layer between long-lived servers (`mcp_server`, `dashboard`) and kernel internals (`cbi`, `memory`). Provides stable, narrow APIs so the servers don't directly import volatile sub-package internals.

## Class Diagram

```mermaid
classDiagram
    class AgentService {
        +list_agents()
        +get_agent(name)
    }
    class LogService {
        +list_sessions()
        +tail_session(id)
    }
    class MemoryService {
        +query(filters)
        +write(entry)
    }
    class KnowledgeService {
        +get_snapshot()
        +list_modules()
    }
    class _fm {
        helper: frontmatter parsing
    }
    AgentService --> _fm
    KnowledgeService --> _fm
```

## Key Decisions

- **Services exist so the surface mcp_server / dashboard depend on stays stable across kernel refactors.** Without this layer, every renaming in `cbi/_primitives/modules.py` would break the MCP and dashboard tool surfaces.
- **No service writes — services are read-mostly.** Mutations go through the kernel CLI (e.g. `engine dna write-doc`), not through a service method.

