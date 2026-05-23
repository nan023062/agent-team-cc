---
name: cbi-skills
owner: architect
description: CBI cross-agent skills: dispatch, memory_write, memory_query, memory_distill
keywords: []
dependencies: []
---
## Positioning

Cross-agent skills: `dispatch` (assistant's routing skill), `memory_write` / `memory_query` / `memory_distill` (memory ops invoked by the assistant on user request).

## Class Diagram

```mermaid
classDiagram
    class dispatch {
        +skill.py
        +classifies user request → which agent
    }
    class memory_write
    class memory_query
    class memory_distill
    note "All four are agent-agnostic: any agent or the assistant can invoke them via `engine skill show <id>`."
```

## Key Decisions

- **A skill lives here only if more than one agent (or the assistant + an agent) invokes it.** Single-agent skills live under that agent's directory. This boundary keeps the cross-agent surface small.
