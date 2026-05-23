---
name: hooks
owner: architect
description: Claude Code lifecycle hooks: session start/end, prompt/tool logging, auto-preview
keywords: []
dependencies: []
---

## Deprecation

**Status: deprecated after Phase 3a (CBIM v1).** The hook scripts in this directory are no longer the runtime hook surface. Phase 3a moved the live hook scripts to `v1/src/kernel/project/hooks_src/cbim_*.py` — pure stdlib MCP clients that reach the server over the UDS socket at `~/.cache/cbim/<project-hash>/mcp.sock`. Phase 3b's `project/init.py` will copy those scripts into the user project's `.claude/hooks/` directory and point `.claude/settings.json` at them; the kernel's `hooks/` package is no longer invoked.

This directory is kept intact for two reasons:

1. **Rollback safety during the transition window** — existing user installations still wired through `.cbim/run hook <event>` keep working until they re-run `cbim project sync`.
2. **Reference for the new MCP server-side handlers** — the in-process logic that used to live here (`load_memory`, `write_memory`, `end_session`, `log_*`) was moved into `mcp_server/tools/hook.py`. Comparing the two side by side documents the lift-and-shift.

**Removal target: CBIM v1.1.** Once `sync` no longer wires `.cbim/run hook` and at least one minor release has passed, this directory will be deleted. Until then: do not extend, do not add new hooks here, do not import from elsewhere in the kernel.

## Positioning

**This package is the legacy in-process hook surface (Phase 0 — pre-MCP).** The live hook surface in Phase 3a+ lives at `v1/src/kernel/project/hooks_src/cbim_*.py` and runs out of `.claude/hooks/` after install. Those scripts are pure stdlib MCP clients; they talk to `mcp_server/tools/hook.py` over a Unix domain socket. They do **not** import `memory.*`, `cbi.*`, `engine.*`, or any other kernel package.

The directory you are reading is retained only as a transition-window fallback (see Deprecation) and will be removed in v1.1.

Historically, Claude Code's hook contract spawned a short-lived subprocess via `.cbim/run hook <event-name>`; `python -m engine` routed it into `hooks.dispatch`, which read the JSON event payload from stdin and invoked the matching handler in this module. Handlers imported kernel internals in-process for hot-path work (memory load/write, snapshot build, session-log open). The Phase 3a redesign collapses both halves of that pipeline (the routing shim and the in-process handlers) onto the MCP transport: hook scripts speak only MCP, and the equivalent in-process logic now lives behind `mcp_server/tools/hook.py`.

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

- **Hook scripts are install-time snapshots living at `.claude/hooks/`, written as pure stdlib + `_lib/` MCP clients.** They reach the kernel only through MCP tool calls over UDS (`~/.cache/cbim/<project-hash>/mcp.sock`) — never via Python import. Main source of truth: `v1/src/kernel/project/hooks_src/cbim_*.py`. Phase 3b's `project/init.py` copies them (with `_lib/`) into the user project's `.claude/hooks/`. This is the inversion of the original "import kernel internals in-process" decision and the reason `dependencies:` in this module's frontmatter must be empty.
- **B-plan pure: MCP unreachable → hook is a no-op + stderr warn.** No spool, no client-side retry beyond the 4-attempt backoff already baked into `_lib/mcp_client.py` (~1.75 s total). If the server cannot be reached after that, the hook exits 0, writes one `[CBIM:hook] mcp unreachable …` line to stderr, and the session keeps going. This is intentional: hot-path correctness lives server-side; if the server is down, the user is degraded but not blocked.
- **Server-side aggregation, client-side dispatch only.** Composite events (especially SessionStart, which used to compose `session_log start + load_context + build_snapshot + threshold banner`) are aggregated inside `mcp_server/tools/hook.py:snapshot_for_session_start`. Hook scripts never compose two business calls themselves — they fan out to one MCP tool per logical step, and that tool encapsulates the composition. This keeps the hook scripts trivial and lets us change the composition without re-installing client snapshots.
- **`auto_preview` stays a separate hook script even though it is also wired to SessionStart.** It calls one MCP tool (`dashboard_ensure_running`) which itself spawns the detached dashboard process server-side. Keeping it as a sibling script preserves the existing `.claude/settings.json` registration pattern (one script per SessionStart slot) and lets dashboard auto-launch be disabled independently of the main SessionStart payload.
- **No hook ever touches `.cbim/` directly.** Every file under `.cbim/` (session logs, `.cc-status`, memory entries, dashboard pid) is mutated exclusively by MCP tools server-side. Hook scripts neither read nor write `.cbim/` paths. This preserves the kernel-only-writes invariant for governance state and gives the dashboard one consistent writer.
- **Always exit 0.** A hook MUST NOT break the assistant turn. `_lib/mcp_client.py` converts every failure mode (unreachable, transport error, server returning `ok=false`) into a `None` return + a one-line stderr warning. Each hook's `main()` simply does `if result is None: return 0` and moves on.
- **No third-party imports, no `cbim.*` imports, no kernel imports.** Hook scripts depend on the Python stdlib and on the sibling `_lib/` package only. This is enforced by static reading; there is no runtime check. If a hook ever needs a kernel-side capability, the answer is to add an MCP tool, not to import.

## Non-Goals

- No upgrade-availability notifier. There is no upgrade flow; `load_memory` does not import any `updater.upgrade.notify` module (none exists).
- No `cbim_kernel.*` import paths. Imports use the flattened package roots: `context`, `memory.engine.*`, `cbi._primitives.snapshot`, `engine.session_log`, `engine.logger`.
- No subprocess invocation of `python -m cbim_kernel` anywhere in this module. `auto_preview` uses `python -m engine dashboard`.

