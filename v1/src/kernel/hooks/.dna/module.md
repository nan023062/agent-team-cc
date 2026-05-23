---
name: hooks
owner: architect
description: Claude Code lifecycle hooks: session start/end, prompt/tool logging, auto-preview
keywords: []
dependencies:
  - v1/src/kernel/memory
  - v1/src/kernel/cbi
  - v1/src/kernel/engine
---

## Positioning

The bridge between Claude Code's hook contract and the kernel. Each Claude Code lifecycle event (`SessionStart`, `Stop`, `SessionEnd`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`) fires a short-lived subprocess via the shim — `.cbim/run hook <event-name>` — which `python -m engine` routes to `hooks.dispatch`. Dispatch reads the JSON event payload from stdin and invokes the matching handler in this module.

Hooks live inside the kernel package so they import kernel internals **in-process**. Memory load, memory write, snapshot build, session-log open — all called as Python functions, no second subprocess hop. The only outbound subprocess in this module is `auto_preview`, which spawns the long-lived dashboard server (process supervision, a different concern from one-shot computation).

## Sub-module Relationships

```mermaid
classDiagram
    class dispatch {
        +EVENT_MAP session-start session-end stop log-prompt log-pre-tool log-post-tool
        +reads stdin JSON
        +swallows all handler exceptions returns 0
    }
    class load_memory {
        +SessionStart phase 1
        +opens session log
        +loads short-term memory + project snapshot
        +emits additionalContext JSON
    }
    class auto_preview {
        +SessionStart phase 2
        +spawns dashboard server detached via python -m engine dashboard
    }
    class write_memory {
        +Stop hook per assistant turn
        +logs [ASSIST] line
        +writes short-term memory entry
        +marks .cc-status idle
    }
    class end_session {
        +SessionEnd hook
        +finalises session log
    }
    class log_user_prompt {
        +UserPromptSubmit
        +appends to session log
    }
    class log_pre_tool {
        +PreToolUse
        +appends to call log
    }
    class log_post_tool {
        +PostToolUse
        +appends to call log
    }

    dispatch --> load_memory : session-start phase 1
    dispatch --> auto_preview : session-start phase 2
    dispatch --> write_memory : stop
    dispatch --> end_session : session-end
    dispatch --> log_user_prompt : log-prompt
    dispatch --> log_pre_tool : log-pre-tool
    dispatch --> log_post_tool : log-post-tool

    load_memory --> CTX[context.project_root / cbim_dir]
    load_memory --> MEM_LOAD[memory.engine.loader.load_context]
    load_memory --> SNAP[cbi._primitives.snapshot.build_snapshot]
    load_memory --> SLOG[engine.session_log.start_session]

    write_memory --> CTX
    write_memory --> MEM_WRITE[memory.engine.writer.write_session]
    write_memory --> LOGGER[engine.logger.log_assist]

    end_session --> LOGGER2[engine.logger.end_session]
    auto_preview --> DASH[subprocess: python -m engine dashboard]
    log_user_prompt --> CTX
    log_pre_tool --> CTX
    log_post_tool --> CTX
```

Dependency edges out of this module land on three stable packages: `context` (root resolution), `memory.engine` (loader/writer), `cbi._primitives.snapshot` (project knowledge snapshot), and `engine.{session_log, logger}` (logging primitives). Nothing in `hooks/` imports `services`, `dashboard`, `mcp_server`, or `project`.

## Origin Context

Claude Code's hook contract is fire-and-forget from the assistant's perspective: each event spawns a subprocess, reads its stdout as `additionalContext` (for SessionStart) or simply runs to completion. The kernel needs to attach behavior to six events:

- **SessionStart** — prime the assistant with short-term memory + project knowledge snapshot, open the session log file, and opportunistically spawn the dashboard server. Two handlers (`load_memory` + `auto_preview`) run sequentially under one dispatch slot to keep stdout ordering predictable.
- **Stop** — persist what the assistant just produced as a short-term memory entry; log the assistant turn.
- **SessionEnd** — finalize the session log.
- **UserPromptSubmit** — append the user message to the session log.
- **PreToolUse / PostToolUse** — append tool-call frames to the call log.

One handler per event family. Handlers are siblings — none imports another. Shared infrastructure (path resolution, memory engine, logger) is pulled from the lower-tier kernel packages, never from a peer.

## Key Decisions

- **Hooks import kernel internals in-process; they do NOT shell out to the CLI for hot-path work.** Memory load (`memory.engine.loader.load_context`), memory write (`memory.engine.writer.write_session`), and snapshot build (`cbi._primitives.snapshot.build_snapshot`) are called as Python functions inside the hook process. SessionStart and Stop fire on every turn; a subprocess hop adds ~150-300 ms of Python startup latency per fire, and these functions were never CLI-only. The hook IS already a Python process with the kernel importable — direct imports are strictly cheaper and equally stable, since hooks ship in the same kernel drop as the engines they call.
- **`auto_preview` is the exception, and it is the right exception.** It does `subprocess.Popen([python, "-m", "engine", "dashboard"], env={"PYTHONPATH": kernel_root, ...})` with detached process flags — not because it needs the CLI surface, but because it needs to spawn a **detached long-lived server** that outlives the hook. That is process supervision, not API invocation; subprocess is the correct primitive. Note the `-m engine` form (not `-m cbim_kernel`); the kernel root is on `PYTHONPATH` via the shim, so `engine` is the top-level package name.
- **SessionStart runs two handlers under one dispatch slot.** `dispatch.run_session_start` calls `load_memory.main(event)` then `auto_preview.main(event)` in sequence under one try/except per handler. This avoids racing two separate SessionStart hook registrations and keeps stdout ordering predictable for the assistant's `additionalContext`.
- **No hook ever writes to `.cbim/config.json` or `.cbim/index.md` or `.dna/`.** Hooks read project state and write to memory/log tiers only. Governance-state mutations (config, dna, agent) go through the kernel CLI from the LLM side. This preserves the kernel-only-writes invariant for governed directories.
- **Every hook swallows exceptions.** A hook MUST NOT break the assistant turn. Failures surface on stderr (visible in `.cbim/logs/`) but `dispatch` always returns 0. `dispatch` itself catches handler exceptions; each handler also catches its own internal errors as a defense-in-depth measure.
- **Hook event names use kebab-case at the dispatch boundary.** `EVENT_MAP` maps `session-start`, `session-end`, `stop`, `log-prompt`, `log-pre-tool`, `log-post-tool` → `run_*` handler functions. Claude Code's settings.json wires its native event names (e.g. `SessionStart`, `UserPromptSubmit`) to the corresponding `.cbim/run hook <kebab-name>` invocation; the mapping is the kernel's stable contract.

## Non-Goals

- No upgrade-availability notifier. There is no upgrade flow; `load_memory` does not import any `updater.upgrade.notify` module (none exists).
- No `cbim_kernel.*` import paths. Imports use the flattened package roots: `context`, `memory.engine.*`, `cbi._primitives.snapshot`, `engine.session_log`, `engine.logger`.
- No subprocess invocation of `python -m cbim_kernel` anywhere in this module. `auto_preview` uses `python -m engine dashboard`.
