---
name: hooks
owner: architect
description: Claude Code lifecycle hooks: session start/end, prompt/tool logging, auto-preview
keywords: []
dependencies:
  - v1/src/kernel/cbim_kernel
  - v1/src/kernel/cbim_kernel/memory
  - v1/src/kernel/cbim_kernel/cbi/_primitives
---

## Positioning

Claude Code lifecycle hooks bound to a CBIM project. Run as short-lived subprocesses invoked by Claude Code's hook contract (stdin = JSON event, stdout = `additionalContext` JSON or plain stdout, exit 0).

Hooks live inside the kernel package so they can **import kernel internals directly** — no subprocess round-trip to the CLI for the hot path (memory load/write, snapshot build). The only outbound subprocess in this module is `auto_preview`, which spawns the long-lived dashboard server (a different concern: process supervision, not one-shot computation).

## Class Diagram

```mermaid
classDiagram
    class load_memory {
        +SessionStart hook
        +opens session log
        +loads recent memory + project snapshot
        +emits additionalContext JSON
    }
    class write_memory {
        +Stop hook (per assistant turn)
        +logs [ASSIST] line
        +writes short-term memory entry
        +marks .cc-status idle
    }
    class end_session {
        +SessionEnd hook
        +finalises session log
    }
    class auto_preview {
        +SessionStart hook
        +spawns dashboard server (detached)
    }
    class log_user_prompt
    class log_pre_tool
    class log_post_tool

    load_memory --> CTX[cbim_kernel.context]
    load_memory --> MEM_LOAD[memory.engine.loader.load_context]
    load_memory --> SNAP[cbi._primitives.snapshot.build_snapshot]
    load_memory --> SLOG[engine.session_log.start_session]
    load_memory --> UPG[updater.upgrade.notify.session_start_line]

    write_memory --> CTX
    write_memory --> MEM_WRITE[memory.engine.writer.write_session]
    write_memory --> LOGGER[engine.logger.log_assist]

    end_session --> CTX
    end_session --> LOGGER2[engine.logger.end_session]

    auto_preview --> CTX
    auto_preview --> DASH[python -m cbim_kernel dashboard]

    log_user_prompt --> CTX
    log_pre_tool --> CTX
    log_post_tool --> CTX
```

## Key Decisions

- **Hooks import kernel internals in-process; they do NOT shell out to the CLI for hot-path work.** Memory load (`memory.engine.loader.load_context`), memory write (`memory.engine.writer.write_session`), and snapshot build (`cbi._primitives.snapshot.build_snapshot`) are all called as Python functions inside the hook process. Rationale: SessionStart and Stop fire on every turn; a subprocess hop adds ~150-300ms of Python startup latency per fire, and the CLI surface for these operations was an LLM-facing convenience that hooks never needed. The hook IS already a Python process with `cbim_kernel` importable — direct imports are strictly cheaper and equally stable, since hooks ship in the same wheel as the engines they call.
- **`auto_preview` is the exception, and it is the right exception.** It does `subprocess.Popen([python, "-m", "cbim_kernel", "dashboard"])` with `DETACHED_PROCESS` — not because it needs the CLI surface, but because it needs to spawn a **detached long-lived server** that outlives the hook. That is process supervision, not API invocation; subprocess is the correct primitive.
- **`load_memory` is the SessionStart slot — and the natural home for the upgrade-availability notifier.** The upgrade banner comes from `updater.upgrade.notify.session_start_line` as one additional line prepended to `additionalContext` when a fresh diagnosis is cached. It does NOT block, does NOT add a separate stdout line, and silently skips on any failure.
- **No hook ever writes to `.cbim/config.json` or `.cbim/index.md`.** Hooks read project state and write to memory/log tiers only. Governance-state mutations (config, dna, index) go through the kernel CLI from the LLM side.
- **Every hook swallows exceptions.** A hook MUST NOT break the assistant turn. Failures surface on stderr (visible in `.cbim/logs/`) but always exit 0.
