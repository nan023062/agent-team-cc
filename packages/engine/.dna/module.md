---
name: cbim-engine
owner: architect
description: Pure TypeScript core engine -- knowledge, memory, coordinator dispatch, migration, and cbim_* MCP tool layer. Zero VS Code dependency.
keywords: [engine, knowledge, memory, dispatch, migration, tools, mcp]
dependencies: []
---

## Positioning

The IDE-agnostic domain core of CBIM v2. Houses all business logic for module knowledge management, three-stage memory distillation, coordinator dispatch, v1-to-v2 migration, and the `cbim_*` MCP tool layer. Depends on no sibling package and no IDE-specific API.

## Sub-module Relationship Diagram

```mermaid
graph TD
    subgraph engine ["@cbim/engine"]
        KNOWLEDGE["packages/engine/src/knowledge<br/><i>Module CRUD, tree scanning,<br/>snapshot construction</i>"]
        MEMORY["packages/engine/src/memory<br/><i>Three-stage distillation:<br/>short - medium - distilled</i>"]
        DISPATCH["packages/engine/src/dispatch<br/><i>Coordinator dispatch;<br/>routes user intent to role +<br/>assembles SDK config</i>"]
        MIGRATION["packages/engine/src/migration<br/><i>v1 to v2 project layout<br/>migration planner + executor</i>"]
        TOOLS["packages/engine/src/tools<br/><i>cbim_* MCP server:<br/>schema + call engine fn +<br/>format output</i>"]
    end

    DISPATCH -->|"assembles SDK config"| TOOLS
    DISPATCH -->|"reads agent context"| KNOWLEDGE
    DISPATCH -->|"injects memory"| MEMORY
    TOOLS -->|"wraps as MCP"| KNOWLEDGE
    TOOLS -->|"wraps as MCP"| MEMORY

    style KNOWLEDGE fill:#e8f4fd,stroke:#2980b9
    style MEMORY fill:#e8f4fd,stroke:#2980b9
    style DISPATCH fill:#e8f4fd,stroke:#2980b9
    style MIGRATION fill:#f4e8fd,stroke:#8e44ad
    style TOOLS fill:#fef3e2,stroke:#e67e22
```

**Internal dependency direction:**
- `dispatch/` depends on `knowledge/` (reads agent configs and module context), `memory/` (injects memory into agent sessions), and `tools/` (gets MCP server + per-role tool configs for SDK assembly)
- `tools/` depends on `knowledge/` and `memory/` (wraps their functions as MCP tools)
- `knowledge/` and `memory/` are independent of each other
- `migration/` is fully isolated -- no runtime coupling with other sub-modules

## Key Decisions

- **Why zero VS Code dependency?** Engine is the stable foundation reused by extension, cli, and potentially future IDE plugins or web-based tools. Any VS Code import would make it non-portable. Enforced at the package boundary: `@cbim/engine` has no `@types/vscode` in its dependency tree.

- **Why five sub-directories, not five separate packages?** `knowledge`, `memory`, `dispatch`, `migration`, and `tools` share a deployment lifecycle and version. Splitting them into separate npm packages would create unnecessary versioning coordination overhead. Engine exposes them as sub-path exports (`@cbim/engine/knowledge`, etc.), giving consumers tree-shaking granularity without package sprawl.

- **Why migration/ is isolated?** Migration is a one-time operation per project. It has no runtime coupling with knowledge/memory/dispatch and should not add weight to the engine's runtime footprint. Pure file transformation with no engine runtime state.
