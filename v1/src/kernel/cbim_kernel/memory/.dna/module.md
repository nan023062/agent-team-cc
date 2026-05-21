---
name: memory
owner: architect
description: Project-local memory subsystem: short/medium/archive tiers, file backend
keywords: []
dependencies: []
---
## Positioning

Project-local memory subsystem. Three tiers (short / medium / archive) under `.cbim/memory/store/`. File-based backend today; pluggable via `MemoryBackend` ABC.

## Class Diagram

```mermaid
classDiagram
    class MemoryBackend {
        <<interface>>
        +write(entry)
        +query(filters) list
        +delete(id)
    }
    class FileBackend {
        +base_dir: Path
        +write(entry)
        +query(filters)
    }
    class Writer {
        +write_short(entry)
        +write_medium(entry)
    }
    class config {
        +keep_days, max_short, etc.
    }
    class engine_cli {
        +cmd_write / load_context / create / add / query / delete / reindex / cleanup
    }
    FileBackend ..|> MemoryBackend
    Writer --> FileBackend
    engine_cli --> Writer
    engine_cli --> config
```

## Key Decisions

- **`.cbim/memory/store/` is the canonical home.** Claude Code's built-in `~/.claude/projects/.../memory/` is explicitly disabled in CBIM projects (called out in the deployed `CLAUDE.md`).
- **File backend is intentionally chosen over SQLite/etc.** Markdown files are human-inspectable, git-friendly, and trivially merged. Performance is not a concern at the scale of one developer's memory.
