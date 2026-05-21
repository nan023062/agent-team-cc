---
name: hooks
owner: architect
description: Claude Code lifecycle hooks: session start/end, prompt/tool logging, auto-preview
keywords: []
dependencies: []
---
## Positioning

Claude Code lifecycle hooks bound to a CBIM project. Run as short-lived subprocesses invoked by Claude Code's hook contract (stdin = JSON event, stdout = `additionalContext` JSON or plain stdout, exit 0).

## Class Diagram

```mermaid
classDiagram
    class load_memory {
        +SessionStart hook
        +loads recent memory + project snapshot
        +emits additionalContext JSON
    }
    class write_memory {
        +SessionEnd-like hook
        +flushes session memory tier
    }
    class end_session {
        +SessionEnd hook
        +closes session log
    }
    class log_user_prompt
    class log_pre_tool
    class log_post_tool
    class auto_preview {
        +PostToolUse hook
        +emits diff preview to stderr
    }
    load_memory --> CTX[cbim_kernel.context]
    load_memory --> ENG[python -m cbim_kernel memory load-context]
    load_memory --> ENG2[python -m cbim_kernel snapshot]
    write_memory --> CTX
    end_session --> CTX
    log_user_prompt --> CTX
    log_pre_tool --> CTX
    log_post_tool --> CTX
    auto_preview --> CTX
```

## Key Decisions

- **Hooks shell out to the kernel CLI instead of importing kernel internals.** This isolates hooks from kernel refactors — a hook only depends on the stable command surface (`python -m cbim_kernel <cmd>`), not on Python APIs. Cost is one subprocess per hook firing, acceptable for low-frequency lifecycle events.
- **`load_memory` is the SessionStart slot — and the natural home for the upgrade-availability notifier.** The `project.upgrade` notifier will be added here as one additional stdout line (`[cbim] update available: X → Y`) when a fresh diagnosis is cached. It does NOT block, does NOT add to `additionalContext`, and silently skips on any failure.
- **No hook ever writes to `.cbim/config.json` or `.cbim/index.md`.** Hooks read project state; they do not mutate governance state. Mutations go through the kernel CLI.
