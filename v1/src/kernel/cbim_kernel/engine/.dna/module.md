---
name: kernel-cli
owner: architect
description: Kernel CLI top-level dispatcher: forwards subcommands to cbi/memory/agents/dna
keywords: []
dependencies: []
---

## Positioning

Top-level kernel CLI dispatcher. Receives `python -m cbim_kernel <cmd> <args>` from the launcher and routes to the appropriate sub-engine (`cbi._primitives.cli` for dna/agent/skill, `memory.engine` for memory, `project` for init/migrate/upgrade) or to a built-in (logs, debug, version).

## Class Diagram

```mermaid
classDiagram
    class cli {
        +main(argv) int
        +build_parser() ArgumentParser
        +cmd_version(args)
        +cmd_skill_show(args)
    }
    class __main__ {
        forwards sys.argv to cli.main
    }
    cli --> cbim_kernel.cbi._primitives.cli : dna / agent subcommands
    cli --> cbim_kernel.memory.engine : memory subcommands
    cli --> cbim_kernel.project : init / migrate / upgrade
```

## Key Decisions

- **Thin dispatcher only — no business logic lives here.** All real work delegates to sub-engines. This keeps `engine/cli.py` legible and prevents it from accumulating cross-domain knowledge.
- **`skill show` is the discovery surface for the CBI agents.** Agent prompts reference skill IDs (`architect.arch_modules`, etc.) and the engine returns the skill content; this is how knowledge ships to LLM context.

